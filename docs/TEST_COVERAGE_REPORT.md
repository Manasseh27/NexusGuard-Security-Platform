# TEST_COVERAGE_REPORT.md
# NexusGuard Security Platform — Test Coverage Analysis
_Manual code audit of test suite. No coverage tooling run (no live environment)._

---

## Current Test Inventory

### `tests/unit/test_compliance_engine.py`
**Coverage: GOOD**

| Test Class | Tests | What Is Covered |
|------------|-------|-----------------|
| `TestCISRule_1_1_EnableAAA` | 6 | Full AAA pass/fail, partial config, score zero/nonzero |
| `TestCISRule_1_2_EnableSecretEncryption` | 6 | type5/8/9 secrets, cleartext, missing, severity check |
| `TestCISRule_2_1_SSHv2Only` | 6 | Telnet allowed, SSH v1, weak RSA key, evidence dict, remediation steps |
| `TestComplianceOrchestrator` | 9 | Report generation, scoring comparison, pass/fail counts, baseline delta, timeout handling, control summaries, content hash determinism, critical failures |
| `TestComplianceRuleRegistry` | 4 | Built-in rules, get by ID, unknown rule, custom rule registration |

**Total unit tests: ~31**  
**Gaps in this suite:** No tests for `OPAPolicyEvaluator`, `NIST_CSF`/`PCI_DSS`/`ISO_27001` frameworks, concurrent evaluation races.

---

### `tests/unit/test_services_and_security.py`
**Coverage: UNKNOWN** — file exists but not read in this audit. Likely covers security utilities and service layer. Needs verification.

---

### `tests/integration/test_api_endpoints.py`
**Coverage: WEAK**

| Test Class | Tests | Problems |
|------------|-------|----------|
| `TestAuthenticationEndpoints` | 3 | Assertions accept `[200, 401, 422]` — passes even on complete failure |
| `TestDeviceEndpoints` | 3 | Wrong URL `/api/v1/devices/devices` (should be `/api/v1/devices`) |
| `TestComplianceEndpoints` | 3 | `drift/active` expects `list` but returns `dict` with `{total, drifts}` |
| `TestMonitoringEndpoints` | 3 | Weak assertions — all accept 404 as passing |
| `TestSIEMEndpoints` | 3 | Missing `source` field in submit_event test will get 422 |
| `TestSecurityHeaders` | 2 | No assertions on actual header values |
| `TestRateLimiting` | 2 | No actual rate limit enforcement test |
| `TestSecurityEndpoints` | 2 | Oversized payload test uses wrong approach |
| `TestEndpointAvailability` | 2 | Health endpoint path wrong (`/api/v1/health/ready` — correct) |

**Total integration tests: ~23**  
**Key Problems:**
1. `demo_devices` fixture uses `device_type="router"` (invalid) — all device tests will fail
2. `authenticated_client` tries to login with `admin`/`admin123` — fails without demo data seeded
3. Most assertions accept 404/401 as success — tests pass even when endpoints are broken
4. URL for devices is wrong: `/api/v1/devices/devices` should be `/api/v1/devices`

---

## What Is NOT Tested

### Authentication (Critical — No Tests)
| Scenario | Tested |
|----------|--------|
| Registration → email verification → login flow | ❌ |
| Password reset full flow (request → reset) | ❌ |
| Account lockout after 5 failed attempts | ❌ |
| Token revocation (logout) | ❌ |
| Refresh token rotation | ❌ |
| Session listing and revocation | ❌ |
| JWT with revoked jti rejected | ❌ |

### RBAC (Critical — No Tests)
| Scenario | Tested |
|----------|--------|
| Viewer cannot access write endpoints | ❌ |
| Analyst cannot access admin endpoints | ❌ |
| Admin can access all endpoints | ❌ |
| Invalid permission string rejected | ❌ |
| Cross-tenant isolation | ❌ |

### Incident Flow (No Tests)
| Scenario | Tested |
|----------|--------|
| Create → Assign → Investigate → Resolve → Close | ❌ |
| Timeline entries created on status change | ❌ |
| Notification created on assignment | ❌ |
| Comment added to incident | ❌ |

### Notification Flow (No Tests)
| Scenario | Tested |
|----------|--------|
| Notification created on incident assignment | ❌ |
| Mark notification as read | ❌ |
| List unread notifications | ❌ |

### Compliance Flow (Partial)
| Scenario | Tested |
|----------|--------|
| Compliance rule evaluation (unit) | ✅ |
| Score calculation from results | ❌ |
| Drift detection | ❌ |
| Exception creation | ❌ |
| Acknowledge drift | ❌ |
| Fleet summary | ❌ |

### Infrastructure (No Tests)
| Scenario | Tested |
|----------|--------|
| Redis connection failure graceful degradation | ❌ |
| DB connection pool exhaustion | ❌ |
| Celery task retry on failure | ❌ |

---

## Required Test Files to Create

### Priority 1 — Auth Tests
**File:** `tests/unit/test_auth_flow.py`
- Test login success/failure
- Test account lockout
- Test token refresh
- Test logout + revocation
- Test password reset flow
- Test email verification flow
- Test password policy enforcement

### Priority 2 — RBAC Tests
**File:** `tests/unit/test_rbac.py`
- Test `require_permission()` for each role
- Test wildcard permission for admin
- Test cross-role permission denial
- Test role alias normalization

### Priority 3 — Incident Tests
**File:** `tests/integration/test_incidents.py`
- Test full incident lifecycle (create → close)
- Test assignment creates notification
- Test timeline populated on each state change
- Test comment creation

### Priority 4 — API Contract Tests
**File:** `tests/integration/test_api_contracts.py`
- Fix existing integration tests (wrong URLs, weak assertions)
- Test response schema matches TypeScript types
- Test pagination parameters

---

## Test Infrastructure Issues to Fix

1. **`conftest.py` `demo_devices` fixture** — change `device_type="router"` to `device_type="generic"`
2. **`conftest.py` `authenticated_client`** — add user creation before login attempt
3. **`conftest.py` `demo_user`** — `role="analyst"` is a string, should be `UserRole.ANALYST` or `"analyst"` (valid enum)
4. **Integration test device URL** — `/api/v1/devices/devices` → `/api/v1/devices`
5. **SIEM submit test** — add `"source": "test"` to the event payload

---

## Estimated Coverage (Current)

| Domain | Unit | Integration | Total |
|--------|------|-------------|-------|
| Compliance Engine | ~80% | ~10% | ~50% |
| Authentication | 0% | ~20% (weak) | ~5% |
| RBAC | 0% | 0% | 0% |
| Incidents | 0% | 0% | 0% |
| Notifications | 0% | 0% | 0% |
| Devices | 0% | ~15% | ~5% |
| SIEM | 0% | ~15% | ~5% |
| Reports | 0% | 0% | 0% |
| Monitoring | 0% | ~15% | ~5% |
| Audit | 0% | 0% | 0% |
| Security Middleware | 0% | ~10% | ~5% |
| **Overall** | | | **~10–15%** |

Production-grade minimum target: **80% on critical paths (auth, RBAC, incidents, compliance)**.
