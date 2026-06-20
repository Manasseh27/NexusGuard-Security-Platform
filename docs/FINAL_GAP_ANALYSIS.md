# FINAL_GAP_ANALYSIS.md
# NexusGuard Security Platform — Gap Analysis
_All gaps identified by recursive code audit. Ordered by priority._

---

## GAP-001 — Missing API Routes (Frontend 404s)
**Priority:** CRITICAL  
**Area:** Backend API

The frontend `api.ts` calls these endpoints which do not exist in any router:

| Frontend Call | Expected Route | Router File |
|---------------|----------------|-------------|
| `monitoringApi.driftEvents()` | `GET /monitoring/drift/events` | `monitoring.py` — missing |
| `monitoringApi.deviceTrend()` | `GET /monitoring/devices/{id}/trend` | `monitoring.py` — missing |
| `complianceApi.frameworkSummary()` | `GET /compliance/frameworks/{fw}/summary` | `compliance.py` — missing |
| `complianceApi.listRules()` | `GET /compliance/rules` | `compliance.py` — missing |

**Fix required:** Add these 4 routes to their respective routers.

---

## GAP-002 — No Email Transport
**Priority:** CRITICAL  
**Area:** Auth / Notifications

- `POST /auth/forgot-password` generates a reset token but **returns it in the API response** (dev hack). No email is sent.
- `POST /auth/register` generates a verification token stored in Redis but never emails it.
- `NotificationService` publishes to broker for `email` channel but no consumer processes it.

**Fix required:** Add an email transport service (SMTP or SES). Notification service needs an email delivery consumer. The reset token must NOT be returned in the API response.

---

## GAP-003 — IPWhitelistMiddleware Production Lockout
**Priority:** CRITICAL  
**Area:** Security Middleware

`security_advanced.py` `IPWhitelistMiddleware` hard-codes whitelist as `["127.0.0.1", "::1"]` and marks `/api/v1/users/` and `/api/v1/audit/` as sensitive paths. In any non-localhost deployment, all user management and audit log endpoints return **403 Forbidden** for everyone.

**Fix required:** Either remove `users/` and `audit/` from sensitive paths (RBAC already protects them) or make the whitelist configurable from settings.

---

## GAP-004 — Demo Users Break Password Policy
**Priority:** CRITICAL  
**Area:** Auth / Security

`user_service.py` `ensure_demo_users()` uses passwords `admin123`, `engineer123`, `analyst123`, `viewer123` — all under the required 12 characters and missing uppercase/special characters. `validate_password_policy()` would reject these. The function is inconsistent: it bypasses policy by calling `create_user()` which calls `hash_password()` without validating policy.

README also publishes these credentials publicly.

**Fix required:** Either (a) update demo passwords to meet policy and treat as development-only with explicit env flag, or (b) remove demo users from README for production deployments.

---

## GAP-005 — Celery Workers Not Running
**Priority:** CRITICAL  
**Area:** Infrastructure

All Celery worker services are commented out in `docker-compose.yml`. The following functionality silently fails:
- `POST /compliance/evaluate/bulk` dispatches to Celery queue — never processed
- `POST /monitoring/devices/{id}/poll` dispatches `run_compliance_eval` — never processed
- Scheduled fleet polling (`poll_fleet_compliance`) — never executes

**Fix required:** Uncomment worker services in docker-compose. Add `celery-beat` for scheduled tasks.

---

## GAP-006 — Auth Routes Missing `db.commit()`
**Priority:** HIGH  
**Area:** Auth

`POST /auth/register`, `POST /auth/verify-email`, `POST /auth/reset-password` all call `db.flush()` but never `db.commit()`. The SQLAlchemy session context manager in `get_db()` must be checked — if it auto-commits on exit, this is fine; if it only flushes, data is not persisted.

**Fix required:** Verify `get_db()` behavior. Add explicit `await db.commit()` after all state-changing operations in auth router.

---

## GAP-007 — ComplianceService `get_all_latest_scores_by_tenant` Query Error
**Priority:** HIGH  
**Area:** Compliance Service

```python
.order_by(ComplianceScore.device_id, ComplianceScore.framework, ComplianceScore.created_at.desc())
.distinct(ComplianceScore.device_id, ComplianceScore.framework)
```
`ComplianceScore` has no `created_at` field — it has `generated_at`. This query will raise `AttributeError` at runtime when any endpoint calls `fleet_summary`, `list_reports`, or `generate_report`.

**Fix required:** Replace `created_at` with `generated_at` in the query.

---

## GAP-008 — conftest.py Invalid DeviceType
**Priority:** HIGH  
**Area:** Tests

`conftest.py` creates `Device(device_type="router", ...)` but `DeviceType` enum has no `"router"` value. Valid values: `cisco_ios`, `cisco_iosxe`, `cisco_iosxr`, `cisco_nxos`, `arista_eos`, `juniper_junos`, `generic`. All integration tests using `demo_devices` fixture will fail with a DB constraint error.

**Fix required:** Change to `device_type="generic"` (or a valid enum value).

---

## GAP-009 — No Password Change Endpoint
**Priority:** HIGH  
**Area:** Auth

`UserService.change_password()` is implemented. `POST /auth/reset-password` uses it for unauthenticated reset. But there is no authenticated `POST /auth/change-password` endpoint for logged-in users to change their own password. This is a standard security requirement.

