from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import User

PASSWORD = "Temporary staff password 123!"


def browser():
    return TestClient(app, headers={"Origin": "http://testserver"})


def csrf(client):
    result = client.get("/api/csrf")
    assert result.status_code == 200
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result


def login(client, email="admin@example.test", password="Demo123!"):
    csrf(client)
    result = client.post("/api/login", json={"email": email, "password": password})
    if result.status_code == 200:
        client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return result


def test_cookie_session_restore_logout_and_csrf():
    with browser() as client:
        assert client.get("/api/me").status_code == 401
        bootstrap = csrf(client)
        before = dict(client.cookies)
        response = client.post(
            "/api/login", json={"email": "admin@example.test", "password": "Demo123!"}
        )
        assert response.status_code == 200
        assert dict(client.cookies) != before
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "samesite=lax" in response.headers["set-cookie"].lower()
        assert client.get("/api/me").json()["email"] == "admin@example.test"
        assert client.post("/api/logout").status_code == 403  # old CSRF after rotation
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        assert client.post("/api/logout").status_code == 204
        assert client.get("/api/me").status_code == 401
        assert bootstrap.headers["cache-control"] == "no-store"


def test_login_without_csrf_or_trusted_origin_fails():
    with browser() as client:
        assert (
            client.post(
                "/api/login", json={"email": "admin@example.test", "password": "Demo123!"}
            ).status_code
            == 403
        )
        csrf(client)
        client.headers["Origin"] = "https://attacker.example"
        assert (
            client.post(
                "/api/login", json={"email": "admin@example.test", "password": "Demo123!"}
            ).status_code
            == 403
        )


def test_super_admin_can_provision_change_and_reset_staff(db_session):
    with browser() as admin, browser() as staff:
        assert login(admin).status_code == 200
        created = admin.post(
            "/api/staff",
            json={
                "name": "New Staff",
                "email": " STAFF@example.test ",
                "role": "HR Lead",
                "temporary_password": PASSWORD,
            },
        )
        assert created.status_code == 201
        identity = created.json()
        assert identity["must_change_password"]
        assert "password_hash" not in identity and "temporary_password" not in identity
        assert PASSWORD not in str(identity)
        assert (
            admin.post(
                "/api/staff",
                json={
                    "name": "Other",
                    "email": "staff@example.test",
                    "role": "HR Lead",
                    "temporary_password": PASSWORD,
                },
            ).status_code
            == 409
        )
        assert login(staff, "staff@example.test", PASSWORD).status_code == 200
        assert staff.get("/api/staff").status_code == 403
        changed = staff.post(
            "/api/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": "My own different password 123!",
                "confirm_password": "My own different password 123!",
            },
        )
        assert changed.status_code == 200
        assert not changed.json()["must_change_password"]
        staff.headers["X-CSRF-Token"] = changed.json()["csrf_token"]
        assert staff.get("/api/staff").status_code == 403  # HR is never admin
        assert (
            admin.post(
                f"/api/staff/{identity['id']}/reset-password",
                json={"temporary_password": "Another temporary password 123!"},
            ).status_code
            == 204
        )
        assert staff.get("/api/me").status_code == 401
        assert login(staff, "staff@example.test", PASSWORD).status_code == 401
        assert login(staff, "staff@example.test", "Another temporary password 123!").json()[
            "must_change_password"
        ]
        stored = db_session.scalar(select(User).where(User.email == "staff@example.test"))
        assert stored.password_hash.startswith("$2b$")


@pytest.mark.parametrize(
    "email",
    ["finance@example.test", "editor@example.test", "branch@example.test", "hr@example.test"],
)
def test_other_roles_cannot_provision_staff(email):
    with browser() as client:
        assert login(client, email).status_code == 200
        assert client.get("/api/staff").status_code == 403
        assert (
            client.post(
                "/api/staff",
                json={
                    "name": "No",
                    "email": "no@example.test",
                    "role": "Super Admin",
                    "temporary_password": PASSWORD,
                },
            ).status_code
            == 403
        )


def test_session_expiry_and_disabled_account(db_session):
    from app.models import AuthSession
    from app.sessions import utc_now

    with browser() as client:
        assert login(client).status_code == 200
        row = db_session.scalar(select(AuthSession).where(AuthSession.user_id.is_not(None)))
        row.idle_expires_at = utc_now() - timedelta(seconds=1)
        db_session.flush()
        assert client.get("/api/me").status_code == 401
        assert login(client).status_code == 200
        user = db_session.scalar(select(User).where(User.email == "admin@example.test"))
        user.is_active = False
        db_session.flush()
        assert client.get("/api/me").status_code == 401


def test_validation_does_not_echo_password():
    with browser() as client:
        csrf(client)
        response = client.post("/api/login", json={"password": "sensitive-must-not-echo"})
        assert response.status_code == 422
        assert "sensitive-must-not-echo" not in response.text


def test_rate_limit_login_returns_retry_after():
    with browser() as client:
        csrf(client)
        for _ in range(5):
            assert (
                client.post(
                    "/api/login", json={"email": "unknown@example.test", "password": "bad"}
                ).status_code
                == 401
            )
        response = client.post(
            "/api/login", json={"email": "unknown@example.test", "password": "bad"}
        )
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) > 0
