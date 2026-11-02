# Branch Office handover

## Run the whole application locally

Requirements: Docker Desktop with its Linux engine running and Git. The full-stack override builds the React bundle and Python API in one non-root image, migrates the existing database, starts the website, and runs hourly maintenance.

```powershell
docker compose -f compose.yaml -f compose.app.yaml up -d --build
docker compose -f compose.yaml -f compose.app.yaml ps
docker compose -f compose.yaml -f compose.app.yaml logs --tail 30 maintenance
```

Open http://localhost:18080. Staff use http://localhost:18080/staff. Local credentials in Compose are development-only; these services bind to loopback. Existing database volumes are retained. Do not run `down -v` against a database you intend to keep.

For a fresh local database, explicitly seed synthetic accounts/catalogue after migration; seeding preserves existing accounts/passwords and content rather than overwriting them:

```powershell
docker compose -f compose.yaml -f compose.app.yaml exec app python -m app.seed --demo
docker compose -f compose.yaml -f compose.app.yaml exec app python -m app.public_seed --demo
```

The five local demo accounts are `admin@example.test`, `finance@example.test`, `branch@example.test`, `hr@example.test` and `editor@example.test`, password `Demo123!`. Only seed these in local demonstration environments. A demo Branch Lead needs an Active branch assignment before writing finance data. Public volunteer membership and staff login accounts remain separate.

For development, run PostgreSQL/Redis with `docker compose up -d`, then the API using `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from backend and `npm run dev` from frontend. If 8000 is occupied, use 8001 and set `API_PROXY_TARGET=http://127.0.0.1:8001` in the frontend process environment before starting Vite. The development frontend defaults to 5173.

## Architecture

The same-origin deployment serves a built React/TypeScript SPA and FastAPI from one container. Public fonts are self-hosted with their SIL licences. Staff code loads only on staff routes, and public static JS/CSS uses gzip without compressing private API data. Explicit public/staff SPA paths support refresh without intercepting unknown API paths or method 405 responses. PostgreSQL is the authoritative relational ledger; SQLAlchemy services own business rules and request handlers commit state/audits together. Alembic versions schema changes. Redis provides shared API/auth rate limits. No banking/payment, email or external machine-translation service is integrated.

Principal records: users/sessions/security events; branches/history; public programmes/events/messages; applications/member records/history; collections/history; transfer batches/allocations/history; weekly reports/submission revisions/history; separate content drafts/published copies/revisions. Existing source IDs are reused rather than creating competing public/private branch registers.

Readiness checks database/schema head and Redis; liveness is independent. Cookie sessions, bcrypt, CSRF/origin checks, forced temporary-password replacement and backend role/scope checks remain authoritative. Production adds secure cookies, HSTS and CSP. A client-side hidden control never grants access.

## Permission matrix

| Module | Super Admin | Finance Reviewer | Branch Lead | HR Lead | Content Editor |
| --- | --- | --- | --- | --- | --- |
| Staff accounts | Create/reset/manage | Denied | Denied | Denied | Denied |
| Branch register | Manage all | Denied | Read current assignment | Denied | Denied |
| Applications/members | Manage all | Denied | Denied | Manage all | Denied |
| Collections | Read all | Read all | Create/edit current Active branch before deadline | Denied | Denied |
| Transfers | Read all | Confirm/return independently | Submit/resubmit current Active branch; cancel Submitted/Returned | Denied | Denied |
| Weekly reports | Read all | Approve/return independently | Edit/submit current Active branch | Denied | Denied |
| Finance dashboard/exports | Read all | Read all | Current assignment only | Denied | Denied |
| Website content | Manage/publish | Denied | Denied | Denied | Manage/publish |

Anonymous users see only published public data and may submit validated contact/volunteer forms. Finance safe branch selectors do not confer HR/branch-admin access. Former branch leads lose read/write/export access. Finance cannot review a report it previously submitted, even following a role change. Finance may settle an existing submission after branch pause/closure; Admin has no hidden finance override.

## Financial definitions and workflow

