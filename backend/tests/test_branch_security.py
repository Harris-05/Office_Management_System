import uuid

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session
from test_secure_flow import browser, csrf, login

from app.models import User, UserRole


@pytest.mark.parametrize(
    "body",
    [
        {"email": "bad\x00@example.test", "password": "Demo123!"},
        {"email": ["admin@example.test"], "password": "Demo123!"},
        {"email": "admin@example.test", "password": {"bad": "shape"}},
    ],
)
def test_malformed_login_is_validation_error_not_server_failure(body):
    with browser() as client:
        csrf(client)
        assert client.post("/api/login", json=body).status_code == 422


def test_reset_lock_contention_returns_retry_conflict_instead_of_waiting(
    engine, db_session, demo_hash
):
    email = f"locked-reset-{uuid.uuid4().hex}@example.test"
    with Session(engine) as setup, setup.begin():
        target = User(
            email=email, name="Lock test", role=UserRole.SUPER_ADMIN, password_hash=demo_hash
        )
        setup.add(target)
        setup.flush()
        target_id = target.id
    try:
        with browser() as client:
            assert login(client).status_code == 200
            db_session.execute(text("SET LOCAL lock_timeout = '500ms'"))
            with Session(engine) as holder, holder.begin():
                holder.scalar(select(User).where(User.id == target_id).with_for_update())
                result = client.post(
                    f"/api/staff/{target_id}/reset-password",
                    json={"temporary_password": "a new temporary password"},
                )
                assert result.status_code == 409
                assert "try again" in result.json()["detail"].lower()
    finally:
        db_session.rollback()
        with Session(engine) as cleanup, cleanup.begin():
            cleanup.execute(delete(User).where(User.id == target_id))
