"""
Prometheus metrics registry for the Cisco Security Platform.
All platform metrics are defined here for consistent labeling and naming.
"""

from prometheus_client import Counter, Gauge, Histogram, Info, Summary

# ── HTTP Layer ─────────────────────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "cisco_security_http_requests_total",
    "Total HTTP requests processed",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "cisco_security_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_CONNECTIONS = Gauge(
    "cisco_security_active_connections",
    "Number of active HTTP connections",
)

# ── Device Operations ──────────────────────────────────────────────────────────

DEVICE_AUDIT_TOTAL = Counter(
    "cisco_security_device_audits_total",
    "Total device audit executions",
    ["device_type", "status", "protocol"],
)

DEVICE_AUDIT_DURATION = Histogram(
    "cisco_security_device_audit_duration_seconds",
    "Device audit execution duration",
    ["device_type", "protocol"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

DEVICE_CONNECTION_POOL = Gauge(
    "cisco_security_device_connections_active",
    "Active device SSH/NETCONF connections",
    ["protocol"],
)

DEVICE_COMMAND_FAILURES = Counter(
    "cisco_security_device_command_failures_total",
    "Device command execution failures",
    ["device_type", "error_type"],
)

# ── Compliance Engine ──────────────────────────────────────────────────────────

COMPLIANCE_SCORE = Gauge(
    "cisco_security_compliance_score",
    "Current compliance score (0-100)",
    ["framework", "tenant_id"],
)

COMPLIANCE_CHECKS_TOTAL = Counter(
    "cisco_security_compliance_checks_total",
    "Total compliance checks executed",
    ["framework", "rule_id", "result"],
)

COMPLIANCE_DRIFT_EVENTS = Counter(
    "cisco_security_compliance_drift_events_total",
    "Compliance drift detection events",
    ["severity", "framework"],
)

POLICY_EVALUATION_DURATION = Histogram(
    "cisco_security_policy_evaluation_duration_seconds",
    "OPA/rule policy evaluation duration",
    ["policy_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# ── AI Copilot ─────────────────────────────────────────────────────────────────

AI_REQUESTS_TOTAL = Counter(
    "cisco_security_ai_requests_total",
    "Total AI copilot requests",
    ["provider", "operation_type", "status"],
)

AI_REQUEST_DURATION = Histogram(
    "cisco_security_ai_request_duration_seconds",
    "AI provider request duration",
    ["provider", "operation_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

AI_TOKEN_USAGE = Counter(
    "cisco_security_ai_tokens_total",
    "Total LLM tokens consumed",
    ["provider", "token_type"],  # token_type: prompt | completion
)

AI_PROVIDER_FALLBACKS = Counter(
    "cisco_security_ai_provider_fallbacks_total",
    "AI provider fallback events",
    ["primary_provider", "fallback_provider"],
)

# ── SIEM Integrations ──────────────────────────────────────────────────────────

SIEM_EVENTS_EXPORTED = Counter(
    "cisco_security_siem_events_exported_total",
    "Total events exported to SIEM platforms",
    ["platform", "event_type", "status"],
)

SIEM_BATCH_SIZE = Histogram(
    "cisco_security_siem_batch_size",
    "SIEM export batch sizes",
    ["platform"],
    buckets=[1, 10, 25, 50, 100, 250, 500, 1000],
)

SIEM_EXPORT_LATENCY = Histogram(
    "cisco_security_siem_export_latency_seconds",
    "SIEM event export latency",
    ["platform"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# ── Worker / Celery ────────────────────────────────────────────────────────────

WORKER_TASKS_TOTAL = Counter(
    "cisco_security_worker_tasks_total",
    "Total Celery worker tasks",
    ["task_name", "status"],
)

WORKER_TASK_DURATION = Histogram(
    "cisco_security_worker_task_duration_seconds",
    "Worker task execution duration",
    ["task_name"],
    buckets=[1, 5, 15, 30, 60, 120, 300, 600, 1800],
)

WORKER_QUEUE_DEPTH = Gauge(
    "cisco_security_worker_queue_depth",
    "Number of tasks in worker queues",
    ["queue_name"],
)

# ── Audit System ───────────────────────────────────────────────────────────────

AUDIT_EVENTS_TOTAL = Counter(
    "cisco_security_audit_events_total",
    "Total audit events recorded",
    ["action", "resource_type", "outcome"],
)

AUDIT_LOG_SIZE = Gauge(
    "cisco_security_audit_log_total_entries",
    "Total audit log entries in database",
)

# ── Threat Intelligence ────────────────────────────────────────────────────────

THREAT_INDICATORS_TOTAL = Gauge(
    "cisco_security_threat_indicators_total",
    "Total threat indicators in database",
    ["indicator_type", "source"],
)

THREAT_MATCHES_TOTAL = Counter(
    "cisco_security_threat_matches_total",
    "Total threat indicator matches detected",
    ["indicator_type", "severity"],
)

# ── Platform Info ──────────────────────────────────────────────────────────────

PLATFORM_INFO = Info(
    "cisco_security_platform",
    "Cisco Security Platform build information",
)

# Populate static info at module load
PLATFORM_INFO.info({
    "version": "2.0.0",
    "service": "cisco-security-platform",
})
