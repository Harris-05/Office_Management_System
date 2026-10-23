# Project decisions

Last updated: 22 October 2026.

This file records agreed project decisions. Approval of a design does not mean its implementation is complete. The assignment brief remains in Task.md; current progress is tracked in Context.md.

## 1. Git branch policy

**User instruction:** Keep work on `feature/basic-login`. Do not create additional branches until the user explicitly asks.

- Switched back to `feature/basic-login`.
- Fast-forwarded it to include the existing database commit `836444f` so completed work is preserved without rewriting history.
- The previously created `feature/database-foundation` branch still exists; it has not been deleted.
- Do not create a worktree on a new branch as a workaround for this instruction. Remain in the current checkout unless the user requests otherwise.
- The earlier feature -> dev -> main PR workflow remains the integration approach, subject to this explicit restriction on creating branches.

## 2. Application stack

- Backend: Python and FastAPI.
- Frontend: React, TypeScript and Vite.
- Database: PostgreSQL, accessed through SQLAlchemy 2.
- Schema changes: Alembic migrations, applied explicitly rather than creating tables at application startup.
- Local database: Docker Compose with persistent storage.
- CI: GitHub Actions, including backend tests/coverage, migration checks and frontend builds.
- Required deployment target: Render; deployment is not implemented yet.
- Current frontend styling uses plain CSS. Tailwind was proposed earlier but has not been adopted.

## 3. Database engineering

Implemented foundation:

- User accounts live in PostgreSQL rather than an in-memory dictionary.
- Database constraints enforce normalized unique emails and valid system roles.
- Keep configuration, session lifecycle, models, HTTP handlers and account logic separated.
- Use request-scoped database sessions and explicit transactions for writes.
- Demo seeding is explicit and idempotent; preserve existing users, names, roles and passwords on reruns.
- Integration tests use a separate PostgreSQL database and roll back test transactions. Do not fall back to the application database or SQLite.
- Future branch, member and finance tables will be added with reviewed migrations when their workflows are designed.

## 4. Authentication approach

**Approved:** Server-side session cookies rather than JWT access/refresh tokens for this first-party browser application.

Approved design: [API security and session-cookie design](docs/superpowers/specs/2026-10-22-api-security-design.md).

Implementation is pending:

- Store sessions in PostgreSQL; send only an opaque random session token in an HttpOnly cookie.
- Store a digest of the bearer session token, not the raw token, in the database.
- Production cookies use Secure, SameSite=Lax, Path=/, no Domain and a __Host- name. Explicit localhost development configuration uses a different cookie name without Secure.
- Authenticated sessions expire after 30 minutes idle or 8 hours total. Anonymous pre-login sessions expire after 15 minutes.
- Rotate the session and CSRF token on successful login; revoke the server-side session on logout.
- Restore the authenticated user after page refresh through `/api/me`; do not store session tokens in browser localStorage/sessionStorage.
- Check the current user's active status and role on authenticated requests.
- Make session rotation, revocation and activity updates safe under concurrent requests.

## 5. Password hashing

**User choice:** bcrypt for new password hashes. Password hashing is one-way; this is not reversible encryption.

Implementation is pending:

- Start with bcrypt cost 12, configurable with a minimum of 10 and performance verification.
- Enforce the 72-byte UTF-8 limit for bcrypt without silent truncation.
- Keep verification of existing Argon2 hashes during migration. Rehash to bcrypt after successful eligible logins; never reset existing passwords to migrate them.
- Existing Argon2 passwords exceeding bcrypt's byte limit retain Argon2 verification until a password-change/reset flow exists.
- Conditional hash updates must not overwrite concurrent password changes.
- Do not reveal passwords/hashes in responses, logs or validation errors. Unknown/inactive accounts receive generic credential failures with hashing work on those paths.

The current implementation still uses Argon2. The approved bcrypt change has not been applied yet.

## 6. Rate limiting

**Approved:** Redis-backed shared, atomic limits rather than independent in-memory counters per worker.

Approved initial configurable defaults, pending implementation:

| Scope | Limit |
| --- | --- |
| General `/api` requests | 120 per minute per trusted client IP |
| Login | 10 attempts per minute per trusted client IP |
| Login account/IP pair | 5 attempts per minute |
| CSRF bootstrap | 20 requests per minute per trusted client IP |

- Return HTTP 429 with Retry-After when a limit is exceeded.
- A Redis outage returns a generic 503 for gated API requests; do not silently disable protection.
- Normalize account keys consistently and avoid raw emails in Redis keys.
- Do not trust arbitrary forwarded-IP headers; proxy trust must be configured explicitly for the deployment.
- Keep process liveness independent of Redis/database availability; readiness checks report dependency failures.

## 7. API and browser protection

Approved, pending implementation:

- Require authentication centrally by default for `/api`, with an explicit public method/path allowlist for login and CSRF bootstrap.
- Require CSRF tokens and exact allowed-origin checks on unsafe browser requests, including login/logout.
- Add reusable backend role guards; frontend visibility alone is not authorization.
- Define branch permissions separately before implementing branch-scoped operations. A stored role alone does not prove access rights.
- Use explicit allowed hosts/origins; no wildcard credentialed CORS or default production secrets.
- Enforce request-size limits on actual streamed bytes and sanitize errors/input validation output.
- Add appropriate security/no-store headers, production HTTPS controls and safe security-event logging.
- Disable public interactive API docs by default in production.
- Exclude demo credential shortcuts/constants from production frontend artifacts and refuse demo seeding in production mode.

## 8. Verification and implementation workflow

- Use the requested agent skills for design, implementation planning, test-first development, review and verification.
- The user approved the security design on 22 October 2026. Do not ask for approval of that same design again unless scope changes materially.
- Prepare the implementation plan next and respect the user's branch instruction throughout.
- Extend Compose and CI with Redis and real integration tests. Retain the minimum 60% backend coverage gate.
- Verify password migration, session/CSRF behavior, role denial, distributed rate limits, expiry/revocation races, dependency failures, input redaction, migrations and frontend login/logout restoration.
- Do not describe approved or planned protections as implemented until code and verification support that claim.

## Remaining decisions

### Staff provisioning update

The user selected Super Admin-created staff accounts with directly shared credentials. Do not add email delivery, emailed invitations or public staff signup. The email is an account identifier, not a mailbox created by this application. The administrator assigns the role; staff cannot self-select access.

See [staff account creation design](docs/superpowers/specs/2026-10-22-staff-account-creation-design.md). The user approved temporary passwords, mandatory first-login password change, 48-hour expiry and administrator resets on 22 October 2026. Both this flow and the previously approved security foundation remain pending implementation. The implementation plan is at docs/superpowers/plans/2026-10-22-secure-staff-accounts.md.

The detailed organisation permission table, branch membership model, financial reporting rules, official sample data and deployment-specific hosts/origins/proxy settings are still outstanding. Approval of this authentication design does not settle them.
