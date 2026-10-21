from fastapi.testclient import TestClient

from app.main import app


def test_health_is_public_and_returns_json():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_unknown_route_returns_not_found():
    with TestClient(app) as client:
        response = client.get("/does-not-exist")

    assert response.status_code == 404
