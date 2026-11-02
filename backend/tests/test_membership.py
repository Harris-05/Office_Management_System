import re
import uuid
from contextlib import ExitStack
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.cleanup_public import cleanup
from app.config import get_settings
from app.main import app
from app.membership_models import ApplicationEvent, Member, MemberEvent
from app.models import User, UserRole
from app.public_models import Branch, PublicSubmission
from app.sessions import create_session, utc_now


@pytest.fixture
def hr(db_session):
    with ExitStack() as stack:

        def client(role=UserRole.HR_LEAD):
            user = db_session.scalar(select(User).where(User.role == role))
            session, token = create_session(db_session, user, utc_now())
            browser = stack.enter_context(TestClient(app, headers={"Origin": "http://testserver"}))
            browser.cookies.set(get_settings().cookie_name, token)
            browser.headers["X-CSRF-Token"] = session.csrf_token
            return browser, user

        yield client


def application(db, **changes):
    branch = Branch(
        slug=uuid.uuid4().hex,
        name="Review test branch",
        name_ur="آزمائشی شاخ",
        city="Test",
        city_ur="آزمائش",
        address="Test street",
        address_ur="آزمائشی گلی",
        hours="Weekdays",
        hours_ur="ہفتہ",
        description="Test branch",
        description_ur="آزمائشی شاخ",
        status="Active",
        is_published=True,
    )
    db.add(branch)
    db.flush()
    row = PublicSubmission(
        id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        fingerprint="x" * 64,
        kind="volunteer",
        name="Review Test Person",
        email=f"{uuid.uuid4().hex}@example.test",
        subject="Volunteer interest",
        message="I would like to help this branch.",
        branch_id=branch.id,
        expires_at=utc_now() + timedelta(days=90),
        **changes,
    )
    db.add(row)
    db.commit()
    return row, branch


def review(client, row, decision="Accepted", version=1):
    return client.post(
        f"/api/applications/{row.id}/review",
        json={
            "expected_version": version,
            "decision": decision,
            "reason": "Reviewed test application",
        },
    )


def test_acceptance_creates_one_member_and_private_audit(hr, db_session):
    client, _ = hr()
    row, _ = application(db_session)
    users_before = db_session.scalar(select(func.count()).select_from(User))
    queued = client.get("/api/applications").json()
    assert queued["total"] == 1 and queued["items"][0]["status"] == "Pending"
    result = review(client, row)
    assert result.status_code == 200, result.text
    accepted = result.json()
    member = accepted["member"]
    assert re.fullmatch(r"MEM-\d{6,}", member["code"])
    assert accepted["status"] == "Accepted" and accepted["version"] == 2
    profile = client.get(f"/api/members/{member['id']}").json()
    assert profile["email"] == row.email and profile["source_id"] == str(row.id)
    assert profile["status"] == "Active" and profile["organisational_role"] == "Volunteer"
    assert db_session.scalar(select(func.count()).select_from(User)) == users_before
    assert review(client, row).status_code == 409
    assert review(client, row, "Declined", 2).status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Member)) == 1
    assert client.get("/api/applications").json()["total"] == 0
    assert client.get("/api/applications?status=All").json()["total"] == 1
    assert client.get(f"/api/applications/{row.id}/audit").json()["total"] == 1
    event = db_session.scalar(select(MemberEvent))
    assert "Reviewed test application" not in str(event.after)
    assert row.email not in str(event.after) and row.message not in str(event.after)


def test_decline_and_duplicate_email_policy(hr, db_session):
    client, _ = hr(UserRole.SUPER_ADMIN)
    first, _ = application(db_session)
    second, _ = application(db_session)
    second.email = first.email
    db_session.commit()
    assert review(client, first).status_code == 200
    conflict = review(client, second)
    assert conflict.status_code == 409 and "MEM-" in conflict.json()["detail"]
    declined = review(client, second, "Declined")
    assert declined.status_code == 200 and declined.json()["member"] is None
    assert db_session.scalar(select(func.count()).select_from(Member)) == 1
    assert review(client, second, "Accepted", 2).status_code == 409


@pytest.mark.parametrize("status", ["Forming", "Paused", "Closed"])
def test_accept_requires_active_branch_but_decline_is_allowed(hr, db_session, status):
    client, _ = hr()
    row, branch = application(db_session)
    branch.is_published = False
    branch.status = status
    db_session.commit()
    assert review(client, row).status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Member)) == 0
    assert review(client, row, "Declined").status_code == 200


def test_unpublished_active_branch_can_process_existing_application(hr, db_session):
    client, _ = hr()
    row, branch = application(db_session)
    branch.is_published = False
    db_session.commit()
    assert review(client, row).status_code == 200


def test_expiry_cleanup_keeps_member_and_removes_application_history(hr, db_session):
    client, _ = hr()
    row, _ = application(db_session)
    member_id = review(client, row).json()["member"]["id"]
    row.expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    assert client.get(f"/api/applications/{row.id}").status_code == 404
    assert client.get(f"/api/applications/{row.id}/audit").status_code == 404
    assert review(client, row, version=2).status_code == 404
    assert client.get("/api/applications?status=All").json()["total"] == 0
    assert client.get(f"/api/members/{member_id}").json()["source_id"] is None
    assert cleanup(db_session) == 1
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(Member, uuid.UUID(member_id)).source_id is None
    assert db_session.scalar(select(func.count()).select_from(ApplicationEvent)) == 0
    assert db_session.scalar(select(func.count()).select_from(MemberEvent)) == 1


