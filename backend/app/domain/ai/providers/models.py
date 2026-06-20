"""
Data models and enumerations for the AI Security Copilot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class AIProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    AZURE = "azure"


class CopilotOperation(str, Enum):
    """Types of copilot operations."""

    COMPLIANCE_EXPLAIN = "compliance_explain"
    REMEDIATION_RECOMMEND = "remediation_recommend"
    ACL_ANALYZE = "acl_analyze"
    CVE_EXPLAIN = "cve_explain"
    ATTACK_PATH = "attack_path"
    CONFIG_ANALYZE = "config_analyze"
    RISK_PRIORITIZE = "risk_prioritize"
    SECURITY_SUMMARIZE = "security_summarize"
    CHAT = "chat"
    RAG_QUERY = "rag_query"


@dataclass
class LLMMessage:
    """Message in LLM conversation."""

    role: str  # system | user | assistant
    content: str


@dataclass
class LLMResponse:
    """Response from LLM provider."""

    content: str
    provider: AIProvider
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    cached: bool = False
    request_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class CopilotRequest:
    """Request to the security copilot."""

    operation: CopilotOperation
    user_message: str
    context: dict[str, Any] = field(default_factory=dict)
    conversation_history: list[LLMMessage] = field(default_factory=list)
    session_id: str | None = None
    user_id: str | None = None
    stream: bool = False


@dataclass
class RemediationRecommendation:
    """Structured remediation recommendation."""

    finding_id: str
    rule_id: str
    severity: str
    title: str
    risk_explanation: str
    business_impact: str
    remediation_steps: list[str]
    cli_commands: list[str]
    verification_steps: list[str]
    estimated_effort: str  # "5 minutes" | "1 hour" | "4 hours" | "1 day"
    priority_score: float  # 0.0–10.0
