import re
import uuid
from contextlib import ExitStack
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from test_branches import fields

from app import collection_service as service
from app.collection_models import Collection, CollectionEvent
from app.config import get_settings
from app.main import app
from app.models import User, UserRole
from app.public_models import Branch
from app.sessions import create_session, utc_now


@pytest.fixture
def staff(db_session):
    with ExitStack() as stack:

        def client(role=UserRole.BRANCH_LEAD):
            user = db_session.scalar(select(User).where(User.role == role))
            row, token = create_session(db_session, user, utc_now())
            browser = stack.enter_context(TestClient(app, headers={"Origin": "http://testserver"}))
            browser.cookies.set(get_settings().cookie_name, token)
            browser.headers["X-CSRF-Token"] = row.csrf_token
            return browser, user

        yield client


def assigned_branch(db, user, **changes):
    row = Branch(**fields(), slug=uuid.uuid4().hex, status="Active", lead_id=user.id, **changes)
    db.add(row)
    db.commit()
    return row


def body(**changes):
    return {
        "request_id": str(uuid.uuid4()),
        "expected_branch_id": str(uuid.uuid4()),
        "amount": "10.10",
        "collected_on": "2020-01-01",
        "collector_name": "Test collector",
        "notes": "Labelled synthetic collection.",
        **changes,
    }


def create(client, **changes):
    changes.setdefault(
        "expected_branch_id", client.get("/api/collections/branches").json()["items"][0]["id"]
    )
    response = client.post("/api/collections", json=body(**changes))
    assert response.status_code == 201, response.text
    return response.json()


def update_body(row, **changes):
    return {
        "expected_version": row["version"],
        "amount": row["amount"],
        "collected_on": row["collected_on"],
        "collector_name": row["collector_name"],
        "notes": row["notes"],
        "reason": "Correct collection details",
        **changes,
    }


def test_create_retry_and_changed_reference_are_safe(staff, db_session):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    payload = body(expected_branch_id=str(branch.id))
    first = lead.post("/api/collections", json=payload)
    assert first.status_code == 201, first.text
    row = first.json()
    assert re.fullmatch(r"COL-\d{6,}", row["code"])
    assert row["branch"]["id"] == str(branch.id)
    assert row["amount"] == "10.10" and row["currency"] == "PKR"
    assert row["can_edit"] and not row["is_locked"]
    assert lead.post("/api/collections", json=payload).json()["id"] == row["id"]
    payload["amount"] = "12.34"
    assert lead.post("/api/collections", json=payload).status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Collection)) == 1
    assert db_session.scalar(select(func.count()).select_from(CollectionEvent)) == 1
    assert lead.get(f"/api/collections/{row['id']}/audit").json()["total"] == 1


def test_creation_time_deadline_survives_historical_date_and_edits(staff, db_session, monkeypatch):
    lead, user = staff()
    assigned_branch(db_session, user)
    now = utc_now()
    monkeypatch.setattr(service, "utc_now", lambda: now)
    row = create(lead)
    assert row["locks_at"] != row["collected_on"]
    path = f"/api/collections/{row['id']}/update"
    response = lead.post(path, json=update_body(row, amount="20.25", collected_on="2021-02-03"))
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["version"] == 2 and edited["amount"] == "20.25"
    assert edited["created_at"] == row["created_at"] and edited["locks_at"] == row["locks_at"]
    assert lead.post(path, json=update_body(edited)).json()["version"] == 2
    assert lead.post(path, json=update_body(row)).status_code == 409
    monkeypatch.setattr(
        service, "utc_now", lambda: now + timedelta(days=7) - timedelta(microseconds=1)
    )
    assert lead.post(path, json=update_body(edited, notes="Last valid edit")).status_code == 200
    latest = lead.get(f"/api/collections/{row['id']}").json()
    monkeypatch.setattr(service, "utc_now", lambda: now + timedelta(days=7))
    assert lead.post(path, json=update_body(latest, amount="99.99")).status_code == 409
    locked = lead.get(f"/api/collections/{row['id']}").json()
    assert locked["is_locked"] and not locked["can_edit"] and locked["amount"] == "20.25"
    assert lead.get("/api/collections?window=Locked").json()["total"] == 1
    assert lead.get("/api/collections?window=Open").json()["total"] == 0


def test_totals_are_exact_across_pages_and_filtered(staff, db_session):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    first, second = (
        create(lead, amount="0.10"),
        create(lead, amount="0.20", collected_on="2022-02-02"),
    )
    result = lead.get("/api/collections?limit=1").json()
    assert len(result["items"]) == 1 and result["total"] == 2 and result["total_amount"] == "0.30"
    assert lead.get("/api/collections?from_date=2022-01-01").json()["total_amount"] == "0.20"
    assert lead.get("/api/collections?to_date=2021-01-01").json()["total_amount"] == "0.10"
    assert lead.get("/api/collections?from_date=2023-01-01&to_date=2020-01-01").status_code == 422
    assert lead.get("/api/collections", params={"search": first["code"]}).json()["total"] == 1
    assert lead.get("/api/collections", params={"branch_id": str(branch.id)}).json()["total"] == 2
    assert Decimal(first["amount"]) + Decimal(second["amount"]) == Decimal("0.30")


