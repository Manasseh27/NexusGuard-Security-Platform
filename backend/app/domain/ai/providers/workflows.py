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
    """Compliance explanation workflow."""

    @staticmethod
    async def explain_failure(
        rule_id: str,
        rule_name: str,
        findings: list[str],
        device_metadata: dict[str, Any],
        framework: str,
        process_fn,  # Injected process function
    ) -> str:
        """Explain a compliance failure with business context."""
        context = {
            "rule_id": rule_id,
            "rule_name": rule_name,
            "framework": framework,
            "findings": findings,
            "device": device_metadata,
        }
        user_msg = (
            f"Explain this compliance failure for a {device_metadata.get('device_type', 'network device')}:\n"
            f"Rule: {rule_name} ({rule_id})\n"
            f"Framework: {framework}\n"
            f"Findings: {chr(10).join(f'- {f}' for f in findings)}"
        )
        request = CopilotRequest(
            operation=CopilotOperation.COMPLIANCE_EXPLAIN,
            user_message=user_msg,
            context=context,
        )
        response = await process_fn(request)
        log.info(
            "workflow.compliance.explained",
            rule_id=rule_id,
            framework=framework,
        )
        return response.content


class CVEWorkflow:
    """CVE analysis workflow."""

    @staticmethod
    async def explain_cve(
        cve_id: str,
        affected_devices: list[dict[str, Any]],
        process_fn,  # Injected process function
    ) -> str:
        """Explain a CVE and its impact on infrastructure."""
        request = CopilotRequest(
            operation=CopilotOperation.CVE_EXPLAIN,
            user_message=f"Explain {cve_id} and its impact on our network infrastructure.",
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
        process_fn=None,  # Injected process function
    ) -> str:
        """Chat with the security copilot."""
        request = CopilotRequest(
            operation=CopilotOperation.CHAT,
            user_message=user_message,
            session_id=session_id,
            conversation_history=history,
            context=context or {},
        )
        response = await process_fn(request)
        log.debug(
            "workflow.chat.completed",
            session_id=session_id,
            tokens=response.total_tokens,
        )
        return response.content


class AttackPathWorkflow:
    """Attack path analysis workflow."""

    @staticmethod
    async def analyze_paths(
        network_topology: dict[str, Any],
        compliance_findings: list[dict[str, Any]],
        process_fn,  # Injected process function
    ) -> str:
        """Analyze potential attack paths based on topology and findings."""
        request = CopilotRequest(
            operation=CopilotOperation.ATTACK_PATH,
            user_message="Analyze potential attack paths through our network based on current compliance findings.",
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
        process_fn,  # Injected process function
    ) -> str:
        """Analyze device configuration against security benchmarks."""
        request = CopilotRequest(
            operation=CopilotOperation.CONFIG_ANALYZE,
            user_message=f"Analyze this device configuration for security issues:\n```\n{device_config}\n```",
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
        process_fn,  # Injected process function
    ) -> str:
        """Prioritize security findings by risk score."""
        request = CopilotRequest(
            operation=CopilotOperation.RISK_PRIORITIZE,
            user_message="Prioritize these security findings by risk and remediation effort.",
            context={"findings": findings, "assets": asset_metadata},
        )
        response = await process_fn(request)
        log.info("workflow.risk_prioritization.completed")
        return response.content
