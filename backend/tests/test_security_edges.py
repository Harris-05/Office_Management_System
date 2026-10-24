from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from test_secure_flow import PASSWORD, browser, csrf, login

from app.config import Settings, get_settings
from app.main import app
from app.models import AuthSession, SecurityEvent, User
from app.passwords import verify_password
from app.rate_limits import consume, get_redis
from app.sessions import utc_now


def test_future_api_route_requires_authentication_by_default():
    @app.get("/api/test-default-protection")
    def unadorned_endpoint():
        return {"private": "must not leak"}

    route = app.routes[-1]
    try:
        with browser() as client:
            assert client.get("/api/test-default-protection").status_code == 401
    finally:
        app.routes.remove(route)


def test_non_ascii_csrf_is_rejected_not_server_error():
    with browser() as client:
        csrf(client)
        client.headers.pop("X-CSRF-Token")
        response = client.post(
            "/api/login",
            headers={b"X-CSRF-Token": b"\xff"},
            json={"email": "admin@example.test", "password": "Demo123!"},
        )
        assert response.status_code == 403


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "1"}])
def test_actual_body_size_is_limited_without_trusting_headers(monkeypatch, headers):
    monkeypatch.setenv("BODY_LIMIT_BYTES", "1024")
    get_settings.cache_clear()
    with browser() as client:
        response = client.post(
            "/api/login", content=iter([b"x" * 600, b"x" * 600]), headers=headers
        )
        assert response.status_code == 413


def test_shared_atomic_limits_expire_and_do_not_store_raw_identity():
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(lambda _: consume("shared:private@example.test", 5), range(16)))
    assert sum(allowed for allowed, _ in outcomes) == 5
    keys = list(get_redis().scan_iter(match=f"{get_settings().rate_namespace}:*"))
    assert all("private@example.test" not in key for key in keys)
    assert all(0 < get_redis().ttl(key) <= 60 for key in keys)
    get_redis().delete(*keys)
    assert consume("shared:private@example.test", 5)[0]


def test_redis_outage_fails_closed_but_liveness_stays_available(monkeypatch):
    def unavailable(*args):
        raise RedisConnectionError("internal secret details")

    with browser() as client, monkeypatch.context() as patch:
        patch.setattr("app.middleware.consume", unavailable)
        assert client.get("/api/me").status_code == 503
        assert "internal secret" not in client.get("/api/me").text
        assert client.get("/health").status_code == 200


def test_forwarded_headers_do_not_bypass_login_limits():
    with browser() as client:
        csrf(client)
        for i in range(5):
            assert (
                client.post(
                    "/api/login",
                    headers={"X-Forwarded-For": f"192.0.2.{i}"},
                    json={"email": "unknown@example.test", "password": "bad"},
                ).status_code
                == 401
            )
        assert (
            client.post(
                "/api/login",
                headers={"X-Forwarded-For": "192.0.2.99"},
                json={"email": "unknown@example.test", "password": "bad"},
            ).status_code
            == 429
        )


def test_general_and_csrf_limit_boundaries(monkeypatch):
    monkeypatch.setenv("API_LIMIT", "2")
    get_settings.cache_clear()
    with browser() as client:
        assert client.get("/api/me").status_code == 401
        assert client.get("/api/me").status_code == 401
        assert client.get("/api/me").status_code == 429
    monkeypatch.setenv("API_LIMIT", "120")
    monkeypatch.setenv("CSRF_LIMIT", "2")
    get_settings.cache_clear()
    with browser() as client:
        assert client.get("/api/csrf").status_code == 200
        assert client.get("/api/csrf").status_code == 200
        assert client.get("/api/csrf").status_code == 429


def test_production_requires_safe_configuration_and_disables_docs():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, database_url="postgresql://u:p@localhost/test", environment="production"
        )
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql://u:p@localhost/test", bcrypt_cost=9)


def test_production_cookie_flags_and_docs_disabled(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.seed import seed_demo_users

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("RATE_LIMIT_SECRET", "production-test-secret-not-used-outside-tests")
    monkeypatch.setenv("ALLOWED_HOSTS", '["staff.example"]')
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://staff.example"]')
    get_settings.cache_clear()
    from app.database import get_db

    production_app = create_app()
    production_app.dependency_overrides[get_db] = app.dependency_overrides[get_db]
    with TestClient(production_app, base_url="https://staff.example") as client:
        assert client.get("/docs").status_code == 404
        response = client.get("/api/csrf")
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert cookie.startswith("__Host-")
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert "Domain=" not in cookie
        assert response.headers["strict-transport-security"] == "max-age=31536000"
    with pytest.raises(ValueError):
        seed_demo_users(None)


def test_temporary_password_expiry_and_required_change_admin(db_session):
    with browser() as admin, browser() as staff:
        assert login(admin).status_code == 200
        result = admin.post(
            "/api/staff",
            json={
                "name": "Second admin",
                "email": "second@example.test",
                "role": "Super Admin",
                "temporary_password": PASSWORD,
            },
        )
        assert result.status_code == 201
        assert login(staff, "second@example.test", PASSWORD).status_code == 200
        assert staff.get("/api/staff").status_code == 403
        row = db_session.scalar(select(User).where(User.email == "second@example.test"))
        row.temporary_password_expires_at = utc_now() - timedelta(seconds=1)
        db_session.flush()
        assert staff.get("/api/me").status_code == 401
        assert login(staff, "second@example.test", PASSWORD).status_code == 401


def test_legacy_login_migrates_hash_and_logout_replay_fails(db_session):
    from pwdlib import PasswordHash

    row = db_session.scalar(select(User).where(User.email == "admin@example.test"))
    row.password_hash = PasswordHash.recommended().hash("Demo123!")
    db_session.flush()
    with browser() as client:
        assert login(client).status_code == 200
        assert row.password_hash.startswith("$2b$")
        assert verify_password("Demo123!", row.password_hash)
        cookie = client.cookies.get(get_settings().cookie_name)
        assert client.post("/api/logout").status_code == 204
        client.cookies.set(get_settings().cookie_name, cookie)
        assert client.get("/api/me").status_code == 401


def test_security_audit_contains_no_credentials(db_session):
    with browser() as admin:
        assert login(admin).status_code == 200
        assert (
            admin.post(
                "/api/staff",
                json={
                    "name": "Audit Staff",
                    "email": "audit@example.test",
                    "role": "Branch Lead",
                    "temporary_password": PASSWORD,
                },
            ).status_code
            == 201
        )
    events = db_session.scalars(select(SecurityEvent)).all()
    assert any(event.action == "staff_created" and event.actor_id for event in events)
    assert PASSWORD not in str([event.__dict__ for event in events])


def test_session_database_stores_only_token_digest(db_session):
    with browser() as client:
        assert login(client).status_code == 200
        token = client.cookies.get(get_settings().cookie_name)
        rows = db_session.scalars(select(AuthSession)).all()
        assert all(token not in str(row.__dict__) for row in rows)
