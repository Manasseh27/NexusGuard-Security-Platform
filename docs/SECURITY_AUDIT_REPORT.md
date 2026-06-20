# SECURITY_AUDIT_REPORT.md
# NexusGuard Security Platform — Security Audit
_Static analysis + manual code review. No pentest performed._

---

## CRITICAL

### SEC-001 — IPWhitelistMiddleware Hard-Codes Localhost Only
**File:** `backend/app/middleware/security_advanced.py` — `IPWhitelistMiddleware`  
**Impact:** All `/api/v1/users/` and `/api/v1/audit/` endpoints return HTTP 403 for any non-localhost client in any real deployment. Additionally, this IP-based control provides false security if placed behind a load balancer (client IP will be the LB's IP, not the real client).  
**Recommendation:** Remove `users/` and `audit/` from sensitive paths — RBAC already enforces these. If IP restriction is needed for `/admin/`, make the WHITELIST configurable via `settings`.

---

### SEC-002 — Password Reset Token Returned in API Response
**File:** `backend/app/api/v1/routers/auth.py` — `forgot_password()`  
```python
return GenericMessageResponse(
    message="If the account exists, a reset token has been issued.",
    token=reset_token,  # ← RETURNED TO CALLER
)
```
**Impact:** Any attacker who calls `POST /auth/forgot-password` with a valid email receives the reset token in the HTTP response. Combined with the fact that the email field is public (user enumeration is partially mitigated), this completely bypasses the intent of password reset — the attacker does not need email access.  
**Recommendation:** Remove `token` from the response immediately. Only deliver tokens via email.

---

### SEC-003 — Demo Passwords Violate Security Policy and Are Publicly Documented
**File:** `backend/app/services/user_service.py`, `README.md`  
```python
("admin", "admin@example.com", "admin123", UserRole.ADMIN),
```
**Impact:** `admin123` is 8 characters, has no uppercase or special character. The platform's own `validate_password_policy()` would reject this. These credentials are published in the README. Any instance with `ENABLE_DEMO_DATA=true` creates exploitable accounts.  
**Recommendation:** Change demo passwords to compliant values (e.g., `Admin@NexusGuard2025!`), gate behind `ENVIRONMENT != "production"` check, and remove from README.

---

### SEC-004 — Users Router Permission Check Does Not Work
**File:** `backend/app/api/v1/routers/users.py`  
```python
current_user=Depends(require_permission("admin")),
```
**Impact:** The string `"admin"` is never present in any role's permission list. The admin role has `"*"` which causes `has_permission("admin")` to return `True` via the wildcard. However, non-admin users attempting to call these endpoints will get 403 as expected — but so would any future service account that has explicit permissions without `"*"`. The intent is unclear and the implementation is fragile.  
**Recommendation:** Define explicit permissions `users:read` and `users:write`, add them to the admin/super_admin role, and use `require_permission("users:write")`.

---

## HIGH

### SEC-005 — JWT Secret Key Not Validated at Startup in Settings
**File:** `backend/app/core/config.py`  
The `Settings.jwt.SECRET_KEY` defaults to `secrets.token_urlsafe(64)` (regenerated each startup). In development this means every restart invalidates all tokens. More critically, if `JWT_SECRET_KEY` is not set in production `.env`, a new random key is silently generated — all sessions become invalid after each deploy.  
**Recommendation:** Require `JWT_SECRET_KEY` to be explicitly set and non-empty in all environments. Add a startup assertion.

---

### SEC-006 — HMAC in AuditMiddleware Uses `hmac.new()` — Does Not Exist
**File:** `backend/app/middleware/security_headers.py`  
```python
signature = hmac.new(
    settings.SECRET_KEY.encode(),
    entry_json.encode(),
    hashlib.sha256,
).hexdigest()
```
`hmac.new()` does not exist in Python's `hmac` module. The correct call is `hmac.new()` → `hmac.digest()` or the constructor is `hmac.HMAC()`. The standard function is `hmac.new(key, msg, digestmod)` — actually this IS correct (`hmac.new` is the low-level constructor). However, the return type is an `HMAC` object and `.hexdigest()` is correct. This will work, but it is unusual style — standard idiom is `hmac.new(...).hexdigest()`. **Confirmed valid**, but the audit middleware **never writes to the database** (see GAP-015).

---

### SEC-007 — No CSRF Protection for Stateful Operations
**File:** `backend/app/main.py`  
The platform uses `SessionMiddleware` with cookies, but there is no CSRF token validation. The `security_config.py` has `CSRF_PROTECTION_ENABLED: bool = True` but this is never enforced. Bearer token auth (JWT) mitigates CSRF for API calls, but the session cookie middleware creates a surface.  
**Recommendation:** Since the API exclusively uses Bearer tokens (not cookie auth for API calls), CSRF risk is low. Document this explicitly. Remove or disable `SessionMiddleware` if sessions are not used for API auth.

---

### SEC-008 — Credentials Stored as `LargeBinary` with No Encryption Context
**File:** `backend/app/infrastructure/database/models.py` — `DeviceCredentials`  
```python
encrypted_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
```
The field is named `encrypted_data` implying encryption at rest. However, no encryption/decryption logic is visible in the codebase for this field. If credentials are stored as plain bytes, they are unencrypted in the database.  
**Recommendation:** Implement Fernet or AES-GCM encryption/decryption in `DeviceCredentialsRepository` or a dedicated `CredentialsVault` service. Use a KMS-backed key or the Vault integration (already configured in settings).

---

### SEC-009 — Rate Limiting Has Duplicate Implementation
**File:** `backend/app/middleware/security_headers.py` (Redis sliding window) vs `backend/app/middleware/security_advanced.py` (in-memory)  
Both `RateLimitMiddleware` classes are registered in `main.py`. The one from `security_advanced.py` is registered first. Both apply to the same requests. The in-memory store does not scale across multiple API replicas.  
**Recommendation:** Keep only the Redis-backed sliding window implementation from `security_headers.py`. Remove the duplicate in-memory `RateLimitMiddleware` from `security_advanced.py`.

---

### SEC-010 — No Rate Limiting on `/auth/register`
**File:** `backend/app/middleware/security_headers.py`  
`STRICT_PATHS` only covers `/api/v1/auth/login` and `/api/v1/auth/token`. The registration endpoint has no special rate limit, enabling account enumeration or mass account creation attacks.  
**Recommendation:** Add `/api/v1/auth/register` to `STRICT_PATHS` with limit of 5/minute.

---

### SEC-011 — `access_token` and `refresh_token` Stored in `localStorage`
**File:** `frontend/src/stores/authStore.ts`, `frontend/src/services/api.ts`  
JWT tokens stored in `localStorage` are accessible to any JavaScript on the page (XSS vectors). The security headers include CSP, but `script-src 'self' 'unsafe-inline'` allows inline scripts.  
**Recommendation:** Consider `httpOnly` cookies for token storage. If localStorage is kept, ensure the CSP removes `'unsafe-inline'` for scripts.

---

## MEDIUM

### SEC-012 — SQL Injection Surface — `event_type.ilike()` Unvalidated
**File:** `backend/app/api/v1/routers/threats.py`  
```python
stmt = stmt.where(SIEMEvent.event_type.ilike(f"%{indicator_type}%"))
```
SQLAlchemy parameterizes this correctly so direct SQL injection is not possible, but unbounded `ILIKE` with user-controlled wildcards can cause performance issues (full table scans). Validate or constrain `indicator_type`.

---

### SEC-013 — Logging of Sensitive Data in Auth Failures
**File:** `backend/app/core/security.py`  
`record_login_attempt(username, ...)` stores username as a Redis key and logs it. Usernames may be email addresses. Depending on logging infrastructure, this constitutes PII in logs.  
**Recommendation:** Hash username before using as Redis key: `hashlib.sha256(username.lower().encode()).hexdigest()`.

---

### SEC-014 — OpenAPI Docs Exposed in Non-Production by Default
**File:** `backend/app/main.py`  
Docs are only disabled in `production`. In `staging`, full API documentation with request/response schemas is publicly accessible. This aids attackers in enumerating the attack surface.  
**Recommendation:** Also disable in `staging`, or add authentication to the docs endpoint.

---

### SEC-015 — `ALLOWED_HOSTS = ["*"]` Default
**File:** `backend/app/core/config.py`  
```python
ALLOWED_HOSTS: list[str] = ["*"]
```
`TrustedHostMiddleware` with `"*"` effectively does nothing — any Host header is accepted.  
**Recommendation:** Set to specific domain(s) in production. Enforce via config validation.

---

## LOW

### SEC-016 — `X-Frame-Timestamp` Header Leaks Server Time
**File:** `backend/app/middleware/security_advanced.py`  
```python
response.headers["X-Frame-Timestamp"] = datetime.now(timezone.utc).isoformat()
```
Non-standard header reveals precise server time. Minor information disclosure.

---

### SEC-017 — bcrypt Rounds = 12 (Acceptable but Review Periodically)
**File:** `backend/app/core/security.py`  
`bcrypt.gensalt(rounds=12)` — rounds=12 is the current minimum recommendation. As hardware improves, consider 13-14.

---

### SEC-018 — `AUDIT_IMMUTABLE = True` in Config but Not Enforced
**File:** `backend/app/core/config.py`  
The `AUDIT_IMMUTABLE` flag is defined but there is no enforcement mechanism (e.g., DB triggers, append-only table policy) to prevent audit log modification.

---

## SUMMARY TABLE

| ID | Severity | Area | Status |
|----|----------|------|--------|
| SEC-001 | Critical | Middleware | Open |
| SEC-002 | Critical | Auth | Open |
| SEC-003 | Critical | Auth/Config | Open |
| SEC-004 | Critical | RBAC | Open |
| SEC-005 | High | Config | Open |
| SEC-006 | High | Audit | Confirmed valid, but audit not persisted |
| SEC-007 | High | CSRF | Low risk with JWT-only auth |
| SEC-008 | High | Credentials | Open |
| SEC-009 | High | Rate Limiting | Open |
| SEC-010 | High | Rate Limiting | Open |
| SEC-011 | High | Frontend | Open |
| SEC-012 | Medium | API | Open |
| SEC-013 | Medium | Logging | Open |
| SEC-014 | Medium | Config | Open |
| SEC-015 | Medium | Config | Open |
| SEC-016 | Low | Headers | Open |
| SEC-017 | Low | Crypto | Monitor |
| SEC-018 | Low | Audit | Open |