Amounts are PKR, exact database numerics and decimal JSON strings. UI selection sums use integer cents. Collection edits end at immutable server `created_at + 168 hours`; collected_on remains a separate business date. No deletion/unlock/admin correction bypass exists.

Transfers select1–100whole, unallocated collections only after that deadline. Submitted reserves the batch; Finance confirms receipt or returns with a reason. Returned releases allocations; resubmission requires every original item still available. Cancellation releases; Confirmed/Cancelled are terminal. Submission does not imply bank receipt.

Cumulative reconciliation: `recorded = not_submitted + awaiting_confirmation + confirmed_received`. Eligible is the unallocated subset past its editing deadline; not_submitted also includes still-editable receipts. Date-filtered dashboard charts and collection totals are distinct from this cumulative balance.

Reporting weeks are Monday 00:00 to next Monday 00:00 Asia/Karachi, end exclusive. Period collections use collected_on; transfers use transferred_on. Transfer statuses are as-of snapshot, not reconstructed historical week-end state. Draft/Returned preview live figures. Closed-week submission freezes a source-ID/revision/value snapshot and narrative revision. Finance Return permits a new submission revision; approval checks full current source membership/values under shared branch locking and rejects changes with HTTP 409. Approved reports are immutable, with later ledger differences visibly flagged.

The report register omits large source snapshots; detail/revisions/exports provide evidence. Complete previews/submissions are bounded at 10,000 sources, with an explicit error instead of partial totals. If later additions exceed the bound, a stale submission can still be returned; its last submitted figures are labelled, and resubmission is unavailable until a complete preview is possible. No reopening/replacement-report correction workflow is included.

## Main API map

Development OpenAPI: `/docs` and `/openapi.json`; production hides both. Existing authentication/staff operations are documented in SECURITY.md.

| Prefix | Main operations |
| --- | --- |
| /api/public/catalog | Anonymous published branches/programmes/events/page introductions |
| /api/public/messages, /api/public/volunteers | Validated idempotent submissions |
| /api/branches | Registry, lifecycle, lead assignment, publication and audit |
| /api/applications, /api/members | Review, acceptance/member creation and member maintenance |
| /api/collections | Scoped register/detail, create, /update, /audit and /branches |
| /api/transfers | Scoped register/detail, /eligible, /balances, create, /confirm, /return, /cancel, /resubmit, /audit |
| /api/reports | Register/detail, /narrative, /submit, /approve, /return, /audit, /revisions, /export.csv, /export.pdf |
| /api/dashboard | Scope/date-filtered ledger/monthly/outstanding/report overview; /export.csv |
| /api/content | Register/create/detail, /branches, /draft, /preview, /publish, /unpublish, /history |

Mutations use current expected_version and explicit reason where applicable. Report Finance decisions require acknowledgement. Safe creation retries retain request UUIDs. HTTP 409 preserves forms until explicit reload; HTTP 401 returns the shell to login and discards private forms. Export 422/network errors stay visible without navigating away. CSV is complete within documented bounds, UTF8/BOM/quoted, with spreadsheet formula guards. PDF embeds licensed Latin/Arabic fonts and shapes Urdu; unsupported characters return 422 and offer lossless CSV rather than silently dropping text.

## Content operations

Use `/staff/content` to create/edit a bilingual programme, event or Home/About/Contact introduction. Saved draft and current published copy are distinct. Preview is protected. Explicit publish copies the validated draft atomically; editing it never leaks into the current public copy. Unpublish retains drafts/history. Events remain subject to their branch's Active+published state. Plain text is rendered as text, including HTML-like input. Existing samples are labelled; no rich HTML, uploads or automatic translation provider is enabled.

## Scheduled operations

```powershell
docker compose -f compose.yaml -f compose.app.yaml exec app python -m app.maintenance --once
# Explicit historical backfill starts on a Monday; generation is bounded/retry-safe.
docker compose -f compose.yaml -f compose.app.yaml exec app python -m app.maintenance --once --from-week 2026-10-26
```

