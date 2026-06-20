# API Documentation

## Authentication
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`

## Health
- `GET /health/live`
- `GET /health/ready`
- `GET /health/detailed`

## Primary Domains
- Monitoring: fleet, devices, trends, drift events.
- Compliance: scores, frameworks, active drift, rules.
- Users: list, create, update, delete, role management.
- SIEM: ingest, list, correlate, health.
- Audit: list and lookup audit events.
- AI: chat, explain, summarize, provider health.
- Reports: list, generate, download.
- Threats: indicators, CVEs, summary.

## Notes
- The live schema is exposed through FastAPI OpenAPI in non-production environments.
- Frontend requests use bearer JWT access tokens plus refresh-token fallback.