@pytest.mark.parametrize("role", [UserRole.SUPER_ADMIN, UserRole.FINANCE_REVIEWER])
def test_admin_finance_are_read_only(staff, db_session, role):
    lead, user = staff()
    assigned_branch(db_session, user)
    row = create(lead)
    reader, _ = staff(role)
    assert reader.get("/api/collections").json()["total"] == 1
    assert not reader.get(f"/api/collections/{row['id']}").json()["can_edit"]
    assert reader.get(f"/api/collections/{row['id']}/audit").status_code == 200
    assert reader.get("/api/collections/branches").json()["total"] == 1
    assert reader.post("/api/collections", json=body()).status_code == 403
    assert (
        reader.post(f"/api/collections/{row['id']}/update", json=update_body(row)).status_code
        == 403
    )


@pytest.mark.parametrize("status", ["Forming", "Paused", "Closed"])
def test_non_active_branch_rejects_new_and_existing_writes(staff, db_session, status):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    row = create(lead)
    branch.status = status
    if status == "Closed":
        branch.lead_id = None
    db_session.commit()
    assert lead.post(
        "/api/collections", json=body(expected_branch_id=str(branch.id))
    ).status_code == (403 if status == "Closed" else 422)
    assert lead.post(f"/api/collections/{row['id']}/update", json=update_body(row)).status_code == (
        404 if status == "Closed" else 422
    )
    if status != "Closed":
        assert not lead.get(f"/api/collections/{row['id']}").json()["can_edit"]


def test_scope_and_assignment_revocation(staff, db_session):
    lead, user = staff()
    assert lead.get("/api/collections").json()["total"] == 0
    assert lead.post("/api/collections", json=body()).status_code == 403
    branch = assigned_branch(db_session, user)
    row = create(lead)
    branch.lead_id = None
    db_session.commit()
    assert lead.get("/api/collections").json()["total"] == 0
    for suffix in ["", "/audit"]:
        assert lead.get(f"/api/collections/{row['id']}{suffix}").status_code == 404
    assert (
        lead.post(f"/api/collections/{row['id']}/update", json=update_body(row)).status_code == 404
    )


@pytest.mark.parametrize(
    "amount", ["0", "-1", "1.001", "NaN", "Infinity", "1e3", "10000000000.00", True, 1.23, 1]
)
def test_invalid_money_never_reaches_numeric_storage(staff, db_session, amount):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    assert (
        lead.post(
            "/api/collections", json=body(amount=amount, expected_branch_id=str(branch.id))
        ).status_code
        == 422
    )


def test_safe_inputs_and_denied_roles(staff, db_session):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    for changes in [
        {"collected_on": "2999-01-01"},
        {"collector_name": "bad\x00name"},
        {"branch_id": str(branch.id)},
        {"created_at": utc_now().isoformat()},
    ]:
        assert (
            lead.post(
                "/api/collections", json=body(expected_branch_id=str(branch.id), **changes)
            ).status_code
            == 422
        )
    assert lead.get("/api/collections", params={"search": "\x00"}).status_code == 422
    csrf = lead.headers.pop("X-CSRF-Token")
    assert lead.post("/api/collections", json=body()).status_code == 403
    lead.headers["X-CSRF-Token"] = csrf
    for role in [UserRole.HR_LEAD, UserRole.CONTENT_EDITOR]:
        reader, _ = staff(role)
        for path in [
            "/api/collections",
            "/api/collections/branches",
            f"/api/collections/{uuid.uuid4()}/audit",
        ]:
            assert reader.get(path).status_code == 403


def test_creation_rejects_a_changed_branch_context(staff, db_session):
    lead, user = staff()
    previous = assigned_branch(db_session, user)
    previous_id = previous.id
    previous.lead_id = None
    db_session.commit()
    current = assigned_branch(db_session, user)
    response = lead.post("/api/collections", json=body(expected_branch_id=str(previous_id)))
    assert response.status_code == 409, response.text
    assert current.id != previous_id
    assert db_session.scalar(select(func.count()).select_from(Collection)) == 0


def test_audit_failure_rolls_back_collection(staff, db_session):
    lead, user = staff()
    assigned_branch(db_session, user)

    def unavailable(mapper, connection, target):
        raise RuntimeError("Audit unavailable")

    event.listen(CollectionEvent, "before_insert", unavailable)
    try:
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            create(lead)
        db_session.rollback()
    finally:
        event.remove(CollectionEvent, "before_insert", unavailable)
    assert db_session.scalar(select(func.count()).select_from(Collection)) == 0


def test_ledger_summaries_do_not_fetch_each_branch_separately(staff, db_session):
    lead, user = staff()
    assigned_branch(db_session, user)
    for _ in range(4):
        create(lead)
    reader, _ = staff(UserRole.FINANCE_REVIEWER)
    statements = []
    connection = db_session.connection()

    def observe(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(connection, "before_cursor_execute", observe)
    try:
        result = reader.get("/api/collections")
        assert result.status_code == 200 and result.json()["total"] == 4
    finally:
        event.remove(connection, "before_cursor_execute", observe)
    assert (
        sum(statement.lstrip().startswith("SELECT public_branches.") for statement in statements)
        <= 1
    )
