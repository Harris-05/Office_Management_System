import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize(
    ("email", "role"),
    [
        ("admin@example.test", "Super Admin"),
        ("finance@example.test", "Finance Reviewer"),
        ("editor@example.test", "Content Editor"),
        ("branch@example.test", "Branch Lead"),
        ("hr@example.test", "HR Lead"),
    ],
)
def test_demo_login_returns_role_without_password(email, role):
    with TestClient(app) as client:
        response = client.post("/api/login", json={"email": email, "password": "Demo123!"})
    assert response.status_code == 200
    assert response.json()["role"] == role
    assert response.json()["email"] == email
    assert "password" not in response.json()


@pytest.mark.parametrize(
    ("email", "password"),
    [("unknown@example.test", "Demo123!"), ("admin@example.test", "wrong")],
)
def test_incorrect_credentials_are_rejected(email, password):
    with TestClient(app) as client:
        response = client.post("/api/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password."}


def test_login_requires_both_fields():
    with TestClient(app) as client:
        response = client.post("/api/login", json={"email": "admin@example.test"})
    assert response.status_code == 422


def test_email_is_normalised():
    with TestClient(app) as client:
        response = client.post(
            "/api/login", json={"email": " ADMIN@example.test ", "password": "Demo123!"}
        )
    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.test"
