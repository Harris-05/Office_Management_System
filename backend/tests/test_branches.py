import re
import uuid
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.main import app
from app.models import User, UserRole
from app.public_models import Branch, BranchAudit
from app.sessions import create_session, utc_now


def fields(**changes):
    return {
        "name": "Test Branch",
        "name_ur": "آزمائشی شاخ",
        "city": "Test City",
        "city_ur": "آزمائشی شہر",
        "address": "Example street",
        "address_ur": "مثالی پتہ",
        "hours": "Weekdays 9–5",
        "hours_ur": "پیر تا جمعہ",
        "description": "A clearly labelled test branch.",
        "description_ur": "یہ آزمائشی شاخ ہے۔",
        **changes,
    }


@pytest.fixture
def staff(db_session):
    with ExitStack() as stack:

        def client(role=UserRole.SUPER_ADMIN):
            user = db_session.scalar(select(User).where(User.role == role))
            row, token = create_session(db_session, user, utc_now())
            browser = stack.enter_context(TestClient(app, headers={"Origin": "http://testserver"}))
            browser.cookies.set(get_settings().cookie_name, token)
            browser.headers["X-CSRF-Token"] = row.csrf_token
            return browser, user

        yield client


def create(client):
    response = client.post("/api/branches", json=fields())
    assert response.status_code == 201, response.text
    return response.json()


