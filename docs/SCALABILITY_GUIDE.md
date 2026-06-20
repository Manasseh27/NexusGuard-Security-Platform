# Scalability Guide

## Immediate Scaling Levers
- Run the API behind multiple workers once the startup path is fully validated.
- Move rate limiting and token/session state into Redis.
- Offload compliance polling and remediation to Celery workers.

## Data Layer
- Add indexes for high-cardinality filters and audit queries.
- Introduce retention and archival policies for time-series and audit tables.
- Keep read-heavy dashboards on cache-backed aggregate endpoints.

## Frontend
- Lazy-load route modules and split large charting code paths.
- Cache dashboard data with react-query and interval-aware refreshes.

## Operational Guardrails
- Alert on API latency, queue depth, worker failures, and Redis saturation.
- Use canary rollouts with health-gated rollback.