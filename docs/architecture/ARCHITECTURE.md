# Cisco Security Platform — Architecture Documentation

## Overview

The Cisco Security Platform is an enterprise-grade, cloud-native cybersecurity compliance and network automation platform. It provides continuous compliance monitoring, AI-assisted remediation, SIEM integration, and real-time threat detection for large-scale Cisco network infrastructure.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CISCO SECURITY PLATFORM v2.0                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐    ┌──────────────────────────────────────────────────┐   │
│  │   React SPA   │    │                  FastAPI Backend                  │   │
│  │  TypeScript   │◄──►│  API Gateway  │  RBAC  │  Auth  │  Audit Log    │   │
│  │  Tailwind     │    └──────┬─────────────────────────────────┬─────────┘   │
│  │  Recharts     │           │                                 │             │
│  └──────────────┘           ▼                                 ▼             │
│                   ┌──────────────────┐               ┌────────────────────┐ │
│                   │  Domain Layer     │               │  Infrastructure    │ │
│                   │                  │               │                    │ │
│                   │ ┌──────────────┐ │               │ ┌────────────────┐ │ │
│                   │ │  Compliance  │ │               │ │   PostgreSQL   │ │ │
│                   │ │  Engine      │ │               │ │   (Primary +   │ │ │
│                   │ │  (CIS/NIST/  │ │               │ │   Read Replica)│ │ │
│                   │ │  PCI/HIPAA)  │ │               │ └────────────────┘ │ │
│                   │ └──────────────┘ │               │ ┌────────────────┐ │ │
│                   │ ┌──────────────┐ │               │ │  Redis Cluster │ │ │
│                   │ │  AI Copilot  │ │               │ │  (Cache +      │ │ │
│                   │ │  (OpenAI/    │ │               │ │   Sessions +   │ │ │
│                   │ │  Anthropic/  │ │               │ │   Rate Limit)  │ │ │
│                   │ │  Ollama)     │ │               │ └────────────────┘ │ │
│                   │ └──────────────┘ │               │ ┌────────────────┐ │ │
│                   │ ┌──────────────┐ │               │ │  Celery + RMQ  │ │ │
│                   │ │  Continuous  │ │               │ │  (Workers +    │ │ │
│                   │ │  Compliance  │ │               │ │   Task Queue)  │ │ │
│                   │ │  Monitor     │ │               │ └────────────────┘ │ │
│                   │ └──────────────┘ │               └────────────────────┘ │
│                   └──────────────────┘                                       │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                     SIEM Integration Layer                              │ │
│  │   Splunk HEC  │  Microsoft Sentinel  │  Elastic SIEM  │  IBM QRadar    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Network Device Execution Engine                      │ │
│  │   SSH (asyncssh/Netmiko)  │  NETCONF (ncclient)  │  REST/RESTCONF     │ │
│  │   Connection Pool         │  Rate Limiting        │  Bulk Pipeline     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         Observability Stack                             │ │
│  │   Prometheus Metrics  │  Grafana Dashboards  │  OpenTelemetry Tracing │ │
│  │   Structured Logging  │  Correlation IDs     │  Health Endpoints       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Domain-Driven Design Structure

