"""
Security Copilot Orchestration — main service coordinating all components.
Thin orchestrator layer that composes providers, analyzers, workflows, and remediation.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

import structlog

from app.core.config import settings
from app.core.metrics import (
    AI_REQUESTS_TOTAL,
    AI_REQUEST_DURATION,
    AI_TOKEN_USAGE,
    AI_PROVIDER_FALLBACKS,
)
from app.domain.ai.providers.analyzers import (
    ACLAnalyzer,
    SecurityConfigAnalyzer,
    ThreatAnalyzer,
)
from app.domain.ai.providers.cache import AIResponseCache
from app.domain.ai.providers.llm_providers import LLMProviderRegistry
from app.domain.ai.providers.models import (
    AIProvider,
    CopilotOperation,
    CopilotRequest,
    LLMResponse,
    RemediationRecommendation,
)
from app.domain.ai.providers.prompt_manager import PromptManager
from app.domain.ai.providers.remediation_engine import RemediationEngine
from app.domain.ai.providers.workflows import (
    AttackPathWorkflow,
    ChatWorkflow,
    ComplianceWorkflow,
    CVEWorkflow,
    ConfigAnalysisWorkflow,
    RiskPrioritizationWorkflow,
)

log = structlog.get_logger(__name__)


class SecurityCopilotOrchestrator:
    """
    Enterprise AI Security Copilot.
    Orchestrates prompt construction, provider selection, fallback, caching,
    and security-specific intelligence operations.
    """

    def __init__(
        self,
        registry: LLMProviderRegistry,
        cache: AIResponseCache | None = None,
    ) -> None:
        self._registry = registry
        self._cache = cache
        self._primary = AIProvider(settings.ai.DEFAULT_PROVIDER)
        self._fallback = AIProvider(settings.ai.FALLBACK_PROVIDER) if settings.ai.FALLBACK_PROVIDER else None

        # Initialize specialized components
        self._remediation_engine = RemediationEngine(registry)
        self._acl_analyzer = ACLAnalyzer()
        self._config_analyzer = SecurityConfigAnalyzer()
        self._threat_analyzer = ThreatAnalyzer()

    async def process(self, request: CopilotRequest) -> LLMResponse:
        """Process a copilot request with provider fallback and caching."""
        messages = PromptManager.build_messages(request)

        # Cache check (skip for streaming and chat)
        if self._cache and request.operation != CopilotOperation.CHAT:
            cached = await self._cache.get(request.operation, messages)
            if cached:
                AI_REQUESTS_TOTAL.labels(
                    provider="cache",
                    operation_type=request.operation.value,
                    status="hit",
                ).inc()
                return LLMResponse(
                    content=cached,
                    provider=self._primary,
                    model="cache",
                    cached=True,
                )

        # Attempt primary provider
        response = await self._attempt_provider(self._primary, request, messages)

        if response is None and self._fallback:
            # Fallback to secondary provider
            log.warning("orchestration.provider.fallback", primary=self._primary.value, fallback=self._fallback.value)
            AI_PROVIDER_FALLBACKS.labels(
                primary_provider=self._primary.value,
                fallback_provider=self._fallback.value,
            ).inc()
            response = await self._attempt_provider(self._fallback, request, messages)

        if response is None:
            raise RuntimeError("All AI providers failed. Please check provider configuration.")

        # Record metrics
        AI_REQUESTS_TOTAL.labels(
            provider=response.provider.value,
            operation_type=request.operation.value,
            status="success",
        ).inc()
        AI_REQUEST_DURATION.labels(
            provider=response.provider.value,
            operation_type=request.operation.value,
        ).observe(response.latency_ms / 1000)
        AI_TOKEN_USAGE.labels(provider=response.provider.value, token_type="prompt").inc(response.prompt_tokens)
        AI_TOKEN_USAGE.labels(provider=response.provider.value, token_type="completion").inc(response.completion_tokens)

        # Cache successful response
        if self._cache and request.operation != CopilotOperation.CHAT:
            await self._cache.set(request.operation, messages, response.content)

        return response

    async def _attempt_provider(
        self,
        provider_type: AIProvider,
        request: CopilotRequest,
        messages,  # list[LLMMessage]
    ) -> LLMResponse | None:
        """Attempt to get response from provider with retries."""
        for attempt in range(settings.ai.MAX_RETRIES):
            try:
                provider = self._registry.get(provider_type)
                return await asyncio.wait_for(
                    provider.complete(
                        messages=messages,
                        max_tokens=settings.ai.OPENAI_MAX_TOKENS,
                        temperature=settings.ai.TEMPERATURE,
                    ),
                    timeout=settings.ai.REQUEST_TIMEOUT,
                )
            except asyncio.TimeoutError:
                log.warning("orchestration.provider.timeout", provider=provider_type.value, attempt=attempt + 1)
            except Exception as exc:
                log.error("orchestration.provider.error", provider=provider_type.value, attempt=attempt + 1, error=str(exc))
                if attempt < settings.ai.MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
        return None

    async def stream_response(self, request: CopilotRequest) -> AsyncGenerator[str, None]:
        """Stream tokens for real-time UI updates."""
        messages = PromptManager.build_messages(request)
        provider = self._registry.get(self._primary)
        try:
            async for token in provider.stream(
                messages=messages,
                max_tokens=settings.ai.OPENAI_MAX_TOKENS,
                temperature=settings.ai.TEMPERATURE,
            ):
                yield token
        except Exception:
            if self._fallback:
                provider = self._registry.get(self._fallback)
                async for token in provider.stream(messages=messages):
                    yield token

    # ── Workflow Delegation ────────────────────────────────────────────────────

    async def explain_compliance_failure(
        self,
        rule_id: str,
        rule_name: str,
        findings: list[str],
        device_metadata: dict[str, Any],
        framework: str,
    ) -> str:
        """Explain a compliance failure with business impact."""
        return await ComplianceWorkflow.explain_failure(
            rule_id=rule_id,
            rule_name=rule_name,
            findings=findings,
            device_metadata=device_metadata,
            framework=framework,
            process_fn=self.process,
        )

    async def recommend_remediation(
        self,
        findings: list[dict[str, Any]],
        device_metadata: dict[str, Any],
    ) -> list[RemediationRecommendation]:
        """Generate remediation recommendations."""
        return await self._remediation_engine.generate_recommendations(
            findings=findings,
            device_metadata=device_metadata,
            process_fn=self.process,
        )

    async def analyze_acl(self, acl_config: str, device_metadata: dict[str, Any]) -> str:
        """Analyze ACL configuration."""
        return await self._acl_analyzer.analyze(
            acl_config=acl_config,
            device_metadata=device_metadata,
            process_fn=self.process,
        )

    async def explain_cve(self, cve_id: str, affected_devices: list[dict[str, Any]]) -> str:
        """Explain a CVE."""
        return await CVEWorkflow.explain_cve(
            cve_id=cve_id,
            affected_devices=affected_devices,
            process_fn=self.process,
        )

    async def analyze_attack_path(
        self,
        network_topology: dict[str, Any],
        compliance_findings: list[dict[str, Any]],
    ) -> str:
        """Analyze attack paths."""
        return await AttackPathWorkflow.analyze_paths(
            network_topology=network_topology,
            compliance_findings=compliance_findings,
            process_fn=self.process,
        )

    async def analyze_config(self, device_config: str, device_metadata: dict[str, Any]) -> str:
        """Analyze device configuration."""
        return await ConfigAnalysisWorkflow.analyze_config(
            device_config=device_config,
            device_metadata=device_metadata,
            process_fn=self.process,
        )

    async def prioritize_risks(
        self,
        findings: list[dict[str, Any]],
        asset_metadata: dict[str, Any],
    ) -> str:
        """Prioritize security findings by risk."""
        return await RiskPrioritizationWorkflow.prioritize_risks(
            findings=findings,
            asset_metadata=asset_metadata,
            process_fn=self.process,
        )

    async def chat(
        self,
        user_message: str,
        session_id: str,
        history,  # list[LLMMessage]
        context: dict[str, Any] | None = None,
    ) -> str:
        """Chat with the security copilot."""
        return await ChatWorkflow.chat(
            user_message=user_message,
            session_id=session_id,
            history=history,
            context=context,
            process_fn=self.process,
        )

    # ── Provider Health ────────────────────────────────────────────────────────

    async def get_provider_health(self) -> dict[str, bool]:
        """Get health status of all LLM providers."""
        return await self._registry.health_status()
