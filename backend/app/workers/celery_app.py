"""
Celery application — task queue for async compliance, audit, and network jobs.
Queues: audit, compliance, monitoring, network, remediation, default
"""

from __future__ import annotations

import time
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure

from app.core.config import settings

celery_app = Celery("nexusguard_security")

celery_app.conf.update(
    broker_url=settings.celery.BROKER_URL,
    result_backend=settings.celery.RESULT_BACKEND,
    task_serializer=settings.celery.TASK_SERIALIZER,
    result_serializer=settings.celery.RESULT_SERIALIZER,
    accept_content=settings.celery.ACCEPT_CONTENT,
    timezone=settings.celery.TIMEZONE,
    enable_utc=settings.celery.ENABLE_UTC,
    task_soft_time_limit=settings.celery.TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.celery.TASK_TIME_LIMIT,
    worker_prefetch_multiplier=settings.celery.WORKER_PREFETCH_MULTIPLIER,
    worker_concurrency=settings.celery.WORKER_CONCURRENCY,
    task_routes={
        "app.workers.tasks.run_device_audit":        {"queue": "audit"},
        "app.workers.tasks.run_compliance_eval":     {"queue": "compliance"},
        "app.workers.tasks.run_bulk_compliance":     {"queue": "compliance"},
        "app.workers.tasks.run_remediation":         {"queue": "remediation"},
        "app.workers.tasks.export_siem_batch":       {"queue": "audit"},
        "app.workers.tasks.poll_device_compliance":  {"queue": "monitoring"},
    },
    beat_schedule={
        "fleet-compliance-poll": {
            "task": "app.workers.tasks.poll_fleet_compliance",
            "schedule": settings.COMPLIANCE_POLLING_INTERVAL_SECONDS,
        },
    },
)


# ── Metrics hooks ──────────────────────────────────────────────────────────────

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    task._start_time = time.monotonic()


@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, *args, **kwargs):
    from app.core.metrics import WORKER_TASKS_TOTAL, WORKER_TASK_DURATION
    duration = time.monotonic() - getattr(task, "_start_time", time.monotonic())
    WORKER_TASKS_TOTAL.labels(task_name=task.name, status=state.lower()).inc()
    WORKER_TASK_DURATION.labels(task_name=task.name).observe(duration)


@task_failure.connect
def task_failure_handler(task_id, exception, traceback, *args, **kwargs):
    import structlog
    log = structlog.get_logger(__name__)
    log.error("worker.task.failed", task_id=task_id, error=str(exception))


# ── Queue depth metrics (scraped by Prometheus) ───────────────────────────────────────

def update_queue_depth_metrics() -> None:
    """Update WORKER_QUEUE_DEPTH gauges from Redis broker queue lengths."""
    try:
        from app.core.metrics import WORKER_QUEUE_DEPTH
        from app.core.config import settings
        import redis as sync_redis

        r = sync_redis.from_url(settings.celery.BROKER_URL, socket_connect_timeout=2)
        for queue in ("audit", "compliance", "remediation", "monitoring", "default"):
            depth = r.llen(queue)
            WORKER_QUEUE_DEPTH.labels(queue_name=queue).set(depth)
    except Exception:
        pass  # Non-critical — metrics best-effort