def test_member_updates_filters_conflicts_and_activation_rules(hr, db_session):
    client, _ = hr()
    row, branch = application(db_session)
    member = review(client, row).json()["member"]
    path = f"/api/members/{member['id']}/update"
    body = {
        "expected_version": 1,
        "team": "Outreach",
        "organisational_role": "Coordinator",
        "status": "Inactive",
        "reason": "Availability changed",
    }
    updated = client.post(path, json=body)
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert client.post(path, json=body).status_code == 409
    body["expected_version"] = 2
    assert client.post(path, json=body).json()["version"] == 2
    for query in [
        f"search={member['code']}",
        "status=Inactive",
        "team=Outreach",
        "organisational_role=Coordinator",
        f"branch_id={branch.id}",
    ]:
        assert client.get(f"/api/members?{query}").json()["total"] == 1
    assert client.get(f"/api/members/{member['id']}/audit").json()["total"] == 2
    branch.status = "Paused"
    branch.is_published = False
    db_session.commit()
    body["status"] = "Active"
    assert client.post(path, json=body).status_code == 422


@pytest.mark.parametrize(
    "role", [UserRole.BRANCH_LEAD, UserRole.FINANCE_REVIEWER, UserRole.CONTENT_EDITOR]
)
def test_other_roles_cannot_read_or_mutate_membership(hr, db_session, role):
    client, _ = hr(role)
    row, _ = application(db_session)
    for path in [
        "/api/applications",
        f"/api/applications/{row.id}",
        f"/api/applications/{row.id}/audit",
        "/api/members",
        f"/api/members/{uuid.uuid4()}",
        "/api/hr/branches",
    ]:
        assert client.get(path).status_code == 403
    assert review(client, row).status_code == 403
    assert client.post(f"/api/members/{uuid.uuid4()}/update", json={}).status_code == 403


def test_safe_inputs_csrf_and_contact_exclusion(hr, db_session):
    client, _ = hr()
    row, branch = application(db_session)
    for path in ["/api/applications", "/api/members", "/api/hr/branches"]:
        assert client.get(path, params={"search": "\x00"}).status_code == 422
        assert client.get(path, params={"limit": 101}).status_code == 422
    assert (
        client.post(
            f"/api/applications/{row.id}/review",
            json={"expected_version": 1, "decision": "Accepted", "reason": "bad\x00reason"},
        ).status_code
        == 422
    )
    assert client.get("/api/hr/branches").json()["items"][0] == {
        "id": str(branch.id),
        "code": branch.code,
        "name": branch.name,
        "status": "Active",
    }
    assert client.get("/api/branches").status_code == 403
    csrf = client.headers.pop("X-CSRF-Token")
    assert review(client, row).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    row.kind = "contact"
    row.review_status = None
    row.review_version = None
    db_session.commit()
    assert client.get(f"/api/applications/{row.id}").status_code == 404
    assert review(client, row).status_code == 404


def test_public_submission_initialises_pending_and_preserves_receipt_retry(hr):
    client, _ = hr(UserRole.SUPER_ADMIN)
    from test_branches import fields

    branch = client.post("/api/branches", json=fields()).json()
    version = client.post(
        f"/api/branches/{branch['id']}/status",
        json={"expected_version": 1, "status": "Active", "reason": "Ready for volunteers"},
    ).json()["version"]
    client.post(
        f"/api/branches/{branch['id']}/publication",
        json={"expected_version": version, "is_published": True},
    )
    body = {
        "request_id": str(uuid.uuid4()),
        "name": "Public Test",
        "email": "public@example.test",
        "subject": "Volunteer interest",
        "message": "I would like to volunteer.",
        "branch_id": branch["id"],
        "consent": True,
    }
    response = client.post("/api/public/volunteers", json=body)
    assert response.status_code == 201, response.text
    assert client.post("/api/public/volunteers", json=body).json() == response.json()
    detail = client.get(f"/api/applications/{response.json()['id']}").json()
    assert detail["status"] == "Pending" and detail["version"] == 1


def test_acceptance_rolls_back_member_when_audit_cannot_save(hr, db_session):
    client, _ = hr()
    row, _ = application(db_session)
    record_id = row.id

    def unavailable(mapper, connection, target):
        raise RuntimeError("Audit unavailable")

    event.listen(MemberEvent, "before_insert", unavailable)
    try:
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            review(client, row)
        db_session.rollback()
    finally:
        event.remove(MemberEvent, "before_insert", unavailable)
    assert db_session.get(PublicSubmission, record_id).review_status == "Pending"
    assert db_session.scalar(select(func.count()).select_from(Member)) == 0
    assert db_session.scalar(select(func.count()).select_from(ApplicationEvent)) == 0


def test_public_application_rejects_nul_before_storage(hr, db_session):
    client, _ = hr()
    _, branch = application(db_session)
    body = {
        "request_id": str(uuid.uuid4()),
        "name": "Bad\x00Name",
        "email": "safe@example.test",
        "subject": "Volunteer interest",
        "message": "I would like to help here.",
        "branch_id": str(branch.id),
        "consent": True,
    }
    assert client.post("/api/public/volunteers", json=body).status_code == 422


def test_multiline_reasons_are_preserved_in_review_and_member_history(hr, db_session):
    client, _ = hr()
    row, _ = application(db_session)
    reason = "Availability confirmed.\nReady to join the outreach team."
    response = client.post(
        f"/api/applications/{row.id}/review",
        json={"expected_version": 1, "decision": "Accepted", "reason": reason},
    )
    assert response.status_code == 200, response.text
    assert response.json()["reason"] == reason
    member = response.json()["member"]
    response = client.post(
        f"/api/members/{member['id']}/update",
        json={
            "expected_version": 1,
            "status": "Active",
            "team": "Outreach",
            "organisational_role": "Volunteer",
            "reason": reason,
        },
    )
    assert response.status_code == 200
    history = client.get(f"/api/members/{member['id']}/audit").json()["items"]
    assert history[0]["reason"] == reason
