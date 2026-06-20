"""
Celery task definitions — all async work dispatched from API handlers.
Each task is idempotent and records metrics on completion.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.workers.tasks.run_device_audit",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def run_device_audit(self, device_id: str, device_ip: str, platform: str = "ios"):
    """Execute a full device audit and store results."""
    log.info("task.device_audit.started", device_id=device_id, device_ip=device_ip)
    try:
        from app.core.dependencies import _get_execution_engine
        pipeline, _, creds_store = _get_execution_engine()

        async def _audit():
            creds = await creds_store.get_credentials(device_ip)
            if not creds:
                return {"status": "skipped", "reason": "no_credentials"}
            from app.services.network.device_executor import CONFIG_COMMANDS, DevicePlatform
            plat = DevicePlatform(platform) if platform in DevicePlatform._value2member_map_ else DevicePlatform.IOS
            result = await pipeline._ssh.execute(creds, CONFIG_COMMANDS.get(plat, []))
            return {"status": "success" if result.success else "failed", "device_id": device_id}

        return _run_async(_audit())
    except Exception as exc:
        log.error("task.device_audit.failed", device_id=device_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.workers.tasks.run_compliance_eval",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def run_compliance_eval(self, device_id: str, frameworks: list[str] | None = None):
    """Run compliance evaluation for a single device."""
    log.info("task.compliance_eval.started", device_id=device_id)
    try:
        from app.core.dependencies import get_compliance_orchestrator, get_device_config
        from app.domain.compliance.engine.compliance_engine import ComplianceFramework

        async def _eval():
            config = await get_device_config(device_id)
            if not config:
                return {"status": "skipped", "reason": "no_config"}
            orchestrator = get_compliance_orchestrator()
            fw_list = [ComplianceFramework(f) for f in (frameworks or ["cis"])]
            report = await orchestrator.evaluate_device(
                device_id=UUID(device_id),
                device_config=config,
                device_metadata={"device_id": device_id},
                frameworks=fw_list,
            )
            return {
                "status": "success",
                "device_id": device_id,
                "score": float(report.overall_score),
                "pass_count": report.pass_count,
                "fail_count": report.fail_count,
            }

        return _run_async(_eval())
    except Exception as exc:
        log.error("task.compliance_eval.failed", device_id=device_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.run_bulk_compliance")
def run_bulk_compliance(device_ids: list[str], frameworks: list[str] | None = None):
    """Fan-out compliance evaluation across a device fleet."""
    log.info("task.bulk_compliance.started", count=len(device_ids))
    results = []
    for device_id in device_ids:
        result = run_compliance_eval.apply_async(
            args=[device_id, frameworks],
            queue="compliance",
        )
        results.append(result.id)
    return {"dispatched": len(results), "task_ids": results}


@celery_app.task(
    name="app.workers.tasks.run_remediation",
    bind=True,
    max_retries=1,
)
def run_remediation(self, device_id: str, device_ip: str, commands: list[str], drift_id: str):
    """Execute automated remediation commands on a device."""
    log.info("task.remediation.started", device_id=device_id, drift_id=drift_id)
    try:
        from app.core.dependencies import get_compliance_monitor
        from app.domain.compliance.models import DriftEvent

        async def _remediate():
            monitor = get_compliance_monitor()
            if monitor._remediation and monitor._remediation._executor:
                drift = DriftEvent(drift_id=drift_id, device_id=device_id, device_ip=device_ip)
                return await monitor._remediation.execute_remediation(
                    device_id=device_id,
                    device_ip=device_ip,
                    commands=commands,
                    drift_event=drift,
                )
            return {"status": "skipped", "reason": "no_remediation_workflow"}

        return _run_async(_remediate())
    except Exception as exc:
        log.error("task.remediation.failed", device_id=device_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.poll_fleet_compliance")
def poll_fleet_compliance():
    """Scheduled task: trigger compliance poll for all registered devices."""
    log.info("task.fleet_poll.started")
    try:
        from app.core.dependencies import get_compliance_monitor

        async def _poll():
            monitor = get_compliance_monitor()
            states = monitor.get_all_states()
            for state in states:
                run_compliance_eval.apply_async(
                    args=[state.device_id, [f.value for f in state.frameworks]],
                    queue="compliance",
                )
            return {"polled": len(states)}

        return _run_async(_poll())
    except Exception as exc:
        log.error("task.fleet_poll.failed", error=str(exc))
        raise
