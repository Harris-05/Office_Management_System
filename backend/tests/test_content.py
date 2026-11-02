"""CMS publication boundaries and revision commands against the real database."""

import uuid
from contextlib import ExitStack
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import get_settings
from app.main import app
from app.models import User, UserRole
from app.public_models import Branch
from app.public_seed import seed_public_content
from app.sessions import create_session, utc_now


@pytest.fixture
def staff(db_session):
    with ExitStack() as stack:

        def client(role=UserRole.CONTENT_EDITOR):
            user = db_session.scalar(select(User).where(User.role == role))
            row, token = create_session(db_session, user, utc_now())
            browser = stack.enter_context(TestClient(app, headers={"Origin": "http://testserver"}))
            browser.cookies.set(get_settings().cookie_name, token)
            browser.headers["X-CSRF-Token"] = row.csrf_token
            return browser

        yield client


def payload(kind="program", **changes):
    fields = {
        "kind": kind,
        "slug": f"sample-{uuid.uuid4().hex}",
        "title": "Community learning",
        "title_ur": "اجتماعی تعلیم",
        "description": "Local practical learning.",
        "description_ur": "مقامی عملی تعلیم۔",
    }
    if kind == "program":
        fields.update(audience="Local residents", audience_ur="مقامی باشندے")
    if kind == "page":
        fields.update(page_key="about")
    return {**fields, **changes}


