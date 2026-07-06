"""
AI Security Copilot API Router
Endpoints: chat (streaming + non-streaming), compliance explanation,
compliance recommendations, incident analysis, device recommendations,
remediation, ACL analysis, CVE explanation, attack path, risk prioritization,
security summary, provider health, session history.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.security import get_current_user, require_permission
from app.domain.ai.providers.copilot_service import (
    CopilotOperation,
    CopilotRequest,
    LLMMessage,
    LLMResponse,
    SecurityCopilotService,
)

log = structlog.get_logger(__name__)
router = APIRouter()

# Max conversation turns kept in Redis per session
_MAX_HISTORY_TURNS = 20
# TTL for session memory in Redis (2 hours)
_SESSION_TTL = 7200


# ── Dependency provider ────────────────────────────────────────────────────────

def _get_copilot() -> SecurityCopilotService:
    from app.core.dependencies import get_copilot_service
    return get_copilot_service()


def _get_redis():
    from app.infrastructure.cache.redis_client import get_redis
    return get_redis()


# ── Session memory helpers ─────────────────────────────────────────────────────

async def _load_session_history(redis, session_id: str) -> list[LLMMessage]:
    """Load conversation history from Redis for a session."""
    if not redis or not session_id:
        return []
    try:
        raw = await redis.get(f"ai:session:{session_id}:history")
        if raw:
            turns = json.loads(raw)
            return [LLMMessage(role=t["role"], content=t["content"]) for t in turns]
    except Exception as exc:
        log.warning("session.load_failed", session_id=session_id, error=str(exc))
    return []


async def _save_session_history(
    redis,
    session_id: str,
    history: list[LLMMessage],
    user_message: str,
    assistant_reply: str,
) -> None:
    """Append the new turn and persist to Redis."""
    if not redis or not session_id:
        return
    try:
        turns = [{"role": m.role, "content": m.content} for m in history]
        turns.append({"role": "user", "content": user_message})
        turns.append({"role": "assistant", "content": assistant_reply})
        # Keep only the last N turns to avoid token overflow
        turns = turns[-(_MAX_HISTORY_TURNS * 2):]
        await redis.setex(
            f"ai:session:{session_id}:history",
            _SESSION_TTL,
            json.dumps(turns),
        )
    except Exception as exc:
        log.warning("session.save_failed", session_id=session_id, error=str(exc))


# ── Request / Response models ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=32_000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8_000)
    session_id: str | None = None
    # history is optional — if omitted, server loads from Redis session
    history: list[ChatMessage] = Field(default_factory=list, max_length=50)
    context: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False


class ComplianceExplainRequest(BaseModel):
    rule_id: str
    rule_name: str
    findings: list[str] = Field(..., min_length=1)
    device_metadata: dict[str, Any] = Field(default_factory=dict)
    framework: str = "cis"


class ComplianceRecommendRequest(BaseModel):
    framework_scores: list[dict[str, Any]] = Field(..., min_length=1)
    fleet_context: dict[str, Any] = Field(default_factory=dict)


class IncidentAnalyzeRequest(BaseModel):
    incident: dict[str, Any]
    related_events: list[dict[str, Any]] = Field(default_factory=list, max_length=50)


class DeviceRecommendRequest(BaseModel):
    device: dict[str, Any]
    compliance_scores: list[dict[str, Any]] = Field(default_factory=list)
    drift_events: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    fleet_context: dict[str, Any] = Field(default_factory=dict)


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


def _to_response(resp: LLMResponse, operation: CopilotOperation, session_id: str | None = None) -> CopilotResponse:
    return CopilotResponse(
        content=resp.content,
        provider=resp.provider.value,
        model=resp.model,
        operation=operation.value,
        tokens_used=resp.total_tokens,
        latency_ms=resp.latency_ms,
        cached=resp.cached,
        session_id=session_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


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
    session_id = request.session_id or str(uuid4())
    redis = _get_redis()

    # Load history from Redis if client didn't send it
    if request.history:
        history = [LLMMessage(role=m.role, content=m.content) for m in request.history]
    else:
        history = await _load_session_history(redis, session_id)

    if request.stream:
        return StreamingResponse(
            _stream_chat(copilot, request.message, session_id, history, request.context, redis),
            media_type="text/event-stream",
            headers={
                "Cache-Control":     "no-cache",
                "X-Accel-Buffering": "no",
                "Connection":        "keep-alive",
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

    await _save_session_history(redis, session_id, history, request.message, response.content)

    log.info(
        "ai.chat.completed",
        session_id=session_id,
        user=current_user.username,
        provider=response.provider.value,
        tokens=response.total_tokens,
    )

    return _to_response(response, CopilotOperation.CHAT, session_id)


async def _stream_chat(
    copilot: SecurityCopilotService,
    message: str,
    session_id: str,
    history: list[LLMMessage],
    context: dict[str, Any],
    redis,
):
    """SSE stream generator — yields tokens then saves history."""
    req = CopilotRequest(
        operation=CopilotOperation.CHAT,
        user_message=message,
        session_id=session_id,
        conversation_history=history,
        context=context,
        stream=True,
    )
    full_reply: list[str] = []
    try:
        async for token in copilot.stream_response(req):
            full_reply.append(token)
            data = json.dumps({"token": token, "session_id": session_id})
            yield f"data: {data}\n\n"

        # Persist completed turn to session memory
        await _save_session_history(redis, session_id, history, message, "".join(full_reply))
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"
    except Exception as exc:
        log.error("ai.stream.error", error=str(exc))
        yield f"data: {json.dumps({'error': str(exc)})}\n\n"


# ── Session history ────────────────────────────────────────────────────────────

@router.get(
    "/sessions/{session_id}/history",
    summary="Retrieve conversation history for a session",
)
async def get_session_history(
    session_id: str,
    current_user=Depends(require_permission("ai:chat")),
) -> dict[str, Any]:
    redis = _get_redis()
    history = await _load_session_history(redis, session_id)
    return {
        "session_id": session_id,
        "turns": len(history) // 2,
        "messages": [{"role": m.role, "content": m.content} for m in history],
    }


@router.delete(
    "/sessions/{session_id}",
    summary="Clear conversation history for a session",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_session(
    session_id: str,
    current_user=Depends(require_permission("ai:chat")),
) -> None:
    redis = _get_redis()
    if redis:
        await redis.delete(f"ai:session:{session_id}:history")


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
    copilot_req = CopilotRequest(
        operation=CopilotOperation.COMPLIANCE_EXPLAIN,
        user_message=(
            f"Explain this {request.framework.upper()} compliance failure:\n"
            f"Rule: {request.rule_name} ({request.rule_id})\n"
            f"Findings:\n" + "\n".join(f"  - {f}" for f in request.findings)
        ),
        context={
            "rule_id": request.rule_id,
            "rule_name": request.rule_name,
            "framework": request.framework,
            "findings": request.findings,
            "device": request.device_metadata,
        },
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return _to_response(response, CopilotOperation.COMPLIANCE_EXPLAIN)


# ── Compliance recommendations ─────────────────────────────────────────────────

@router.post(
    "/recommend/compliance",
    summary="AI-powered compliance improvement recommendations",
    response_model=CopilotResponse,
)
async def recommend_compliance(
    request: ComplianceRecommendRequest,
    current_user=Depends(require_permission("ai:analyze")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    content = await copilot.recommend_compliance_improvements(
        framework_scores=request.framework_scores,
        fleet_context=request.fleet_context,
    )
    # recommend_compliance_improvements returns str; wrap in a minimal response
    from app.domain.ai.providers.models import AIProvider, LLMResponse
    resp = LLMResponse(
        content=content,
        provider=AIProvider(copilot._primary.value),
        model="",
        cached=False,
    )
    return _to_response(resp, CopilotOperation.COMPLIANCE_RECOMMEND)


# ── Incident analysis ──────────────────────────────────────────────────────────

@router.post(
    "/analyze/incident",
    summary="AI-powered incident analysis and response guidance",
    response_model=CopilotResponse,
)
async def analyze_incident(
    request: IncidentAnalyzeRequest,
    current_user=Depends(require_permission("ai:analyze")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    copilot_req = CopilotRequest(
        operation=CopilotOperation.INCIDENT_ANALYZE,
        user_message=(
            f"Analyze this security incident:\n"
            f"Title: {request.incident.get('title', 'Unknown')}\n"
            f"Severity: {request.incident.get('severity', 'unknown').upper()}\n"
            f"Status: {request.incident.get('status', 'unknown')}\n"
            f"Description: {request.incident.get('description', 'No description.')}\n"
            f"Related events: {len(request.related_events)}"
        ),
        context={
            "incident": request.incident,
            "related_events": request.related_events[:20],
        },
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    log.info(
        "ai.incident.analyzed",
        incident_id=request.incident.get("id"),
        user=current_user.username,
    )
    return _to_response(response, CopilotOperation.INCIDENT_ANALYZE)


# ── Device recommendations ─────────────────────────────────────────────────────

@router.post(
    "/recommend/device",
    summary="AI-powered device security recommendations",
    response_model=CopilotResponse,
)
async def recommend_device(
    request: DeviceRecommendRequest,
    current_user=Depends(require_permission("ai:analyze")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    copilot_req = CopilotRequest(
        operation=CopilotOperation.DEVICE_RECOMMEND,
        user_message=(
            f"Provide security recommendations for device: "
            f"{request.device.get('hostname', request.device.get('device_id', 'unknown'))}\n"
            f"Type: {request.device.get('device_type', 'unknown')}\n"
            f"Status: {request.device.get('monitoring_state', 'unknown')}\n"
            f"Active drift events: {len(request.drift_events)}"
        ),
        context={
            "device": request.device,
            "compliance_scores": request.compliance_scores,
            "drift_events": request.drift_events[:10],
            "fleet": request.fleet_context,
        },
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return _to_response(response, CopilotOperation.DEVICE_RECOMMEND)


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
                "finding_id":        rec.finding_id,
                "rule_id":           rec.rule_id,
                "severity":          rec.severity,
                "title":             rec.title,
                "risk_explanation":  rec.risk_explanation,
                "business_impact":   rec.business_impact,
                "remediation_steps": rec.remediation_steps,
                "cli_commands":      rec.cli_commands,
                "verification_steps":rec.verification_steps,
                "estimated_effort":  rec.estimated_effort,
                "priority_score":    rec.priority_score,
            }
            for rec in recommendations
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
    copilot_req = CopilotRequest(
        operation=CopilotOperation.ACL_ANALYZE,
        user_message=f"Analyze this ACL configuration:\n```\n{request.acl_config}\n```",
        context={"device": request.device_metadata},
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return _to_response(response, CopilotOperation.ACL_ANALYZE)


# ── CVE explanation ────────────────────────────────────────────────────────────

@router.post(
    "/explain/cve",
    summary="AI explanation of a CVE and its impact",
    response_model=CopilotResponse,
)
async def explain_cve(
    request: CVERequest,
    current_user=Depends(require_permission("ai:explain")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    copilot_req = CopilotRequest(
        operation=CopilotOperation.CVE_EXPLAIN,
        user_message=(
            f"Explain {request.cve_id} and its impact on our infrastructure.\n"
            f"Affected devices: {len(request.affected_devices)}"
        ),
        context={"cve_id": request.cve_id, "affected_devices": request.affected_devices},
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return _to_response(response, CopilotOperation.CVE_EXPLAIN)


# ── Attack path analysis ───────────────────────────────────────────────────────

@router.post(
    "/analyze/attack-path",
    summary="AI-powered attack path analysis",
    response_model=CopilotResponse,
)
async def analyze_attack_path(
    request: AttackPathRequest,
    current_user=Depends(require_permission("ai:analyze")),
    copilot: SecurityCopilotService = Depends(_get_copilot),
) -> CopilotResponse:
    copilot_req = CopilotRequest(
        operation=CopilotOperation.ATTACK_PATH,
        user_message=(
            f"Analyze potential attack paths through our network. "
            f"{len(request.compliance_findings)} compliance finding(s) in scope."
        ),
        context={
            "topology": request.network_topology,
            "findings": request.compliance_findings,
        },
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return _to_response(response, CopilotOperation.ATTACK_PATH)


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
    copilot_req = CopilotRequest(
        operation=CopilotOperation.RISK_PRIORITIZE,
        user_message=(
            f"Prioritize {len(request.findings)} security findings by risk. "
            f"Regulatory requirements: {', '.join(request.regulatory_requirements) or 'None specified'}. "
            "Produce a ranked remediation roadmap with effort estimates."
        ),
        context={
            "findings": request.findings,
            "device": request.device_metadata,
            "regulatory_requirements": request.regulatory_requirements,
        },
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return _to_response(response, CopilotOperation.RISK_PRIORITIZE)


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

    copilot_req = CopilotRequest(
        operation=CopilotOperation.SECURITY_SUMMARIZE,
        user_message=(
            f"Generate an executive security summary for the last {hours} hours. "
            f"Fleet: {fleet.get('total_devices', 0)} devices, "
            f"{fleet.get('average_compliance_score', 0):.1f}% avg compliance, "
            f"{fleet.get('active_drift_events', 0)} active drift events."
        ),
        context={
            "fleet_summary": fleet,
            "time_range_hours": hours,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        user_id=str(current_user.id),
    )
    response = await copilot.process(copilot_req)
    return _to_response(response, CopilotOperation.SECURITY_SUMMARIZE)


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
        "primary":   copilot._primary.value,
        "fallback":  copilot._fallback.value if copilot._fallback else None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