```
backend/app/
├── api/v1/routers/          # HTTP route handlers (thin controllers)
├── core/
│   ├── config.py            # Pydantic Settings with environment separation
│   ├── metrics.py           # Prometheus registry (all metrics defined here)
│   ├── exceptions.py        # Domain exceptions + handlers
│   └── security.py          # JWT, RBAC, permission decorators
├── domain/
│   ├── compliance/
│   │   ├── engine/          # Core compliance engine, rule evaluation
│   │   ├── repositories/    # Data access abstractions
│   │   ├── strategies/      # Pluggable scoring strategies
│   │   └── opa/             # Open Policy Agent integration
│   ├── audit/
│   │   ├── handlers/        # Audit event handlers
│   │   ├── repositories/    # Immutable audit log store
│   │   └── dtos/            # Data transfer objects
│   ├── devices/
│   │   ├── repositories/    # Device CRUD
│   │   └── handlers/        # Device lifecycle events
│   ├── threats/
│   │   ├── repositories/    # Threat intelligence store
│   │   └── handlers/        # IOC matching, CVE enrichment
│   └── ai/
│       ├── providers/       # LLM provider abstractions (OpenAI/Anthropic/Ollama)
│       ├── orchestration/   # Prompt orchestration, chain-of-thought
│       └── rag/             # Vector store, embeddings, RAG pipeline
├── services/
│   ├── compliance/          # ContinuousComplianceMonitor (flagship)
│   ├── siem/                # SIEMPipeline (Splunk/Sentinel/Elastic/QRadar)
│   ├── network/             # BulkExecutionPipeline, SSH/NETCONF executors
│   └── audit/               # AuditService, immutable log management
├── infrastructure/
│   ├── database/            # AsyncSQLAlchemy, migrations, health checks
│   ├── cache/               # Redis client, connection pool
│   ├── messaging/           # Celery broker, task routing
│   └── vault/               # HashiCorp Vault integration
├── workers/                 # Celery task definitions
└── middleware/
    ├── security_headers.py  # SecurityHeaders, RateLimit, Audit middlewares
    └── ...
```

---

## Compliance Framework Support

| Framework    | Rules | Weighted Scoring | OPA Support | Auto-Remediation |
|--------------|-------|-----------------|-------------|-----------------|
| CIS IOS L1   | 87    | ✅              | ✅          | ✅              |
| CIS IOS L2   | 43    | ✅              | ✅          | ⚠️ Manual       |
| NIST CSF     | 108   | ✅              | ✅          | ⚠️ Manual       |
| NIST 800-53  | 256   | ✅              | ✅          | ❌              |
| PCI-DSS v4   | 64    | ✅              | ✅          | ⚠️ Manual       |
| HIPAA        | 45    | ✅              | ✅          | ❌              |
| ISO 27001    | 114   | ✅              | ✅          | ❌              |
| MITRE ATT&CK | 72    | ✅              | ✅          | ❌              |

---

## RBAC Matrix

| Role              | Devices | Audits  | Compliance | Remediation | AI Copilot | Admin  | SIEM   |
|-------------------|---------|---------|------------|-------------|------------|--------|--------|
| **Viewer**        | Read    | Read    | Read       | ❌          | Read       | ❌     | Read   |
| **Analyst**       | Read    | Execute | Read       | Propose     | Full       | ❌     | Read   |
| **Engineer**      | Full    | Execute | Full       | Execute     | Full       | ❌     | Config |
| **SecOps Lead**   | Full    | Full    | Full       | Approve     | Full       | Partial | Full  |
| **Admin**         | Full    | Full    | Full       | Full        | Full       | Full   | Full   |
| **Read-Only API** | Read    | ❌      | Read       | ❌          | ❌         | ❌     | ❌     |

---

## Continuous Compliance Monitoring — Architecture

```
Device Fleet (1000+ devices)
        │
        ▼
┌─────────────────────┐
│  Scheduling Loop    │  ← Runs every 10s, checks next_poll_at per device
│  (asyncio task)     │
└────────┬────────────┘
         │  Due devices
         ▼
┌─────────────────────┐    ┌──────────────────────┐
│  Poll Device        │───►│  NetworkConfigFetcher │
│  (concurrent, ≤50)  │    │  (SSH/NETCONF)        │
└────────┬────────────┘    └──────────────────────┘
         │  Config dict
         ▼
┌─────────────────────┐
│  Config Hash        │
│  Comparison         │
└────────┬────────────┘
         │  Changed?
    Yes  ▼         No → skip
┌─────────────────────┐
│  Compliance         │
│  Orchestrator       │
│  (rule evaluation)  │
└────────┬────────────┘
         │  ComplianceReport
         ▼
┌─────────────────────┐    ┌──────────────────────┐
│  Drift Detection    │───►│  Alert Dispatcher     │
│  (score delta ≥5%)  │    │  (SIEM + webhooks)   │
└────────┬────────────┘    └──────────────────────┘
         │
         ▼
┌─────────────────────┐    ┌──────────────────────┐
│  History Store      │    │  Remediation Workflow │
│  (Redis + Postgres) │    │  (if auto-enabled)    │
└─────────────────────┘    └──────────────────────┘
```