**Fix required:** Add `POST /auth/change-password` route accepting `current_password` + `new_password`.

---

## GAP-010 — Monitoring Trend Data is Fabricated
**Priority:** HIGH  
**Area:** Dashboard / Monitoring

`useDashboardData.ts` `useRadarData()` generates radar chart data by adding hardcoded offsets (`RADAR_OFFSETS = [3, -5, 2, -7, 4, -9]`) to the fleet score. This is not real per-framework data. The compliance trend panel similarly has no real historical time-series data — the `/monitoring/devices/{id}/trend` endpoint is missing entirely.

**Fix required:** Implement `/monitoring/devices/{id}/trend` endpoint querying `compliance_scores` history. Feed real data to the radar chart via `complianceApi.frameworkSummary()`.

---

## GAP-011 — Frontend Dashboard KPIs May Show Zeros
**Priority:** HIGH  
**Area:** Frontend / Dashboard

`FleetStatusPanel` and `KPICards` depend on `monitoringApi.fleetStatus()` which calls `DeviceService.fleet_status_summary()`. If no devices or no monitoring states exist, all KPIs show 0. There is no loading state differentiated from empty state, and no "seed data" mechanism for demo environments.

**Fix required:** Implement proper empty state UI + wire `ENABLE_DEMO_DATA` flag to call `ensure_demo_users()` and a device seeder on startup.

---

## GAP-012 — Users Router Uses Wrong Permission String
**Priority:** HIGH  
**Area:** RBAC

`users.py` uses `require_permission("admin")` but the permission matrix in `security.py` defines `"*"` for admin, not a literal `"admin"` permission string. The permission `"admin"` is never in any role's permission list. `CurrentUser.has_permission("admin")` will return `False` for all roles including admin — only `"*"` wildcard admins pass.

**Fix required:** Change `require_permission("admin")` to a proper permission like `"users:read"` / `"users:write"` and add those to the admin role's permission list, or use `get_current_user` + a role check.

---

## GAP-013 — No Frontend Notification Bell / UI
**Priority:** MEDIUM  
**Area:** Frontend

`notificationsApi` is defined in `api.ts` and the backend is complete, but there is no notification bell component in the `TopNav` or anywhere in the frontend. Users receive no in-app notifications.

**Fix required:** Add a notification bell to `TopNav.tsx` using `notificationsApi.listMine({ unread_only: true })`.

---

## GAP-014 — No Real-Time Updates
**Priority:** MEDIUM  
**Area:** Frontend / Backend

The frontend uses polling (`useFleetPolling` hook) for monitoring data. There is no WebSocket or SSE connection for real-time alerts or notification push. `SSE streaming` exists for AI chat but not for notifications or drift events.

**Fix required:** Add SSE endpoint for notification streaming, or add WebSocket support for real-time drift alerts.

---

## GAP-015 — Audit Log Never Written to Database
**Priority:** MEDIUM  
**Area:** Audit

`AuditMiddleware` signs entries with HMAC and attempts to publish to the message broker. If the broker is unavailable, it falls back to structured logging. Neither path writes to the `audit_logs` database table via `AuditLogRepository`. The `GET /audit` endpoint queries the DB — it will always return empty results.

**Fix required:** Add a broker consumer (or inline write) that persists `AuditLog` rows to the DB from `AuditMiddleware`.

---

## GAP-016 — No `ENABLE_DEMO_DATA` Startup Hook
**Priority:** MEDIUM  
**Area:** Seeding / DX

`settings.ENABLE_DEMO_DATA` flag exists but is never checked anywhere. `ensure_demo_users()` is never called automatically. A fresh deployment has zero users — login is impossible without manual seeding.

**Fix required:** In `lifespan()` startup, check `settings.ENABLE_DEMO_DATA` and call `ensure_demo_users()`.

---

## GAP-017 — Frontend Pages Not Verified
**Priority:** MEDIUM  
**Area:** Frontend

These pages exist but were not fully audited: `Alerts.tsx`, `Analytics.tsx`, `Devices.tsx`, `Compliance.tsx`, `SIEM.tsx`, `Threats.tsx`, `Users.tsx`, `Copilot.tsx`. Some may contain hardcoded mock data or incomplete API integrations.

**Fix required:** Audit each page to confirm real API calls replace any mock/hardcoded values.

---

## GAP-018 — Report Storage is Ephemeral
**Priority:** MEDIUM  
**Area:** Reports

Generated reports are stored in Redis with a 7-day TTL. `list_reports` derives virtual reports from compliance scores (no Redis). `get_report` requires Redis — if Redis restarts without persistence, all generated reports are lost.

**Fix required:** Store reports in the database (add a `reports` table) or enable Redis persistence (`appendonly yes`).

---

## GAP-019 — No `GET /monitoring/drift/events` Pagination
**Priority:** LOW  
**Area:** API

Once GAP-001 is fixed and the drift events route is added, it should support proper pagination consistent with other list endpoints.

---

## GAP-020 — `.env` Contains Default Secrets
**Priority:** LOW (dev only)  
**Area:** Security

`.env.example` has `SECRET_KEY=change-me-to-a-random-64-char-string`. The current `.env` file (committed to repo as per directory listing) may contain these placeholders. In production, all secrets must be rotated before deployment.

**Fix required:** Add `.env` to `.gitignore` (it appears to be tracked). Verify `.gitignore` excludes it.