def command(client, row, action, **body):
    result = client.post(
        f"/api/branches/{row['id']}/{action}", json={"expected_version": row["version"], **body}
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_create_codes_details_filters_and_audit(staff, db_session):
    admin, _ = staff()
    first, second = create(admin), create(admin)
    assert re.fullmatch(r"BR-\d{6,}", first["code"])
    assert first["code"] != second["code"]
    assert first["status"] == "Forming" and not first["is_published"]
    assert first["version"] == 1 and first["lead"] is None
    assert admin.get(f"/api/branches/{first['id']}").json()["code"] == first["code"]
    result = admin.get("/api/branches", params={"search": first["code"], "limit": 1}).json()
    assert result["total"] == 1 and result["items"][0]["id"] == first["id"]
    assert admin.get("/api/branches", params={"status": "Active"}).json()["total"] == 0
    history = admin.get(f"/api/branches/{first['id']}/audit").json()
    assert history["total"] == 1 and history["items"][0]["action"] == "created"
    assert history["items"][0]["after"]["code"] == first["code"]
    assert db_session.scalar(select(func.count()).select_from(BranchAudit)) == 2


def test_mutations_conflict_and_no_op_preserve_revision(staff):
    admin, _ = staff()
    row = create(admin)
    changed = command(admin, row, "update", **fields(name="Updated branch"))
    assert changed["version"] == 2 and changed["slug"] == row["slug"]
    assert command(admin, changed, "update", **fields(name="Updated branch"))["version"] == 2
    stale = admin.post(
        f"/api/branches/{row['id']}/update", json={"expected_version": 1, **fields()}
    )
    assert stale.status_code == 409
    assert admin.get(f"/api/branches/{row['id']}/audit").json()["total"] == 2


@pytest.mark.parametrize(
    "start,end,allowed",
    [
        (a, b, b in targets)
        for a, targets in {
            "Forming": {"Active", "Closed"},
            "Active": {"Paused", "Closed"},
            "Paused": {"Active", "Closed"},
            "Closed": set(),
        }.items()
        for b in ("Forming", "Active", "Paused", "Closed")
    ],
)
def test_lifecycle_pairs(staff, db_session, start, end, allowed):
    admin, _ = staff()
    row = create(admin)
    stored = db_session.get(Branch, uuid.UUID(row["id"]))
    stored.status = start
    db_session.commit()
    result = admin.post(
        f"/api/branches/{row['id']}/status",
        json={"expected_version": 1, "status": end, "reason": "Test transition"},
    )
    assert result.status_code == (200 if allowed or start == end else 422)
    if start == end:
        assert result.json()["version"] == 1


def test_publication_pause_close_and_assignment_release(staff, db_session):
    admin, _ = staff()
    lead, lead_user = staff(UserRole.BRANCH_LEAD)
    row = create(admin)
    assert (
        admin.post(
            f"/api/branches/{row['id']}/publication",
            json={"expected_version": 1, "is_published": True},
        ).status_code
        == 422
    )
    row = command(admin, row, "lead", lead_id=str(lead_user.id))
    row = command(admin, row, "status", status="Active", reason="Ready to operate")
    row = command(admin, row, "publication", is_published=True)
    assert any(x["id"] == row["id"] for x in admin.get("/api/public/catalog").json()["branches"])
    assert lead.get(f"/api/branches/{row['id']}").status_code == 200
    row = command(admin, row, "status", status="Paused", reason="Temporary pause")
    assert not row["is_published"]
    assert not admin.get("/api/public/catalog").json()["branches"]
    row = command(admin, row, "status", status="Active", reason="Resume local work")
    assert not row["is_published"]
    row = command(admin, row, "status", status="Closed", reason="Branch closing")
    assert row["lead"] is None
    assert lead.get(f"/api/branches/{row['id']}").status_code == 404
    assert (
        admin.post(
            f"/api/branches/{row['id']}/update",
            json={"expected_version": row["version"], **fields()},
        ).status_code
        == 422
    )
    assert admin.get(f"/api/branches/{row['id']}/audit").json()["items"][0]["before"][
        "lead_id"
    ] == str(lead_user.id)


def test_lead_scope_and_invalid_or_duplicate_assignment(staff):
    admin, admin_user = staff()
    lead, lead_user = staff(UserRole.BRANCH_LEAD)
    a, b = create(admin), create(admin)
    assert lead.get("/api/branches").json()["total"] == 0
    a = command(admin, a, "lead", lead_id=str(lead_user.id))
    assert [row["id"] for row in lead.get("/api/branches").json()["items"]] == [a["id"]]
    assert lead.get(f"/api/branches/{b['id']}").status_code == 404
    assert lead.get(f"/api/branches/{b['id']}/audit").status_code == 404
    assert (
        lead.post(
            f"/api/branches/{a['id']}/status",
            json={"expected_version": a["version"], "status": "Active", "reason": "Forged write"},
        ).status_code
        == 403
    )
    assert (
        admin.post(
            f"/api/branches/{b['id']}/lead",
            json={"expected_version": 1, "lead_id": str(lead_user.id)},
        ).status_code
        == 409
    )
    for bad in (str(admin_user.id), str(uuid.uuid4())):
        assert (
            admin.post(
                f"/api/branches/{b['id']}/lead", json={"expected_version": 1, "lead_id": bad}
            ).status_code
            == 422
        )
    options = admin.get("/api/branches/eligible-leads", params={"limit": 1}).json()
    assert options["items"][0]["branch_id"] == a["id"]
    assert lead.get("/api/branches/eligible-leads").status_code == 403
    a = command(admin, a, "lead", lead_id=None)
    assert lead.get(f"/api/branches/{a['id']}").status_code == 404


@pytest.mark.parametrize(
    "role", [UserRole.CONTENT_EDITOR, UserRole.HR_LEAD, UserRole.FINANCE_REVIEWER]
)
def test_other_roles_cannot_access_internal_registry(staff, role):
    client, _ = staff(role)
    assert client.get("/api/branches").status_code == 403
    assert client.post("/api/branches", json=fields()).status_code == 403


def test_csrf_validation_and_unknown_fields(staff):
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/branches").status_code == 401
    admin, _ = staff()
    assert admin.get("/api/branches", params={"search": "bad\x00query"}).status_code == 422
    assert (
        admin.get("/api/branches/eligible-leads", params={"search": "bad\x00query"}).status_code
        == 422
    )
    for data in (
        fields(name="  "),
        fields(name="bad\x00name"),
        fields(name="bad\x07name"),
        fields(code="FORGED"),
    ):
        assert admin.post("/api/branches", json=data).status_code == 422
    admin.headers.pop("X-CSRF-Token")
    assert admin.post("/api/branches", json=fields()).status_code == 403