---

## AI Copilot — Provider Abstraction

```
SecurityCopilotService
        │
        ├── Primary Provider (configurable)
        │   ├── OpenAI GPT-4o
        │   ├── Anthropic Claude 3.5 Sonnet
        │   ├── Azure OpenAI
        │   └── Ollama (local LLM — no API key)
        │
        ├── Fallback Provider (automatic on failure)
        │
        ├── AI Response Cache (Redis, 1h TTL)
        │
        └── Operations
            ├── explain_compliance_failure()
            ├── recommend_remediation()
            ├── analyze_acl()
            ├── explain_cve()
            ├── analyze_attack_path()
            ├── config_analyze()
            ├── risk_prioritize()
            └── chat() (streaming supported)
```

---

## Kubernetes Deployment Architecture

```
Namespace: cisco-security
├── Deployments
│   ├── api          (3–20 replicas, HPA on CPU/Memory)
│   ├── frontend     (2–5 replicas)
│   ├── worker-audit (2–10 replicas)
│   ├── worker-compliance (3–15 replicas)
│   └── worker-network    (2–20 replicas, high SSH concurrency)
├── StatefulSets
│   ├── postgresql   (primary + read replica)
│   └── redis        (master + 2 replicas)
├── Network Policies
│   ├── api: ingress from ingress-nginx + frontend only
│   ├── workers: egress to DB, Redis, devices (22/830)
│   └── default-deny all
├── PodDisruptionBudgets
│   └── api: minAvailable=2
└── HorizontalPodAutoscalers
    └── All services with configurable scale triggers
```

---

## Security Controls

| Control                    | Implementation                                     |
|----------------------------|----------------------------------------------------|
| Authentication             | JWT (HS256, 30min access + 7d refresh)             |
| Authorization              | RBAC with fine-grained permissions                 |
| Rate Limiting              | Redis sliding window (per-IP + per-user)           |
| Secure Headers             | A+ Mozilla Observatory rating                      |
| CSRF Protection            | SameSite=Strict session cookies                    |
| Audit Logging              | HMAC-signed, append-only, 7-year retention         |
| Secret Management          | HashiCorp Vault integration                        |
| Transport Security         | TLS 1.3, HSTS with preload                         |
| Container Security         | Non-root, read-only FS, dropped capabilities       |
| Network Segmentation       | Kubernetes NetworkPolicy, namespace isolation      |
| Dependency Scanning        | Integrated in CI/CD pipeline                       |
| Supply Chain               | Image signing, SBOM generation                     |

---

## Scaling Strategy

| Tier            | Current Capacity | Scale Target | Mechanism                    |
|-----------------|-----------------|--------------|------------------------------|
| API             | 3 pods, 4 workers each | 20 pods  | HPA (CPU 70%)            |
| Device Polling  | 50 concurrent SSH | 1000+ devices | Worker HPA + batching      |
| Compliance Eval | 10 parallel rules/device | Fleet-wide | Celery worker scaling    |
| SIEM Export     | 100 events/batch | 10K events/s | Queue + batch tuning        |
| AI Requests     | Provider rate-limited | Fallback chain | Multi-provider routing  |

---

## Disaster Recovery

- **RTO**: 15 minutes (automated failover via ArgoCD + health probes)
- **RPO**: 5 minutes (PostgreSQL WAL streaming to read replica)
- **Backup**: Daily encrypted snapshots to S3 (90-day retention)
- **Rollback**: Helm revision history (5 revisions), ArgoCD sync
- **Runbooks**: `/docs/runbooks/` for all failure scenarios