def create(client, content=None):
    response = client.post(
        "/api/content", json={"content": content or payload(), "reason": "Initial draft"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def command(client, row, action, **values):
    response = client.post(
        f"/api/content/{row['id']}/{action}",
        json={
            "expected_version": row["version"],
            "reason": "Reviewed bilingual copy",
            **values,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_draft_publish_edit_preview_and_unpublish_do_not_leak(staff):
    editor = staff()
    row = create(editor)
    def catalog():
        return editor.get("/api/public/catalog").json()["programs"]
    assert not catalog()
    assert row["published"] is None and not row["is_published"]
    published = command(editor, row, "publish")
    assert catalog()[0]["title"] == "Community learning"
    changed = command(
        editor, published, "draft", content={**row["draft"], "title": "Secret next draft"}
    )
    assert changed["has_unpublished_changes"]
    assert catalog()[0]["title"] == "Community learning"
    preview = editor.get(f"/api/content/{row['id']}/preview").json()
    assert preview["content"]["title"] == "Secret next draft"
    assert "draft" not in str(catalog())
    changed = command(editor, changed, "publish")
    assert catalog()[0]["title"] == "Secret next draft"
    command(editor, changed, "unpublish")
    assert not catalog()
    history = editor.get(f"/api/content/{row['id']}/history").json()
    assert history["total"] == 5
    assert [x["action"] for x in history["items"]] == [
        "unpublished",
        "published",
        "draft_saved",
        "published",
        "created",
    ]
    assert history["items"][-1]["snapshot"]["draft"]["title"] == "Community learning"
    assert all(x["actor"]["name"] and x["reason"] for x in history["items"])


def test_stale_commands_preserve_content_and_history(staff):
    editor = staff()
    row = create(editor)
    changed = command(editor, row, "draft", content={**row["draft"], "title": "Updated title"})
    for action in ("draft", "publish", "unpublish"):
        body = {"expected_version": row["version"], "reason": "Stale command"}
        if action == "draft":
            body["content"] = row["draft"]
        response = editor.post(f"/api/content/{row['id']}/{action}", json=body)
        assert response.status_code == 409
    assert editor.get(f"/api/content/{row['id']}").json() == changed
    assert editor.get(f"/api/content/{row['id']}/history").json()["total"] == 2


@pytest.mark.parametrize(
    "role", [UserRole.BRANCH_LEAD, UserRole.FINANCE_REVIEWER, UserRole.HR_LEAD]
)
def test_staff_roles_cannot_read_previews_or_mutate(staff, role):
    row = create(staff())
    denied = staff(role)
    for suffix in ("", "/preview", "/history"):
        assert denied.get(f"/api/content/{row['id']}{suffix}").status_code == 403
    assert denied.get("/api/content").status_code == 403
    assert denied.get("/api/content/branches").status_code == 403
    assert (
        denied.post("/api/content", json={"content": payload(), "reason": "Attempt"}).status_code
        == 403
    )
    for action in ("draft", "publish", "unpublish"):
        assert (
            denied.post(
                f"/api/content/{row['id']}/{action}",
                json={
                    "expected_version": 1,
                    "reason": "Attempt",
                    **({"content": row["draft"]} if action == "draft" else {}),
                },
            ).status_code
            == 403
        )


def test_anonymous_draft_preview_denied(staff):
    row = create(staff())
    with TestClient(app) as client:
        assert client.get(f"/api/content/{row['id']}/preview").status_code == 401


def test_page_published_snapshot_and_plain_text(staff):
    editor = staff(UserRole.SUPER_ADMIN)
    row = create(editor, payload("page", description="<script>alert(1)</script>"))
    assert editor.get("/api/public/catalog").json()["pages"] == []
    row = command(editor, row, "publish")
    public = editor.get("/api/public/catalog").json()["pages"][0]
    assert public["page_key"] == "about" and public["description"] == "<script>alert(1)</script>"
    command(editor, row, "draft", content={**row["draft"], "description": "Private replacement"})
    assert editor.get("/api/public/catalog").json()["pages"][0] == public
    duplicate = editor.post(
        "/api/content", json={"content": payload("page"), "reason": "Duplicate"}
    )
    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"slug": "../unsafe"},
        {"slug": "javascript:alert"},
        {"title": "\u0000bad"},
        {"title_ur": ""},
        {"unexpected": "value"},
    ],
)
def test_invalid_fields_rejected(staff, changes):
    response = staff().post(
        "/api/content", json={"content": payload(**changes), "reason": "Validation test"}
    )
    assert response.status_code == 422


def test_event_requires_existing_active_published_branch_and_ordered_dates(staff, db_session):
    editor = staff()
    branch = Branch(
        slug="event-test",
        name="Example",
        name_ur="مثال",
        city="City",
        city_ur="شہر",
        address="Road",
        address_ur="سڑک",
        hours="9 to 5",
        hours_ur="صبح",
        description="Example",
        description_ur="مثال",
        status="Paused",
        is_published=False,
    )
    db_session.add(branch)
    db_session.flush()
    start = utc_now() + timedelta(days=7)
    event = payload(
        "event",
        branch_id=str(branch.id),
        starts_at=start.isoformat(),
        ends_at=(start + timedelta(hours=2)).isoformat(),
    )
    row = create(editor, event)
    response = editor.post(
        f"/api/content/{row['id']}/publish", json={"expected_version": 1, "reason": "Ready"}
    )
    assert response.status_code == 422
    branch.status, branch.is_published = "Active", True
    db_session.commit()
    row = command(editor, row, "publish")
    assert len(editor.get("/api/public/catalog").json()["events"]) == 1
    branch.status, branch.is_published = "Paused", False
    db_session.commit()
    assert editor.get("/api/public/catalog").json()["events"] == []
    assert editor.get("/api/content/branches").json() == []
    invalid = {**event, "ends_at": event["starts_at"]}
    assert (
        editor.post(
            "/api/content", json={"content": invalid, "reason": "Invalid dates"}
        ).status_code
        == 422
    )


def test_samples_seeded_after_migration_are_editable_and_adoption_is_repeat_safe(staff, db_session):
    assert seed_public_content(db_session) == 12
    editor = staff()
    page = editor.get("/api/content").json()
    assert page["total"] == 9
    assert all(row["is_demo"] and row["is_published"] for row in page["items"])
    assert seed_public_content(db_session) == 0
    assert editor.get("/api/content").json()["total"] == 9
    row = next(row for row in page["items"] if row["kind"] == "program")
    changed = command(editor, row, "draft", content={**row["draft"], "title": "Edited example"})
    assert changed["is_demo"]
    seed_public_content(db_session)
    assert editor.get(f"/api/content/{row['id']}").json()["draft"]["title"] == "Edited example"
    assert editor.get(f"/api/content/{row['id']}/history").json()["total"] == 2
