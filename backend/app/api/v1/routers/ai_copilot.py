"""
AI Security Copilot API Router
Endpoints: chat, compliance explanation, remediation, ACL analysis,
           CVE explanation, attack path, risk prioritization, streaming.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.security import get_current_user, require_permission
from app.domain.ai.providers.copilot_service import (
    CopilotOperation,
    CopilotRequest,
    LLMMessage,
    SecurityCopilotService,
)

log = structlog.get_logger(__name__)
router = APIRouter()


# ── Dependency provider ────────────────────────────────────────────────────────

def _get_copilot() -> SecurityCopilotService:
    from app.core.dependencies import get_copilot_service
    return get_copilot_service()


# ── Request / Response models ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=32_000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8_000)
    session_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)
    context: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


class ComplianceExplainRequest(BaseModel):
    rule_id: str
    rule_name: str
    findings: list[str] = Field(..., min_length=1)
    device_metadata: dict[str, Any] = Field(default_factory=dict)
    framework: str = "cis"


class RemediationRequest(BaseModel):
    device_id: UUID
    findings: list[dict[str, Any]] = Field(..., min_length=1, max_length=50)
    device_metadata: dict[str, Any] = Field(default_factory=dict)


class ACLAnalyzeRequest(BaseModel):
    acl_config: str = Field(..., min_length=1, max_length=50_000)
    device_metadata: dict[str, Any] = Field(default_factory=dict)


class CVERequest(BaseModel):
    cve_id: str = Field(..., pattern=r"^CVE-\d{4}-\d{4,}$")
    affected_devices: list[dict[str, Any]] = Field(default_factory=list)


class AttackPathRequest(BaseModel):
    network_topology: dict[str, Any]
    compliance_findings: list[dict[str, Any]] = Field(default_factory=list)


class RiskPrioritizeRequest(BaseModel):
    findings: list[dict[str, Any]] = Field(..., min_length=1, max_length=200)
    device_metadata: dict[str, Any] = Field(default_factory=dict)
    regulatory_requirements: list[str] = Field(default_factory=list)


class CopilotResponse(BaseModel):
    content: str
    provider: str
    model: str
    operation: str
    tokens_used: int
    latency_ms: int
    cached: bool
    session_id: str | None = None
    generated_at: str


# ── Chat endpoint (with optional streaming) ────────────────────────────────────

@router.post(
    "/chat",
    summary="Conversational AI security assistant",
    response_model=CopilotResponse,
)
async def chat(
    request: ChatRequest,
    current_user=Depends(require_permission("ai:chat")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> Any:
    import uuid
    session_id = request.session_id or str(uuid.uuid4())

    history = [LLMMessage(role=m.role, content=m.content) for m in request.history]

    if request.stream:
        return StreamingResponse(
            _stream_chat(copilot, request.message, session_id, history, request.context),
            media_type="text/event-stream",
            headers={
                "Cache-Control":    "no-cache",
                "X-Accel-Buffering":"no",
                "Connection":       "keep-alive",
            },
        )

    copilot_req = CopilotRequest(
        operation=CopilotOperation.CHAT,
        user_message=request.message,
        session_id=session_id,
        conversation_history=history,
        context=request.context,
        user_id=str(current_user.id),
    )

    response = await copilot.process(copilot_req)

    log.info(
        "ai.chat.completed",
        session_id=session_id,
        user=current_user.username,
        provider=response.provider.value,
        tokens=response.total_tokens,
    )

    return CopilotResponse(
        content=response.content,
        provider=response.provider.value,
        model=response.model,
        operation=CopilotOperation.CHAT.value,
        tokens_used=response.total_tokens,
        latency_ms=response.latency_ms,
        cached=response.cached,
        session_id=session_id,
        generated_at=datetime.utcnow().isoformat(),
    )


async def _stream_chat(
    copilot: SecurityCopilotService,
    message: str,
    session_id: str,
    history: list[LLMMessage],
    context: dict[str, Any],
):
    """SSE stream generator for real-time chat tokens."""
    from app.domain.ai.providers.copilot_service import CopilotRequest, CopilotOperation

    req = CopilotRequest(
        operation=CopilotOperation.CHAT,
        user_message=message,
        session_id=session_id,
        conversation_history=history,
        context=context,
        stream=True,
    )
    try:
        async for token in copilot.stream_response(req):
            data = json.dumps({"token": token, "session_id": session_id})
            yield f"data: {data}\n\n"
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"
    except Exception as exc:
        log.error("ai.stream.error", error=str(exc))
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"


# ── Compliance explanation ─────────────────────────────────────────────────────

@router.post(
    "/explain/compliance",
    summary="AI explanation of a compliance failure",
    response_model=CopilotResponse,
)
async def explain_compliance(
    request: ComplianceExplainRequest,
    current_user=Depends(require_permission("ai:explain")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    explanation = await copilot.explain_compliance_failure(
        rule_id=request.rule_id,
        rule_name=request.rule_name,
        findings=request.findings,
        device_metadata=request.device_metadata,
        framework=request.framework,
    )
    return CopilotResponse(
        content=explanation,
        provider="ai",
        model="",
        operation=CopilotOperation.COMPLIANCE_EXPLAIN.value,
        tokens_used=0,
        latency_ms=0,
        cached=False,
        generated_at=datetime.utcnow().isoformat(),
    )


# ── Remediation recommendations ────────────────────────────────────────────────

@router.post(
    "/remediation",
    summary="AI-powered remediation recommendations",
)
async def get_remediation(
    request: RemediationRequest,
    current_user=Depends(require_permission("ai:remediation")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> dict[str, Any]:
    recommendations = await copilot.recommend_remediation(
        findings=request.findings,
        device_metadata=request.device_metadata,
    )
    return {
        "device_id": str(request.device_id),
        "total_findings": len(request.findings),
        "recommendations": [
            {
                "finding_id":       rec.finding_id,
                "rule_id":          rec.rule_id,
                "severity":         rec.severity,
                "title":            rec.title,
                "risk_explanation": rec.risk_explanation,
                "business_impact":  rec.business_impact,
                "remediation_steps":rec.remediation_steps,
                "cli_commands":     rec.cli_commands,
                "verification_steps":rec.verification_steps,
                "estimated_effort": rec.estimated_effort,
                "priority_score":   rec.priority_score,
            }
            for rec in recommendations
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }


# ── ACL analysis ───────────────────────────────────────────────────────────────

@router.post(
    "/analyze/acl",
    summary="AI-powered ACL security analysis",
    response_model=CopilotResponse,
)
async def analyze_acl(
    request: ACLAnalyzeRequest,
    current_user=Depends(require_permission("ai:analyze")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    analysis = await copilot.analyze_acl(
        acl_config=request.acl_config,
        device_metadata=request.device_metadata,
    )
    return CopilotResponse(
        content=analysis,
        provider="ai",
        model="",
        operation=CopilotOperation.ACL_ANALYZE.value,
        tokens_used=0,
        latency_ms=0,
        cached=False,
        generated_at=datetime.utcnow().isoformat(),
    )


# ── CVE explanation ────────────────────────────────────────────────────────────

@router.post(
    "/explain/cve",
    summary="AI explanation of a CVE and its network impact",
    response_model=CopilotResponse,
)
async def explain_cve(
    request: CVERequest,
    current_user=Depends(require_permission("ai:explain")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    explanation = await copilot.explain_cve(
        cve_id=request.cve_id,
        affected_devices=request.affected_devices,
    )
    return CopilotResponse(
        content=explanation,
        provider="ai",
        model="",
        operation=CopilotOperation.CVE_EXPLAIN.value,
        tokens_used=0,
        latency_ms=0,
        cached=False,
        generated_at=datetime.utcnow().isoformat(),
    )


# ── Attack path analysis ───────────────────────────────────────────────────────

@router.post(
    "/analyze/attack-path",
    summary="AI-powered attack path analysis based on topology and findings",
    response_model=CopilotResponse,
)
async def analyze_attack_path(
    request: AttackPathRequest,
    current_user=Depends(require_permission("ai:analyze")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    analysis = await copilot.analyze_attack_path(
        network_topology=request.network_topology,
        compliance_findings=request.compliance_findings,
    )
    return CopilotResponse(
        content=analysis,
        provider="ai",
        model="",
        operation=CopilotOperation.ATTACK_PATH.value,
        tokens_used=0,
        latency_ms=0,
        cached=False,
        generated_at=datetime.utcnow().isoformat(),
    )


# ── Risk prioritization ────────────────────────────────────────────────────────

@router.post(
    "/prioritize/risk",
    summary="AI-powered risk prioritization and remediation roadmap",
    response_model=CopilotResponse,
)
async def prioritize_risk(
    request: RiskPrioritizeRequest,
    current_user=Depends(require_permission("ai:analyze")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    context = {
        "findings": request.findings,
        "device": request.device_metadata,
        "regulatory_requirements": request.regulatory_requirements,
    }
    copilot_req = CopilotRequest(
        operation=CopilotOperation.RISK_PRIORITIZE,
        user_message=(
            f"Prioritize these {len(request.findings)} security findings by risk. "
            f"Regulatory requirements: {', '.join(request.regulatory_requirements) or 'None specified'}. "
            "Produce a ranked remediation roadmap with effort estimates."
        ),
        context=context,
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return CopilotResponse(
        content=response.content,
        provider=response.provider.value,
        model=response.model,
        operation=CopilotOperation.RISK_PRIORITIZE.value,
        tokens_used=response.total_tokens,
        latency_ms=response.latency_ms,
        cached=response.cached,
        generated_at=datetime.utcnow().isoformat(),
    )


# ── Security summary ───────────────────────────────────────────────────────────

@router.get(
    "/summary/security",
    summary="AI-generated executive security summary",
    response_model=CopilotResponse,
)
async def security_summary(
    hours: int = Query(default=24, ge=1, le=168),
    current_user=Depends(require_permission("ai:summarize")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    from app.core.dependencies import get_compliance_monitor
    monitor = get_compliance_monitor()
    fleet = monitor.get_fleet_summary()

    context = {
        "fleet_summary": fleet,
        "time_range_hours": hours,
        "generated_at": datetime.utcnow().isoformat(),
    }
    copilot_req = CopilotRequest(
        operation=CopilotOperation.SECURITY_SUMMARIZE,
        user_message=(
            f"Generate an executive security summary for the last {hours} hours. "
            f"Fleet has {fleet.get('total_devices', 0)} devices with "
            f"{fleet.get('average_compliance_score', 0):.1f}% average compliance. "
            f"{fleet.get('active_drift_events', 0)} active drift events detected."
        ),
        context=context,
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return CopilotResponse(
        content=response.content,
        provider=response.provider.value,
        model=response.model,
        operation=CopilotOperation.SECURITY_SUMMARIZE.value,
        tokens_used=response.total_tokens,
        latency_ms=response.latency_ms,
        cached=response.cached,
        generated_at=datetime.utcnow().isoformat(),
    )


# ── Provider health ────────────────────────────────────────────────────────────

@router.get(
    "/providers/health",
    summary="Check health of all configured AI providers",
)
async def providers_health(
    current_user=Depends(require_permission("ai:admin")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> dict[str, Any]:
    status_map = await copilot._registry.health_status()
    return {
        "providers": status_map,
        "primary":  copilot._primary.value,
        "fallback": copilot._fallback.value if copilot._fallback else None,
        "checked_at": datetime.utcnow().isoformat(),
    }
