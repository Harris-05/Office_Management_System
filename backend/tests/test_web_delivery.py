from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import install_frontend
from app.middleware import SecurityMiddleware
from app.config import get_settings


def test_spa_refresh_and_asset_routes_preserve_api_boundaries(tmp_path):
    (tmp_path / "index.html").write_text("<html>Branch Office shell</html>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_text("console.log('asset')", encoding="utf-8")
    app = FastAPI()
    install_frontend(app, tmp_path)
    with TestClient(app) as client:
        for path in ["/", "/about", "/staff/reports", "/staff/content", "/staff/dashboard/"]:
            response = client.get(path)
            assert response.status_code == 200 and "Branch Office shell" in response.text
        assert client.get("/assets/app.js").status_code == 200
        for path in ["/api/missing", "/health/missing", "/assets/nope.js", "/missing", "/staff/nope"]:
            assert client.get(path).status_code == 404
        assert client.get("/assets/%2e%2e/index.html").status_code == 404


def test_missing_frontend_is_safe_in_development(tmp_path):
    app = FastAPI()
    install_frontend(app, tmp_path / "absent")
    with TestClient(app) as client:
        assert client.get("/").status_code == 404


def test_production_delivery_restricts_executable_sources(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("ALLOWED_HOSTS", '["office.example"]')
    monkeypatch.setenv("ALLOWED_ORIGINS", '["https://office.example"]')
    monkeypatch.setenv("RATE_LIMIT_SECRET", "production-header-test-only-secret-long-enough")
    get_settings.cache_clear()
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/health")
        assert "script-src 'self'" in response.headers["content-security-policy"]
        assert "object-src 'none'" in response.headers["content-security-policy"]
        assert "max-age=" in response.headers["strict-transport-security"]
