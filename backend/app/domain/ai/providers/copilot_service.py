"""
Enterprise AI Security Copilot — Refactored as Modular Architecture.

This module re-exports all components for 100% backward compatibility.
The implementation has been decomposed into focused, testable modules:

- models.py: Data structures and enumerations
- llm_providers.py: LLM provider abstractions (OpenAI, Anthropic, Ollama, etc.)
- prompt_manager.py: Prompt construction and system prompts
- workflows.py: High-level security operations (compliance, CVE, chat, etc.)
- analyzers.py: Specialized analysis (ACLs, configs, threats)
- remediation_engine.py: Remediation-specific logic and parsing
- cache.py: Redis-backed response caching
- orchestration.py: Main service coordinating all components

All existing imports and APIs continue to work unchanged.
"""

from __future__ import annotations

# Re-export all public APIs for backward compatibility
from app.domain.ai.providers.models import (
    AIProvider,
    CopilotOperation,
    CopilotRequest,
    LLMMessage,
    LLMResponse,
    RemediationRecommendation,
)
from app.domain.ai.providers.llm_providers import (
    LLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    LLMProviderRegistry,
)
from app.domain.ai.providers.cache import AIResponseCache
from app.domain.ai.providers.orchestration import SecurityCopilotOrchestrator
from app.domain.ai.providers.prompt_manager import PromptManager, SYSTEM_PROMPTS
from app.domain.ai.providers.workflows import (
    ComplianceWorkflow,
    CVEWorkflow,
    ChatWorkflow,
    AttackPathWorkflow,
    ConfigAnalysisWorkflow,
    RiskPrioritizationWorkflow,
)
from app.domain.ai.providers.analyzers import (
    ACLAnalyzer,
    SecurityConfigAnalyzer,
    ThreatAnalyzer,
)
from app.domain.ai.providers.remediation_engine import RemediationEngine

# Main service alias for backward compatibility
SecurityCopilotService = SecurityCopilotOrchestrator

__all__ = [
    # Enumerations
    "AIProvider",
    "CopilotOperation",
    # Data Models
    "CopilotRequest",
    "LLMMessage",
    "LLMResponse",
    "RemediationRecommendation",
    # Providers
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "LLMProviderRegistry",
    # Services
    "SecurityCopilotService",
    "SecurityCopilotOrchestrator",
    "AIResponseCache",
    "PromptManager",
    "RemediationEngine",
    # Workflows
    "ComplianceWorkflow",
    "CVEWorkflow",
    "ChatWorkflow",
    "AttackPathWorkflow",
    "ConfigAnalysisWorkflow",
    "RiskPrioritizationWorkflow",
    # Analyzers
    "ACLAnalyzer",
    "SecurityConfigAnalyzer",
    "ThreatAnalyzer",
    # System Prompts
    "SYSTEM_PROMPTS",
]
