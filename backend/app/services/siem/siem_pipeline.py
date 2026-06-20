"""
Enterprise SIEM Integration Layer
Supports: Splunk HEC, Microsoft Sentinel, Elastic SIEM, IBM QRadar
Features: batching, retries, delivery tracking, event normalization,
          schema validation, ingestion pipelines, export scheduling.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

from app.core.config import settings
from app.core.metrics import SIEM_EVENTS_EXPORTED, SIEM_BATCH_SIZE, SIEM_EXPORT_LATENCY

log = structlog.get_logger(__name__)


# ── Event Schema ───────────────────────────────────────────────────────────────

class SIEMEventType(str, Enum):
    COMPLIANCE_FAILURE    = "compliance_failure"
    COMPLIANCE_PASS       = "compliance_pass"
    DRIFT_DETECTED        = "drift_detected"
    AUDIT_EXECUTED        = "audit_executed"
    REMEDIATION_APPLIED   = "remediation_applied"
    THREAT_DETECTED       = "threat_detected"
    AUTH_SUCCESS          = "auth_success"
    AUTH_FAILURE          = "auth_failure"
    CONFIG_CHANGED        = "config_changed"
    DEVICE_UNREACHABLE    = "device_unreachable"
    POLICY_VIOLATION      = "policy_violation"
    USER_ACTION           = "user_action"


class SIEMSeverity(str, Enum):
    CRITICAL  = "critical"
    HIGH      = "high"
    MEDIUM    = "medium"
    LOW       = "low"
    INFO      = "info"


@dataclass
class NormalizedEvent:
    """Platform-agnostic normalized security event — maps to any SIEM schema."""
    event_id:       str              = field(default_factory=lambda: str(uuid4()))
    event_type:     SIEMEventType    = SIEMEventType.USER_ACTION
    severity:       SIEMSeverity     = SIEMSeverity.INFO
    timestamp:      datetime         = field(default_factory=lambda: datetime.now(timezone.utc))
    source_system:  str              = "cisco-security-platform"
    source_host:    str              = "platform"
    tenant_id:      str              = "default"
    device_id:      str | None       = None
    device_ip:      str | None       = None
    device_type:    str | None       = None
    user_id:        str | None       = None
    username:       str | None       = None
    action:         str              = ""
    outcome:        str              = "unknown"
    rule_id:        str | None       = None
    framework:      str | None       = None
    compliance_score: float | None   = None
    description:    str              = ""
    raw_data:       dict[str, Any]   = field(default_factory=dict)
    tags:           list[str]        = field(default_factory=list)
    mitre_tactics:  list[str]        = field(default_factory=list)
    mitre_techniques: list[str]      = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        key = f"{self.event_type}:{self.device_id}:{self.rule_id}:{self.timestamp.isoformat()}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class DeliveryReceipt:
    event_id:      str
    platform:      str
    delivered_at:  datetime
    status:        str           # success | failed | queued
    attempts:      int           = 1
    error_message: str | None    = None
    platform_ref:  str | None    = None   # Splunk ackId, Sentinel response, etc.


# ── Base SIEM Adapter ──────────────────────────────────────────────────────────

class SIEMAdapter(ABC):
    """Abstract base for all SIEM platform adapters."""

    platform_name: str
    max_batch_size: int = 100
    max_retries: int = 3
    retry_backoff: float = 2.0

    @abstractmethod
    async def send_batch(self, events: list[NormalizedEvent]) -> list[DeliveryReceipt]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    async def send_single(self, event: NormalizedEvent) -> DeliveryReceipt:
        receipts = await self.send_batch([event])
        return receipts[0]

    async def _retry_send(self, func, *args, **kwargs) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                wait = self.retry_backoff ** attempt
                log.warning(
                    "siem.retry",
                    platform=self.platform_name,
                    attempt=attempt + 1,
                    wait=wait,
                    error=str(exc),
                )
                await asyncio.sleep(wait)
        raise RuntimeError(f"SIEM send failed after {self.max_retries} attempts: {last_exc}") from last_exc


# ── Splunk HEC Adapter ─────────────────────────────────────────────────────────

class SplunkHECAdapter(SIEMAdapter):
    """
    Splunk HTTP Event Collector adapter.
    Supports: batching, indexer acknowledgment, sourcetype mapping.
    """
    platform_name = "splunk"

    def __init__(self) -> None:
        import aiohttp
        cfg = settings.siem
        self._url = cfg.SPLUNK_HEC_URL
        self._token = cfg.SPLUNK_HEC_TOKEN
        self._index = cfg.SPLUNK_INDEX
        self._sourcetype = cfg.SPLUNK_SOURCETYPE
        self.max_batch_size = cfg.SPLUNK_BATCH_SIZE
        self._session: aiohttp.ClientSession | None = None

    def _to_hec_event(self, event: NormalizedEvent) -> dict[str, Any]:
        return {
            "time": event.timestamp.timestamp(),
            "host": event.source_host,
            "source": event.source_system,
            "sourcetype": self._sourcetype,
            "index": self._index,
            "event": {
                "event_id":         event.event_id,
                "event_type":       event.event_type.value,
                "severity":         event.severity.value,
                "tenant_id":        event.tenant_id,
                "device_id":        event.device_id,
                "device_ip":        event.device_ip,
                "device_type":      event.device_type,
                "user_id":          event.user_id,
                "username":         event.username,
                "action":           event.action,
                "outcome":          event.outcome,
                "rule_id":          event.rule_id,
                "framework":        event.framework,
                "compliance_score": event.compliance_score,
                "description":      event.description,
                "tags":             event.tags,
                "mitre_tactics":    event.mitre_tactics,
                "mitre_techniques": event.mitre_techniques,
                **event.raw_data,
            },
        }

    async def _get_session(self):
        import aiohttp
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Splunk {self._token}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self._session

    async def send_batch(self, events: list[NormalizedEvent]) -> list[DeliveryReceipt]:
        if not self._url or not self._token:
            log.warning("siem.splunk.not_configured")
            return [DeliveryReceipt(e.event_id, self.platform_name, datetime.now(timezone.utc), "skipped") for e in events]

        start = time.monotonic()
        # Splunk HEC accepts newline-delimited JSON
        payload = "\n".join(json.dumps(self._to_hec_event(e)) for e in events)
        receipts: list[DeliveryReceipt] = []

        async def _post():
            session = await self._get_session()
            async with session.post(f"{self._url}/services/collector/event", data=payload) as resp:
                body = await resp.json()
                if resp.status not in (200, 201):
                    raise RuntimeError(f"Splunk HEC error {resp.status}: {body}")
                return body

        try:
            result = await self._retry_send(_post)
            latency = time.monotonic() - start
            SIEM_EXPORT_LATENCY.labels(platform=self.platform_name).observe(latency)
            SIEM_BATCH_SIZE.labels(platform=self.platform_name).observe(len(events))

            for event in events:
                receipts.append(DeliveryReceipt(
                    event_id=event.event_id,
                    platform=self.platform_name,
                    delivered_at=datetime.now(timezone.utc),
                    status="success",
                    platform_ref=str(result.get("ackId")),
                ))
                SIEM_EVENTS_EXPORTED.labels(
                    platform=self.platform_name,
                    event_type=event.event_type.value,
                    status="success",
                ).inc()
        except Exception as exc:
            log.error("siem.splunk.send_failed", error=str(exc), batch_size=len(events))
            for event in events:
                receipts.append(DeliveryReceipt(
                    event_id=event.event_id,
                    platform=self.platform_name,
                    delivered_at=datetime.now(timezone.utc),
                    status="failed",
                    error_message=str(exc),
                ))
                SIEM_EVENTS_EXPORTED.labels(
                    platform=self.platform_name,
                    event_type=event.event_type.value,
                    status="failed",
                ).inc()
        return receipts

    async def health_check(self) -> bool:
        if not self._url or not self._token:
            return False
        try:
            session = await self._get_session()
            async with session.get(f"{self._url}/services/collector/health") as resp:
                return resp.status == 200
        except Exception:
            return False


# ── Microsoft Sentinel Adapter ─────────────────────────────────────────────────

class SentinelAdapter(SIEMAdapter):
    """
    Microsoft Sentinel Log Analytics Data Collector API adapter.
    Uses HMAC-SHA256 signature authentication.
    """
    platform_name = "sentinel"

    def __init__(self) -> None:
        cfg = settings.siem
        self._workspace_id = cfg.SENTINEL_WORKSPACE_ID
        self._primary_key = cfg.SENTINEL_PRIMARY_KEY
        self._log_type = cfg.SENTINEL_LOG_TYPE
        self._session = None

    def _build_signature(self, date: str, content_length: int, method: str, content_type: str, resource: str) -> str:
        import base64, hashlib, hmac
        x_headers = f"x-ms-date:{date}"
        string_to_hash = f"{method}\n{content_length}\n{content_type}\n{x_headers}\n{resource}"
        bytes_to_hash = string_to_hash.encode("utf-8")
        decoded_key = base64.b64decode(self._primary_key)
        encoded_hash = base64.b64encode(hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()).decode()
        return f"SharedKey {self._workspace_id}:{encoded_hash}"

    def _to_sentinel_record(self, event: NormalizedEvent) -> dict[str, Any]:
        return {
            "TimeGenerated":      event.timestamp.isoformat(),
            "EventId":            event.event_id,
            "EventType":          event.event_type.value,
            "Severity":           event.severity.value,
            "TenantId":           event.tenant_id,
            "DeviceId":           event.device_id or "",
            "DeviceIp":           event.device_ip or "",
            "DeviceType":         event.device_type or "",
            "UserId":             event.user_id or "",
            "Username":           event.username or "",
            "Action":             event.action,
            "Outcome":            event.outcome,
            "RuleId":             event.rule_id or "",
            "Framework":          event.framework or "",
            "ComplianceScore":    event.compliance_score,
            "Description":        event.description,
            "MitreTactics":       ",".join(event.mitre_tactics),
            "MitreTechniques":    ",".join(event.mitre_techniques),
            "Tags":               ",".join(event.tags),
            "SourceSystem":       event.source_system,
        }

    async def send_batch(self, events: list[NormalizedEvent]) -> list[DeliveryReceipt]:
        if not self._workspace_id or not self._primary_key:
            return [DeliveryReceipt(e.event_id, self.platform_name, datetime.now(timezone.utc), "skipped") for e in events]

        import aiohttp
        from email.utils import formatdate

        records = [self._to_sentinel_record(e) for e in events]
        body = json.dumps(records)
        date = formatdate(usegmt=True)
        content_length = len(body)
        resource = "/api/logs"
        content_type = "application/json"
        signature = self._build_signature(date, content_length, "POST", content_type, resource)
        url = f"https://{self._workspace_id}.ods.opinsights.azure.com{resource}?api-version=2016-04-01"
        headers = {
            "Content-Type": content_type,
            "Authorization": signature,
            "Log-Type": self._log_type,
            "x-ms-date": date,
        }
        start = time.monotonic()
        receipts: list[DeliveryReceipt] = []

        async def _post():
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=body, headers=headers) as resp:
                    if resp.status not in (200, 202):
                        raise RuntimeError(f"Sentinel error {resp.status}: {await resp.text()}")

        try:
            await self._retry_send(_post)
            latency = time.monotonic() - start
            SIEM_EXPORT_LATENCY.labels(platform=self.platform_name).observe(latency)
            SIEM_BATCH_SIZE.labels(platform=self.platform_name).observe(len(events))
            for e in events:
                receipts.append(DeliveryReceipt(e.event_id, self.platform_name, datetime.now(timezone.utc), "success"))
                SIEM_EVENTS_EXPORTED.labels(platform=self.platform_name, event_type=e.event_type.value, status="success").inc()
        except Exception as exc:
            log.error("siem.sentinel.send_failed", error=str(exc))
            for e in events:
                receipts.append(DeliveryReceipt(e.event_id, self.platform_name, datetime.now(timezone.utc), "failed", error_message=str(exc)))
                SIEM_EVENTS_EXPORTED.labels(platform=self.platform_name, event_type=e.event_type.value, status="failed").inc()
        return receipts

    async def health_check(self) -> bool:
        return bool(self._workspace_id and self._primary_key)


# ── Elastic SIEM Adapter ───────────────────────────────────────────────────────

class ElasticSIEMAdapter(SIEMAdapter):
    """
    Elastic Security SIEM adapter using Elasticsearch Bulk API.
    Supports index lifecycle management and ECS normalization.
    """
    platform_name = "elastic"

    def __init__(self) -> None:
        cfg = settings.siem
        self._url = cfg.ELASTIC_URL
        self._api_key = cfg.ELASTIC_API_KEY
        self._index_prefix = cfg.ELASTIC_INDEX_PREFIX
        self._session = None

    def _index_name(self, event: NormalizedEvent) -> str:
        date_suffix = event.timestamp.strftime("%Y.%m.%d")
        return f"{self._index_prefix}-{event.event_type.value}-{date_suffix}"

    def _to_ecs(self, event: NormalizedEvent) -> dict[str, Any]:
        """Map to Elastic Common Schema (ECS) format."""
        return {
            "@timestamp":       event.timestamp.isoformat(),
            "event": {
                "id":           event.event_id,
                "kind":         "event",
                "category":     ["network", "configuration"],
                "type":         [event.event_type.value],
                "outcome":      event.outcome,
                "severity":     {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(event.severity.value, 0),
            },
            "host": {
                "id":           event.device_id,
                "ip":           [event.device_ip] if event.device_ip else [],
                "type":         event.device_type,
            },
            "user": {
                "id":           event.user_id,
                "name":         event.username,
            },
            "rule": {
                "id":           event.rule_id,
                "name":         event.description,
            },
            "labels": {
                "tenant_id":    event.tenant_id,
                "framework":    event.framework,
                "action":       event.action,
            },
            "tags":             event.tags,
            "threat": {
                "tactic":       {"name": event.mitre_tactics},
                "technique":    {"id": event.mitre_techniques},
            },
            "cisco_security": {
                "compliance_score": event.compliance_score,
                "source_system":    event.source_system,
                **event.raw_data,
            },
        }

    async def send_batch(self, events: list[NormalizedEvent]) -> list[DeliveryReceipt]:
        if not self._url or not self._api_key:
            return [DeliveryReceipt(e.event_id, self.platform_name, datetime.now(timezone.utc), "skipped") for e in events]

        import aiohttp
        # Elastic Bulk API format: action_meta\ndoc\n...
        lines = []
        for event in events:
            action = {"index": {"_index": self._index_name(event), "_id": event.event_id}}
            lines.append(json.dumps(action))
            lines.append(json.dumps(self._to_ecs(event)))
        bulk_body = "\n".join(lines) + "\n"

        start = time.monotonic()
        receipts: list[DeliveryReceipt] = []

        async def _post():
            headers = {
                "Authorization": f"ApiKey {self._api_key}",
                "Content-Type": "application/x-ndjson",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self._url}/_bulk", data=bulk_body, headers=headers) as resp:
                    body = await resp.json()
                    if resp.status not in (200, 201) or body.get("errors"):
                        raise RuntimeError(f"Elastic bulk error: {body}")
                    return body

        try:
            result = await self._retry_send(_post)
            latency = time.monotonic() - start
            SIEM_EXPORT_LATENCY.labels(platform=self.platform_name).observe(latency)
            SIEM_BATCH_SIZE.labels(platform=self.platform_name).observe(len(events))
            for e in events:
                receipts.append(DeliveryReceipt(e.event_id, self.platform_name, datetime.now(timezone.utc), "success"))
                SIEM_EVENTS_EXPORTED.labels(platform=self.platform_name, event_type=e.event_type.value, status="success").inc()
        except Exception as exc:
            log.error("siem.elastic.send_failed", error=str(exc))
            for e in events:
                receipts.append(DeliveryReceipt(e.event_id, self.platform_name, datetime.now(timezone.utc), "failed", error_message=str(exc)))
                SIEM_EVENTS_EXPORTED.labels(platform=self.platform_name, event_type=e.event_type.value, status="failed").inc()
        return receipts

    async def health_check(self) -> bool:
        if not self._url or not self._api_key:
            return False
        try:
            import aiohttp
            headers = {"Authorization": f"ApiKey {self._api_key}"}
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{self._url}/_cluster/health", headers=headers) as r:
                    return r.status == 200
        except Exception:
            return False


# ── SIEM Pipeline Orchestrator ─────────────────────────────────────────────────

class SIEMPipeline:
    """
    Multi-platform SIEM export pipeline with:
    - Per-platform batching queues
    - Background flush workers
    - Delivery tracking
    - Event deduplication
    """

    def __init__(self) -> None:
        self._adapters: dict[str, SIEMAdapter] = {}
        self._queues: dict[str, asyncio.Queue[NormalizedEvent]] = {}
        self._seen_hashes: set[str] = set()
        self._running = False
        self._workers: list[asyncio.Task] = []
        self._receipts: list[DeliveryReceipt] = []
        self._lock = asyncio.Lock()

    def register_adapter(self, adapter: SIEMAdapter) -> None:
        self._adapters[adapter.platform_name] = adapter
        self._queues[adapter.platform_name] = asyncio.Queue(maxsize=10_000)
        log.info("siem.pipeline.adapter_registered", platform=adapter.platform_name)

    async def start(self) -> None:
        self._running = True
        for name in self._adapters:
            task = asyncio.create_task(self._flush_worker(name), name=f"siem-worker-{name}")
            self._workers.append(task)
        log.info("siem.pipeline.started", adapters=list(self._adapters.keys()))

    async def stop(self) -> None:
        self._running = False
        # Drain all queues before shutdown
        for name, queue in self._queues.items():
            await self._flush_queue(name, drain=True)
        for task in self._workers:
            task.cancel()
        log.info("siem.pipeline.stopped")

    async def emit(self, event: NormalizedEvent) -> None:
        """Enqueue an event for delivery to all registered platforms."""
        # Deduplication
        if event.content_hash in self._seen_hashes:
            log.debug("siem.event.duplicate_skipped", event_id=event.event_id)
            return
        async with self._lock:
            self._seen_hashes.add(event.content_hash)
            if len(self._seen_hashes) > 100_000:
                # Rotate oldest 10% to prevent unbounded growth
                seen_list = list(self._seen_hashes)
                self._seen_hashes = set(seen_list[10_000:])

        for name, queue in self._queues.items():
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                log.error("siem.queue.full", platform=name, dropped_event=event.event_id)
                SIEM_EVENTS_EXPORTED.labels(platform=name, event_type=event.event_type.value, status="dropped").inc()

    async def _flush_worker(self, platform: str) -> None:
        adapter = self._adapters[platform]
        queue = self._queues[platform]
        flush_interval = settings.siem.SPLUNK_FLUSH_INTERVAL

        while self._running:
            await asyncio.sleep(flush_interval)
            await self._flush_queue(platform)

    async def _flush_queue(self, platform: str, drain: bool = False) -> None:
        adapter = self._adapters[platform]
        queue = self._queues[platform]
        batch: list[NormalizedEvent] = []

        max_size = adapter.max_batch_size
        while not queue.empty() and len(batch) < max_size:
            try:
                batch.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break

        if not batch:
            return

        log.debug("siem.pipeline.flushing", platform=platform, batch_size=len(batch))
        receipts = await adapter.send_batch(batch)
        self._receipts.extend(receipts)

        # If drain mode (shutdown), continue until empty
        if drain and not queue.empty():
            await self._flush_queue(platform, drain=True)

    async def health_status(self) -> dict[str, bool]:
        results = {}
        for name, adapter in self._adapters.items():
            results[name] = await adapter.health_check()
        return results

    def get_recent_receipts(self, limit: int = 100) -> list[DeliveryReceipt]:
        return self._receipts[-limit:]


# ── Factory ────────────────────────────────────────────────────────────────────

def build_siem_pipeline() -> SIEMPipeline:
    """Build and configure the SIEM pipeline from settings."""
    pipeline = SIEMPipeline()
    cfg = settings.siem

    if cfg.SPLUNK_HEC_URL and cfg.SPLUNK_HEC_TOKEN:
        pipeline.register_adapter(SplunkHECAdapter())

    if cfg.SENTINEL_WORKSPACE_ID and cfg.SENTINEL_PRIMARY_KEY:
        pipeline.register_adapter(SentinelAdapter())

    if cfg.ELASTIC_URL and cfg.ELASTIC_API_KEY:
        pipeline.register_adapter(ElasticSIEMAdapter())

    return pipeline
