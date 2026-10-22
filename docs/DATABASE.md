# PostgreSQL setup and development

## Design

The API now authenticates against PostgreSQL instead of an in-memory account dictionary. SQLAlchemy 2 models describe persisted records; Alembic migrations version the schema. Routes handle HTTP validation and responses, `users.py` contains account lookup/authentication logic, and `database.py` owns engine/session lifecycle. This keeps persistence separate from the UI and request handling without adding unnecessary abstraction layers.

Each request gets a short-lived session. Reads do not commit; write operations own explicit transactions and commit only when the complete operation succeeds. Closing a session rolls back uncommitted work. Connection pooling is bounded and checks stale connections before reuse. This synchronous database access runs in FastAPI's worker threads through regular `def` endpoints/dependencies.

The first schema contains **users** only, matching the current login feature. It has a UUID primary key, unique normalized email, display name, Argon2 password hash, one of the five system roles, active flag and timezone-aware creation time. PostgreSQL constraints enforce unique email, normalized email, a nonempty name and valid role values. Unique email already has a supporting index; no redundant index is added.

Branches, branch assignments, members, collections and reports will get their own reviewed migrations when their workflows are implemented. A stored role does not yet enforce permissions. Login still returns a profile without creating a session/token; this change establishes persistent accounts rather than completing authentication/authorisation.

## Local setup (PowerShell)

Start Docker Desktop, then run from the project root:

```powershell
docker compose up -d --wait db
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
# First setup only; preserve an existing .env.
Copy-Item backend/.env.example backend/.env
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed --demo
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The local Compose service uses PostgreSQL 16, listens only on `127.0.0.1:5432`, and stores data in a named Docker volume. `docker compose stop db` stops it while retaining records. Do not remove the volume unless intentionally resetting local data. If port 5432 is occupied, change the host port in Compose and both database URLs accordingly.

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
- `GET /health/ready`: verifies a connection and the migrated users table; returns 503 if unavailable.
- Database errors in API handlers return a generic 503 without SQL, passwords or driver details. Login still returns generic 401 for incorrect credentials or inactive accounts.

## References

- [SQLAlchemy sessions and transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Alembic migration workflow](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [FastAPI password hashing with pwdlib](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
