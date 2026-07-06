"""
Workflows — high-level security operations (compliance, CVE, chat, etc.).
These are composed from prompt management and provider execution.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.domain.ai.providers.models import CopilotOperation, CopilotRequest

log = structlog.get_logger(__name__)


class ComplianceWorkflow:
    """Compliance explanation and recommendation workflows."""

    @staticmethod
    async def explain_failure(
        rule_id: str,
        rule_name: str,
        findings: list[str],
        device_metadata: dict[str, Any],
        framework: str,
        process_fn,
    ) -> str:
        context = {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "framework": framework.upper(),
            "findings": findings,
            "device": device_metadata,
        }
        user_msg = (
            f"Explain this {framework.upper()} compliance failure:\n"
            f"Rule: {rule_name} ({rule_id})\n"
            f"Device: {device_metadata.get('hostname', 'unknown')} "
            f"({device_metadata.get('device_type', 'network device')})\n"
            f"Findings:\n" + "\n".join(f"  - {f}" for f in findings)
        )
        request = CopilotRequest(
            operation=CopilotOperation.COMPLIANCE_EXPLAIN,
            user_message=user_msg,
            context=context,
        )
        response = await process_fn(request)
        log.info("workflow.compliance.explained", rule_id=rule_id, framework=framework)
        return response.content

    @staticmethod
    async def recommend_improvements(
        framework_scores: list[dict[str, Any]],
        fleet_context: dict[str, Any],
        process_fn,
    ) -> str:
        context = {
            "framework_scores": framework_scores,
            "fleet": fleet_context,
        }
        score_lines = "\n".join(
            f"  - {s.get('id', s.get('framework', 'unknown')).upper()}: "
            f"{s.get('avg_score', s.get('overall_score', 0)):.1f}% "
            f"({s.get('device_count', 1)} device(s))"
            for s in framework_scores
        )
        user_msg = (
            f"Based on the current compliance scores, recommend the highest-impact improvements:\n"
            f"{score_lines}\n\n"
            f"Fleet: {fleet_context.get('total_devices', 0)} devices, "
            f"{fleet_context.get('active_drift_events', 0)} active drift events."
        )
        request = CopilotRequest(
            operation=CopilotOperation.COMPLIANCE_RECOMMEND,
            user_message=user_msg,
            context=context,
        )
        response = await process_fn(request)
        log.info("workflow.compliance.recommendations_generated")
        return response.content


class CVEWorkflow:
    """CVE analysis workflow."""

    @staticmethod
    async def explain_cve(
        cve_id: str,
        affected_devices: list[dict[str, Any]],
        process_fn,
    ) -> str:
        device_summary = (
            f"{len(affected_devices)} affected device(s): "
            + ", ".join(d.get("hostname", d.get("device_id", "unknown")) for d in affected_devices[:5])
        ) if affected_devices else "No specific devices provided."

        request = CopilotRequest(
            operation=CopilotOperation.CVE_EXPLAIN,
            user_message=(
                f"Explain {cve_id} and its impact on our infrastructure.\n"
                f"Affected devices: {device_summary}"
            ),
            context={"cve_id": cve_id, "affected_devices": affected_devices},
        )
        response = await process_fn(request)
        log.info("workflow.cve.explained", cve_id=cve_id)
        return response.content


class ChatWorkflow:
    """General chat workflow for assistant interactions."""

    @staticmethod
    async def chat(
        user_message: str,
        session_id: str,
        history,  # list[LLMMessage]
        context: dict[str, Any] | None = None,
        process_fn=None,
    ) -> str:
        request = CopilotRequest(
            operation=CopilotOperation.CHAT,
            user_message=user_message,
            session_id=session_id,
            conversation_history=history,
            context=context or {},
        )
        response = await process_fn(request)
        log.debug("workflow.chat.completed", session_id=session_id, tokens=response.total_tokens)
        return response.content


class AttackPathWorkflow:
    """Attack path analysis workflow."""

    @staticmethod
    async def analyze_paths(
        network_topology: dict[str, Any],
        compliance_findings: list[dict[str, Any]],
        process_fn,
    ) -> str:
        request = CopilotRequest(
            operation=CopilotOperation.ATTACK_PATH,
            user_message=(
                f"Analyze potential attack paths through our network. "
                f"We have {len(compliance_findings)} compliance finding(s) and "
                f"{len(network_topology.get('devices', []))} device(s) in scope."
            ),
            context={"topology": network_topology, "findings": compliance_findings},
        )
        response = await process_fn(request)
        log.info("workflow.attack_path.analyzed")
        return response.content


class ConfigAnalysisWorkflow:
    """Device configuration analysis workflow."""

    @staticmethod
    async def analyze_config(
        device_config: str,
        device_metadata: dict[str, Any],
        process_fn,
    ) -> str:
        request = CopilotRequest(
            operation=CopilotOperation.CONFIG_ANALYZE,
            user_message=(
                f"Perform a security assessment of this device configuration:\n"
                f"Device: {device_metadata.get('hostname', 'unknown')} "
                f"({device_metadata.get('device_type', 'unknown')})\n"
                f"```\n{device_config}\n```"
            ),
            context={"device": device_metadata},
        )
        response = await process_fn(request)
        log.info("workflow.config_analysis.completed", device=device_metadata.get("device_id"))
        return response.content


class RiskPrioritizationWorkflow:
    """Risk prioritization workflow."""

    @staticmethod
    async def prioritize_risks(
        findings: list[dict[str, Any]],
        asset_metadata: dict[str, Any],
        process_fn,
    ) -> str:
        severity_counts: dict[str, int] = {}
        for f in findings:
            sev = f.get("severity", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        request = CopilotRequest(
            operation=CopilotOperation.RISK_PRIORITIZE,
            user_message=(
                f"Prioritize {len(findings)} security findings by risk and remediation effort.\n"
                f"Severity breakdown: "
                + ", ".join(f"{k}: {v}" for k, v in severity_counts.items())
            ),
            context={"findings": findings, "assets": asset_metadata},
        )
        response = await process_fn(request)
        log.info("workflow.risk_prioritization.completed")
        return response.content


class IncidentAnalysisWorkflow:
    """Incident analysis and response workflow."""

    @staticmethod
    async def analyze_incident(
        incident: dict[str, Any],
        related_events: list[dict[str, Any]],
        process_fn,
    ) -> str:
        context = {
            "incident": incident,
            "related_events": related_events[:20],  # cap to avoid token overflow
        }
        user_msg = (
            f"Analyze this security incident and provide response guidance:\n"
            f"Title: {incident.get('title', 'Unknown')}\n"
            f"Severity: {incident.get('severity', 'unknown').upper()}\n"
            f"Status: {incident.get('status', 'unknown')}\n"
            f"Description: {incident.get('description', 'No description provided.')}\n"
            f"Related events: {len(related_events)}"
        )
        request = CopilotRequest(
            operation=CopilotOperation.INCIDENT_ANALYZE,
            user_message=user_msg,
            context=context,
        )
        response = await process_fn(request)
        log.info(
            "workflow.incident.analyzed",
            incident_id=incident.get("id"),
            severity=incident.get("severity"),
        )
        return response.content


class DeviceRecommendationWorkflow:
    """Device-specific security recommendation workflow."""

    @staticmethod
    async def recommend_for_device(
        device: dict[str, Any],
        compliance_scores: list[dict[str, Any]],
        drift_events: list[dict[str, Any]],
        fleet_context: dict[str, Any],
        process_fn,
    ) -> str:
        context = {
            "device": device,
            "compliance_scores": compliance_scores,
            "drift_events": drift_events[:10],
            "fleet": fleet_context,
        }
        score_lines = "\n".join(
            f"  - {s.get('framework', 'unknown').upper()}: {s.get('overall_score', 0):.1f}%"
            for s in compliance_scores
        )
        user_msg = (
            f"Provide security recommendations for this device:\n"
            f"Device: {device.get('hostname', device.get('device_id', 'unknown'))}\n"
            f"Type: {device.get('device_type', 'unknown')}\n"
            f"Status: {device.get('monitoring_state', 'unknown')}\n"
            f"Compliance scores:\n{score_lines}\n"
            f"Active drift events: {len(drift_events)}\n"
            f"Fleet average score: {fleet_context.get('average_compliance_score', 0):.1f}%"
        )
        request = CopilotRequest(
            operation=CopilotOperation.DEVICE_RECOMMEND,
            user_message=user_msg,
            context=context,
        )
        response = await process_fn(request)
        log.info(
            "workflow.device_recommend.completed",
            device_id=device.get("device_id"),
        )
        return response.content
