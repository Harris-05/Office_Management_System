import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import app
from app.public_models import PublicSubmission
from app.public_seed import seed_public_content


def browser():
    client = TestClient(app, headers={"Origin": "http://testserver"})
    response = client.get("/api/csrf")
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


def payload(**changes):
    return {
        "request_id": str(uuid.uuid4()),
        "name": "Example Visitor",
        "email": "visitor@example.test",
        "subject": "A question",
        "message": "I would like to learn about the local team.",
        "consent": True,
        **changes,
    }


def test_catalogue_and_idempotent_seed(db_session):
    assert seed_public_content(db_session) == 12
    db_session.flush()
    assert seed_public_content(db_session) == 0
    with TestClient(app) as client:
        response = client.get("/api/public/catalog")
        assert response.status_code == 200
        data = response.json()
        assert [len(data[key]) for key in ("branches", "programs", "events")] == [3, 3, 6]
        assert all(row["is_demo"] for row in data["events"])
        assert all(row["title_ur"] for row in data["events"])
        assert client.get("/api/public/messages").status_code == 405


def test_unpublished_branch_hides_its_events(db_session):
    from app.public_models import Branch

    seed_public_content(db_session)
    branch = db_session.scalar(select(Branch).where(Branch.slug == "karachi-demo"))
    branch.is_published = False
    db_session.flush()
    data = TestClient(app).get("/api/public/catalog").json()
    assert len(data["branches"]) == 2
    assert all(row["branch_id"] != str(branch.id) for row in data["events"])


def test_contact_is_private_persisted_and_idempotent(db_session):
    with browser() as client:
        body = payload()
        result = client.post("/api/public/messages", json=body)
        assert result.status_code == 201
        assert set(result.json()) == {"id"}
        again = client.post("/api/public/messages", json=body)
        assert again.json() == result.json()
        assert db_session.scalar(select(func.count()).select_from(PublicSubmission)) == 1
        row = db_session.get(PublicSubmission, uuid.UUID(result.json()["id"]))
        assert row.email == body["email"] and row.kind == "contact"
        assert row.expires_at > datetime.now(UTC) + timedelta(days=89)
        changed = client.post("/api/public/messages", json={**body, "message": "Different message"})
        assert changed.status_code == 409
    with browser() as stranger:
        assert stranger.post("/api/public/messages", json=body).status_code == 409
        assert stranger.get("/api/staff/public-submissions").status_code == 401


@pytest.mark.parametrize(
    "changes",
    [{"consent": False}, {"email": "not-an-email"}, {"name": "  "}, {"message": "x"}, {"extra": 1}],
)
def test_invalid_submission_rejected(changes):
    with browser() as client:
        assert client.post("/api/public/messages", json=payload(**changes)).status_code == 422


def test_csrf_origin_and_rate_limit():
    with TestClient(app) as client:
        assert client.post("/api/public/messages", json=payload()).status_code == 403
    with browser() as client:
        client.headers["Origin"] = "https://untrusted.example"
        assert client.post("/api/public/messages", json=payload()).status_code == 403
    with browser() as client:
        statuses = [
            client.post("/api/public/messages", json=payload()).status_code for _ in range(6)
        ]
        assert 429 in statuses


def test_volunteer_requires_a_published_branch(db_session):
    seed_public_content(db_session)
    with browser() as client:
        branch = client.get("/api/public/catalog").json()["branches"][0]
        body = payload(branch_id=branch["id"])
        assert client.post("/api/public/volunteers", json=body).status_code == 201
        assert (
            client.post(
                "/api/public/volunteers", json=payload(branch_id=str(uuid.uuid4()))
            ).status_code
            == 422
        )
        assert client.post("/api/public/volunteers", json=payload()).status_code == 422


def test_inbox_permissions_retention_and_committed_session_activity(db_session):
    from sqlalchemy.orm import Session

    from app.cleanup_public import cleanup
    from app.config import get_settings
    from app.database import get_db
    from app.models import AuthSession, User
    from app.sessions import create_session, utc_now

    seed_public_content(db_session)
    with browser() as visitor:
        branch_id = visitor.get("/api/public/catalog").json()["branches"][0]["id"]
        visitor.post("/api/public/messages", json=payload())
        visitor.post("/api/public/volunteers", json=payload(branch_id=branch_id))
    db_session.commit()
    for email, expected in [
        ("admin@example.test", {"contact", "volunteer"}),
        ("hr@example.test", {"volunteer"}),
        ("editor@example.test", None),
    ]:
        user = db_session.scalar(select(User).where(User.email == email))
        row, token = create_session(db_session, user, utc_now() - timedelta(minutes=5))
        session_id, old_idle = row.id, row.idle_expires_at
        db_session.commit()

        def request_db():
            with Session(bind=db_session.bind, join_transaction_mode="create_savepoint") as db:
                yield db

        previous = app.dependency_overrides[get_db]
        app.dependency_overrides[get_db] = request_db
        try:
            with TestClient(app) as staff:
                staff.cookies.set(get_settings().cookie_name, token)
                result = staff.get("/api/staff/public-submissions")
            if expected is None:
                assert result.status_code == 403
            else:
                assert result.status_code == 200
                assert {item["kind"] for item in result.json()} == expected
                assert all("fingerprint" not in item for item in result.json())
                db_session.expire_all()
                assert db_session.get(AuthSession, session_id).idle_expires_at > old_idle
        finally:
            app.dependency_overrides[get_db] = previous
    expired = db_session.scalar(select(PublicSubmission).where(PublicSubmission.kind == "contact"))
    expired.expires_at = utc_now() - timedelta(seconds=1)
    db_session.flush()
    assert cleanup(db_session) == 1
    assert db_session.scalar(select(func.count()).select_from(PublicSubmission)) == 1


def test_seed_forbidden_in_production(db_session, monkeypatch):
    from types import SimpleNamespace

    import app.public_seed as seed_module

    monkeypatch.setattr(
        seed_module, "get_settings", lambda: SimpleNamespace(environment="production")
    )
    with pytest.raises(ValueError, match="forbidden"):
        seed_public_content(db_session)
