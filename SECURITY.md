# Authentication and staff account operations

## Implemented scope

The current feature provides administrator-created accounts, login/logout, current-user restoration, temporary passwords, password change/reset and reusable role guards. It does not implement the branch membership model or the full organisation permission matrix. No public signup, invitation email, password-recovery email or JWT flow exists.

Users are stored in PostgreSQL. New passwords use bcrypt cost 12. Existing Argon2 hashes remain verifiable and migrate to bcrypt after a successful eligible login; existing passwords are never reset to migrate them. Bcrypt passwords are limited to 72 UTF-8 bytes, never silently truncated. New passwords require at least 15 characters; spaces and Unicode are accepted, embedded NUL is rejected. An existing Argon2 password beyond bcrypt's byte limit remains Argon2 until changed.

## Local startup

From the repository root:

```powershell
docker compose up -d --wait db redis
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --no-proxy-headers
```

Preserve your existing backend/.env. New configuration defaults work with the local Compose services; backend/.env.example lists explicit development values. Start the frontend separately using `npm ci` and `npm run dev` inside frontend. Existing local demo logins remain valid; no frontend credential autofill is included.

## Creating accounts

1. Sign in as Super Admin, then open Manage staff accounts.
2. Enter the person's name, existing email, role and temporary password.
3. Keep the temporary password available before submitting; it is hashed, never returned and cannot be retrieved. Share credentials directly through your chosen channel.
4. The recipient signs in, then changes their password before accessing ordinary APIs. Temporary passwords expire after 48 hours.
5. For forgotten/expired credentials, select Reset password for that account. Existing sessions are revoked, a new temporary password is set and first-login change is required again. Reset does not reactivate disabled users. To change your own password, use Change password instead of the administrative reset action.

Branches are not yet modelled; this screen does not promise branch isolation. Staff cannot self-select roles or call provisioning/reset endpoints unless their current account is an unrestricted Super Admin.

## First administrator and maintenance

On an installation without any Super Admin, run from backend:

```powershell
..\.venv\Scripts\python.exe -m app.bootstrap
```

This is interactive, accepts no password command argument, refuses a second bootstrap and requires a first-login password change. Complete that change before the temporary credential expires. Keep another authorised Super Admin available for account recovery; there is no public bootstrap/reset backdoor. An installation where every administrator has lost/expired credentials requires an authorised database operator's recovery procedure, not public signup.

To remove expired session rows periodically:

```powershell
..\.venv\Scripts\python.exe -m app.cleanup_sessions
```

Expiry is enforced on requests even before cleanup. Run cleanup as an operator/scheduled deployment task. Never put migration downgrade/reset/seed commands into application startup. `python -m app.seed --demo` remains development-only, adds only missing synthetic accounts and is refused in production.

## Session and HTTP protections

- Opaque bearer session token in an HttpOnly cookie; only its SHA-256 digest is stored in PostgreSQL. Tokens never enter localStorage/sessionStorage or JSON responses.
- Authenticated expiry: 30 minutes idle, 8 hours absolute. Anonymous pre-login sessions expire after 15 minutes. Login/password change rotates tokens; logout/password reset revokes server-side sessions. Current account status, credential version and role are checked at access time.
- Synchronizer CSRF token is bootstrapped over same-origin JSON, kept in React memory and required in X-CSRF-Token on unsafe requests, together with an exact configured Origin check. No Origin/null/untrusted origins are rejected on unsafe browser API actions.
- All registered `/api` routes inherit authentication by default. Only GET /api/csrf and POST /api/login are public. Required-password-change sessions cannot access ordinary protected APIs. Health endpoints remain public.
- Shared Redis limits: 120 API requests/minute/IP; 10 login attempts/minute/IP; 5 login attempts/minute/normalized-account-IP; 20 CSRF bootstrap requests/minute/IP. 429 includes Retry-After; the UI shows retry information. General and narrower limits both apply.
- Limits run before application database dependencies/password work. Redis failure returns generic 503 rather than disabling protection. PostgreSQL errors and input validation are sanitized; streamed request bodies are capped at 1 MiB, independent of Content-Length.
- Security/no-store headers, explicit allowed hosts/origins and production cookie validation are configured. Account creation, reset, password change and successful login/logout have database security-event records without credentials. A complete organisation-wide audit trail remains future work.

## API contracts

| Endpoint | Access and result |
| --- | --- |
| GET /api/csrf | Public; creates/reuses anonymous or authenticated session; returns csrf_token |
| POST /api/login | Origin + CSRF + limits; email/password; returns profile + rotated csrf_token and sets cookie |
| GET /api/me | Authenticated; current id/name/email/role/must_change_password |
| POST /api/logout | Authenticated + Origin + CSRF; revokes session, clears cookie, 204 |
| POST /api/change-password | Authenticated + Origin + CSRF; current_password/new_password/confirm_password; rotates session, returns updated profile + csrf_token |
| GET /api/staff?offset=0&limit=25 | Unrestricted Super Admin; paginated profiles, limit 1–100 |
| POST /api/staff | Unrestricted Super Admin + Origin + CSRF; name/email/role/temporary_password; 201 profile, 409 duplicate email |
| POST /api/staff/{id}/reset-password | Unrestricted Super Admin + Origin + CSRF; temporary_password; 204 |
| GET /health | Process liveness; no database/Redis query |
| GET /health/ready | PostgreSQL migrated schema + Redis availability |

Generic credential failures are 401; authorization/CSRF denials 403; oversized bodies 413; invalid input 422; dependency outages 503. Credentials/CSRF belong in request bodies/headers, never URLs.

## Production configuration

Set ENVIRONMENT=production, COOKIE_SECURE=true, a random RATE_LIMIT_SECRET of at least 32 characters, HTTPS ALLOWED_ORIGINS (JSON list), explicit ALLOWED_HOSTS (JSON list), DATABASE_URL and REDIS_URL through the hosting provider. The production cookie is __Host-branch_session, Secure/HttpOnly/SameSite=Lax, Path=/, with no Domain. Local HTTP uses branch_session_dev. Do not enable production mode with public demo credentials in the database; development seed refusal does not remove existing accounts.

Prefer one origin for UI/API. Separate-origin deployment requires deliberate credentialed CORS, compatible cookie behavior and frontend request configuration; it is not the default. Interactive API docs/OpenAPI are disabled in production. TLS terminates at the trusted hosting proxy; HSTS is sent in production.

Use --no-proxy-headers for direct local execution. Before deploying behind Render, identify and explicitly configure trusted proxy addresses in Uvicorn and verify that requests map to the actual client IP. Do not use wildcard forwarding trust or accept arbitrary X-Forwarded-For headers. Without this deployment step, all users may share a proxy's rate-limit bucket. Redis/Python timeouts are bounded; application rate limits are not a replacement for host/edge resource protection.

## Testing

Use a dedicated PostgreSQL database ending _test and Redis test database/unique namespace. Tests remove only their own expiring keys, never FLUSHDB. From backend:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://branch_office:local_dev_password@localhost:5432/branch_office_test'
$env:TEST_REDIS_URL='redis://localhost:6379/2'
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
```

From frontend: `npm test` and `npm run build`. CI runs real PostgreSQL/Redis, migration checks and the backend coverage gate. Tests cover session/CSRF behavior, role denials, temporary credentials, hashing compatibility, rate limits, dependency outages, malformed/oversized input, cookie flags, production settings and concurrency. Production deployment and full business-feature security must be validated separately.
