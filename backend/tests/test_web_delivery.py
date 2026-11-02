from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.web import install_frontend


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