The local maintenance service runs immediately and hourly. The Render cron runs at minute 5 of every hour UTC. It generates at most 100 missing branch/week drafts per transaction, starting at branch registration week unless backfill is requested, and runs existing expired-session/90-day correspondence cleanup. Retried/multiple workers cannot duplicate drafts. Large backlogs need repeated bounded runs. Approved reports are never regenerated. Worker failures log their type and retry next interval; cron exits nonzero on failure. Monitor job success/backlog and Redis memory. The worker has no HTTP listener and intentionally has no inherited web healthcheck.

## Render deployment

`render.yaml` is a reviewable Blueprint for the image web service, PostgreSQL 16, Key Value and hourly cron. Automatic deployment is off, branch main is explicit, database external access is disabled and production hosts/origins must be supplied as JSON arrays for the actual HTTPS hostname. It uses current plan IDs from Render's documentation; plans are billable. Review costs and region in the Render dashboard before creating services. No hosted service has been provisioned by this work.

1. Commit/review/PR the intended version through dev→main; user controls history and PRs. Verify actual GitHub CI, including the image smoke job.
2. Connect the repository to Render and review the Blueprint. Supply ALLOWED_HOSTS such as `["your-service.onrender.com"]` and ALLOWED_ORIGINS such as `["https://your-service.onrender.com"]`. Use generated production secrets, never local Compose credentials.
3. Web pre-deploy runs `python -m alembic upgrade head`. Readiness refuses mismatched schema. Start with the image command and assigned PORT; do not enable the dev reloader.
4. Bootstrap the first Super Admin interactively with `python -m app.bootstrap` in the service shell. Share temporary credentials privately and require first-login replacement. Do not seed demo accounts or illustrative catalogue data in production.
5. Verify HTTPS cookie/CSRF/origin behaviour, all roles, static route refresh, readiness, reports, exports, publication and cron logs on the live hostname. Confirm the reverse proxy's trusted-client-IP configuration before relying on per-IP limits; do not blindly trust user-supplied forwarding headers.
6. Record the actual live URL and judged commit hash after those checks. A prepared Blueprint/local image is not a live deployment result.

References: [Render Blueprint](https://render.com/docs/blueprint-spec), [Docker on Render](https://render.com/docs/docker), [fpdf2 text shaping](https://py-pdf.github.io/fpdf2/TextShaping.html), [fpdf2 patched release 2.8.8](https://github.com/py-pdf/fpdf2/releases/tag/2.8.8).

## Backup, recovery and releases

Take a PostgreSQL backup before schema changes using the provider's snapshot facility or `pg_dump --format=custom --no-owner --no-acl`; supply credentials through a secret manager/environment, not command history. Encrypt backups, restrict access and apply retention consistent with correspondence/member policy. Restore into an isolated database first with `pg_restore`, migrate to the matching application version, then check readiness, record counts and sample reconciliations before changing a live connection. A Redis restart expires rate counters; PostgreSQL sessions remain authoritative.

Deploy application/schema versions together. Prefer forward fixes and additive migrations. Rolling back an image is safe only if the schema stays compatible. Never downgrade a production schema merely to undo a release; test recovery on a separate restore and retain immutable audits. CI downgrade/re-upgrade tests use disposable `_test` databases only.

## Acceptance and external inputs

See [ACCEPTANCE.md](ACCEPTANCE.md) for the measured local verification results and external acceptance gaps. Automated and browser evidence is recorded under `.venv` locally and the completion execution ledger under docs. It proves synthetic fixtures and observed workflows, not a complete production security/accessibility certification. Original business data is retained; browser-only synthetic programmes/branches/reports/transfers are clearly labelled and audited.

Before final submission, the user still needs official organiser sample data/expected dashboard values, organisation-approved public copy/assets and any surprise-task requirements; actual Render account/launch and live checks; actual main CI/PR status; genuine qualifying commit history; and the user's own-voice video/final hash. Do not fabricate these. The repository's existing `.gitignore` excludes docs/Context; this tracked root handover provides essential operations/permission/API information without changing that policy. Explicitly include any ignored formal docs the user chooses to submit.
