"""
AI Security Copilot — Modular architecture.

Exports all public APIs from the refactored modules.
All existing code using this package will continue to work unchanged.
"""

from app.domain.ai.providers.copilot_service import (
    AIProvider,
    CopilotOperation,
    CopilotRequest,
    LLMMessage,
    LLMResponse,
    RemediationRecommendation,
    LLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    LLMProviderRegistry,
    SecurityCopilotService,
    SecurityCopilotOrchestrator,
    AIResponseCache,
    PromptManager,
    RemediationEngine,
    ComplianceWorkflow,
    CVEWorkflow,
    ChatWorkflow,
    AttackPathWorkflow,
    ConfigAnalysisWorkflow,
    RiskPrioritizationWorkflow,
    ACLAnalyzer,
    SecurityConfigAnalyzer,
    ThreatAnalyzer,
    SYSTEM_PROMPTS,
)

__all__ = [
    "AIProvider",
    "CopilotOperation",
    "CopilotRequest",
    "LLMMessage",
    "LLMResponse",
    "RemediationRecommendation",
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "LLMProviderRegistry",
    "SecurityCopilotService",
    "SecurityCopilotOrchestrator",
    "AIResponseCache",
    "PromptManager",
    "RemediationEngine",
    "ComplianceWorkflow",
    "CVEWorkflow",
    "ChatWorkflow",
    "AttackPathWorkflow",
    "ConfigAnalysisWorkflow",
    "RiskPrioritizationWorkflow",
    "ACLAnalyzer",
    "SecurityConfigAnalyzer",
    "ThreatAnalyzer",
    "SYSTEM_PROMPTS",
]
