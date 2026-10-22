import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import get_db
from app.main import app
from app.models import User, UserRole
from app.passwords import hash_password, verify_password
from app.seed import seed_demo_users
from app.users import find_user_by_email


def test_seed_is_idempotent_and_preserves_existing_accounts(db_session):
    user = find_user_by_email(db_session, "admin@example.test")
    original_hash = user.password_hash
    user.name = "Changed in database"
    user.is_active = False
    assert seed_demo_users(db_session) == 0
    assert db_session.scalar(select(func.count()).select_from(User)) == 5
    assert user.password_hash == original_hash
    assert user.name == "Changed in database"
    assert not user.is_active
    assert original_hash.startswith("$argon2id$")
    assert verify_password("Demo123!", original_hash)
    assert user.created_at.tzinfo is not None


def test_login_reads_new_records_from_database(db_session):
    db_session.add(
        User(
            email="new@example.test",
            name="New Staff",
            role=UserRole.HR_LEAD,
            password_hash=hash_password("different-password"),
        )
    )
    db_session.flush()
    with TestClient(app) as client:
        response = client.post(
            "/api/login", json={"email": "new@example.test", "password": "different-password"}
        )
    assert response.json() == {"name": "New Staff", "email": "new@example.test", "role": "HR Lead"}


def test_inactive_users_cannot_log_in(db_session):
    find_user_by_email(db_session, "admin@example.test").is_active = False
    db_session.flush()
    with TestClient(app) as client:
        response = client.post(
            "/api/login", json={"email": "admin@example.test", "password": "Demo123!"}
        )
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("email", "role"),
    [
        ("admin@example.test", "HR Lead"),
        ("UPPER@example.test", "HR Lead"),
        ("other@example.test", "Unknown Role"),
    ],
)
def test_database_rejects_duplicate_email_unnormalized_email_and_invalid_role(
    db_session, email, role
):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO users (id, email, name, password_hash, role) "
                "VALUES (gen_random_uuid(), :email, 'Staff', 'not-used', :role)"
            ),
            {"email": email, "role": role},
        )


def test_readiness_checks_migrated_database():
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_database_failure_returns_safe_service_unavailable():
    def unavailable():
        raise SQLAlchemyError("private SQL details must not leak")

    app.dependency_overrides[get_db] = unavailable
    with TestClient(app) as client:
        response = client.post(
            "/api/login", json={"email": "admin@example.test", "password": "Demo123!"}
        )
    assert response.status_code == 503
    assert response.json() == {"detail": "Database temporarily unavailable."}
