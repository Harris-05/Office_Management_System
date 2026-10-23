# PostgreSQL setup and development

## Design

The API now authenticates against PostgreSQL instead of an in-memory account dictionary. SQLAlchemy 2 models describe persisted records; Alembic migrations version the schema. Routes handle HTTP validation and responses, `users.py` contains account lookup/authentication logic, and `database.py` owns engine/session lifecycle. This keeps persistence separate from the UI and request handling without adding unnecessary abstraction layers.

Each request gets a short-lived session. Reads do not commit; write operations own explicit transactions and commit only when the complete operation succeeds. Closing a session rolls back uncommitted work. Connection pooling is bounded and checks stale connections before reuse. This synchronous database access runs in FastAPI's worker threads through regular `def` endpoints/dependencies.

The schema contains staff **users**, server-side **auth_sessions**, and **security_events** for authentication/account operations. User rows have a UUID primary key, unique normalized email, display name, password hash, one of five system roles, active flag, credential version and timezone-aware creation time. New hashes use bcrypt; existing Argon2 hashes remain verifiable and migrate after successful login when eligible. PostgreSQL constraints enforce unique email, normalized email, a nonempty name and valid role values.

Branches, branch assignments, members, collections and reports will get their own reviewed migrations when their workflows are implemented. Current route guards enforce the initial Super Admin staff-account scope and authenticated-session requirements; the full role/action permission matrix and branch-level authorization remain future work.

## Local setup (PowerShell)

Start Docker Desktop, then run from the project root:

```powershell
docker compose up -d --wait db redis
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
# First setup only; preserve an existing .env.
Copy-Item backend/.env.example backend/.env
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed --demo
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --no-proxy-headers
```

The local Compose services use PostgreSQL 16 and Redis 7, bound to loopback; PostgreSQL stores data in a named Docker volume. `docker compose stop db redis` stops them while retaining PostgreSQL records. Do not remove the volume unless intentionally resetting local data. If port 5432 is occupied, change the host port in Compose and database URLs accordingly.

The example credentials are local development values. `backend/.env` is ignored by Git. In hosted environments, set `DATABASE_URL` through the hosting provider rather than committing credentials. Environment variables override the file. Configuration requires a PostgreSQL URL; both `postgresql://` and `postgresql+psycopg://` use psycopg 3. The backend fails startup on missing/invalid configuration and does not create tables or seed users at startup.

Start the frontend separately with `npm ci` and `npm run dev` inside `frontend`. The five sample accounts in README work after explicitly seeding. Seed data is synthetic development data, not organiser-supplied acceptance data; replace/use the official dataset when available.

## Migrations

From `backend`:

```powershell
..\.venv\Scripts\python.exe -m alembic current
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic check
# After changing model metadata:
..\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe schema change"
```

Review generated migrations before committing; generation cannot infer every intended schema/data change. Apply migrations as an explicit release step. Never replace migrations with `create_all()` in application startup. `alembic downgrade` may drop records, so use it only deliberately, with backups where needed. CI tests upgrade/downgrade/re-upgrade only against its disposable test database.

## Seeding

`python -m app.seed --demo` adds missing demo accounts in one transaction. Running it again does not duplicate users, reset passwords, reactivate users or overwrite names/roles. It is never run automatically. Do not run it on a production database: these are public demo credentials. No public user-creation endpoint has been added.

## Database-backed tests

Create a separate local test database once, from the project root:

```powershell
docker compose exec -T db createdb -U branch_office branch_office_test
```

If it already exists, keep it; do not recreate/drop it. From `backend`:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://branch_office:local_dev_password@localhost:5432/branch_office_test'
..\.venv\Scripts\python.exe -m pytest
```

Tests require an explicit PostgreSQL URL with a database name ending `_test`; they do not fall back to your application database or SQLite. They apply real migrations, check metadata drift, and roll back each test's transaction so cases remain isolated. Use a dedicated test database, not one containing valuable records. CI creates its own PostgreSQL 16 service and runs the same tests with the existing 60% coverage minimum.

## Health and failures

- `GET /health`: process liveness; no database query.
- `GET /health/ready`: verifies a connection, migrated authentication tables and Redis availability; returns 503 if unavailable.
- Database errors in API handlers return a generic 503 without SQL, passwords or driver details. Login still returns generic 401 for incorrect credentials or inactive accounts.

## References

- [SQLAlchemy sessions and transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Alembic migration workflow](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [FastAPI password hashing with pwdlib](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
