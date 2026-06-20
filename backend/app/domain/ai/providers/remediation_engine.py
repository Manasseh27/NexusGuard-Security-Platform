"""
Remediation engine — handles remediation operations and recommendation parsing.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import structlog

from app.domain.ai.providers.models import (
    CopilotOperation,
    CopilotRequest,
    RemediationRecommendation,
)
from app.domain.ai.providers.llm_providers import LLMProviderRegistry

log = structlog.get_logger(__name__)


class RemediationEngine:
    """Orchestrates remediation-specific operations."""

    def __init__(self, registry: LLMProviderRegistry) -> None:
        self._registry = registry

    async def generate_recommendations(
        self,
        findings: list[dict[str, Any]],
        device_metadata: dict[str, Any],
        process_fn,  # Injected process function from orchestration layer
    ) -> list[RemediationRecommendation]:
        """Generate structured remediation recommendations for findings."""
        context = {"device": device_metadata, "findings": findings}
        findings_text = "\n".join(
            f"[{f.get('severity', 'UNKNOWN')}] {f.get('rule_name')}: {', '.join(f.get('findings', []))}"
            for f in findings
        )
        user_msg = (
            f"Provide prioritized remediation recommendations for these findings on a "
            f"{device_metadata.get('platform', 'Cisco IOS')} device:\n{findings_text}\n\n"
            "For each finding, provide:\n1. Risk explanation\n2. Business impact\n"
            "3. Step-by-step remediation\n4. Exact CLI commands\n5. Verification commands\n6. Effort estimate"
        )
        request = CopilotRequest(
            operation=CopilotOperation.REMEDIATION_RECOMMEND,
            user_message=user_msg,
            context=context,
        )
        response = await process_fn(request)
        return self._parse_remediation_response(response.content, findings)

    def _parse_remediation_response(
        self,
        content: str,
        findings: list[dict[str, Any]],
    ) -> list[RemediationRecommendation]:
        """Parse LLM response into structured RemediationRecommendation objects."""
        recommendations = []
        for i, finding in enumerate(findings):
            rec = RemediationRecommendation(
                finding_id=finding.get("finding_id", str(uuid4())),
                rule_id=finding.get("rule_id", ""),
                severity=finding.get("severity", "medium"),
                title=f"Remediate {finding.get('rule_name', 'finding')}",
                risk_explanation=content,
                business_impact="See AI analysis above",
                remediation_steps=[],
                cli_commands=[],
                verification_steps=[],
                estimated_effort="30 minutes",
                priority_score=float(i + 1),
            )
            recommendations.append(rec)
        return recommendations

    def parse_cli_commands_from_response(self, response_text: str) -> list[str]:
        """Extract CLI commands from LLM response."""
        # Simple extraction: look for code blocks or specific patterns
        commands = []
        lines = response_text.split("\n")
        in_code_block = False

        for line in lines:
            if "```" in line or line.startswith("config t"):
                in_code_block = not in_code_block
                continue

            if in_code_block and line.strip() and not line.startswith("#"):
                commands.append(line.strip())

        return commands

    def parse_verification_steps(self, response_text: str) -> list[str]:
        """Extract verification steps from LLM response."""
        verification_keywords = ["verify", "check", "confirm", "show"]
        steps = []

        for line in response_text.split("\n"):
            if any(kw in line.lower() for kw in verification_keywords):
                steps.append(line.strip())

        return steps
