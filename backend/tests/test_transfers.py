import uuid
from datetime import datetime, timedelta

import pytest
import test_collections as collection_tests
from sqlalchemy import select
from test_collections import assigned_branch, create

from app import collection_service
from app.models import UserRole
from app.sessions import utc_now

staff = collection_tests.staff


def locked_collection(client, monkeypatch, **changes):
    with monkeypatch.context() as patch:
        patch.setattr(collection_service, "utc_now", lambda: utc_now() - timedelta(days=8))
        return create(client, **changes)


def payload(branch, rows, **changes):
    return {
        "request_id": str(uuid.uuid4()),
        "expected_branch_id": str(branch.id),
        "collection_ids": [row["id"] for row in rows],
        "transferred_on": "2026-01-01",
        "reference": "SYNTHETIC-TRANSFER",
        "notes": "Test transfer, not a real deposit.",
        **changes,
    }


def submit(client, branch, rows, **changes):
    response = client.post("/api/transfers", json=payload(branch, rows, **changes))
    assert response.status_code == 201, response.text
    return response.json()


def action(client, row, name, **changes):
    return client.post(
        f"/api/transfers/{row['id']}/{name}",
        json={"expected_version": row["version"], "reason": "Synthetic review reason", **changes},
    )


def test_transfer_lifecycle_and_balances(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    rows = [locked_collection(lead, monkeypatch, amount=value) for value in ["0.01", "0.02"]]
    create(lead, amount="0.03")
    assert lead.get("/api/transfers/eligible").json()["total"] == 2
    transfer = submit(lead, branch, rows)
    assert transfer["amount"] == "0.03" and transfer["status"] == "Submitted"
    assert transfer["code"].startswith("TRF-")
    assert transfer["can_cancel"] and not transfer["can_confirm"]
    assert lead.get("/api/transfers/eligible").json()["total"] == 0
    balances = lead.get("/api/transfers/balances").json()
    assert balances == {
        "recorded": "0.06",
        "not_submitted": "0.03",
        "eligible": "0.00",
        "awaiting_confirmation": "0.03",
        "confirmed_received": "0.00",
        "currency": "PKR",
    }
    returned = action(finance, transfer, "return").json()
    assert returned["status"] == "Returned" and returned["version"] == 2
    assert lead.get("/api/transfers/eligible").json()["total"] == 2
    resubmitted = action(
        lead, returned, "resubmit", transferred_on="2026-01-02", reference="CORRECTED-REF", notes=""
    )
    assert resubmitted.status_code == 200, resubmitted.text
    confirmed = action(finance, resubmitted.json(), "confirm")
    assert confirmed.status_code == 200, confirmed.text
    row = confirmed.json()
    assert row["status"] == "Confirmed" and row["confirmed_at"] and row["reviewer"]
    assert not any(row[key] for key in ["can_confirm", "can_return", "can_cancel", "can_resubmit"])
    assert lead.get("/api/transfers/balances").json()["confirmed_received"] == "0.03"
    assert action(lead, row, "cancel").status_code == 409
    assert action(finance, row, "return").status_code == 409
    history = finance.get(f"/api/transfers/{row['id']}/audit").json()
    assert history["total"] == 4
    assert {event["action"] for event in history["items"]} == {
        "transfer_submitted",
        "transfer_returned",
        "transfer_resubmitted",
        "transfer_confirmed",
    }


def test_transfer_retry_fixed_batch_reallocation_and_cancel(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    rows = [locked_collection(lead, monkeypatch)]
    data = payload(branch, rows)
    first = lead.post("/api/transfers", json=data)
    assert first.status_code == 201, first.text
    row = first.json()
    assert lead.post("/api/transfers", json=data).json()["id"] == row["id"]
    assert lead.post("/api/transfers", json={**data, "notes": "Changed"}).status_code == 409
    assert lead.post("/api/transfers", json=payload(branch, rows)).status_code == 409
    returned = action(finance, row, "return").json()
    newer = submit(lead, branch, rows)
    failed = action(
        lead, returned, "resubmit", transferred_on="2026-01-01", reference="RETRY", notes=""
    )
    assert failed.status_code == 409
    assert action(lead, newer, "cancel").json()["status"] == "Cancelled"
    assert action(lead, returned, "cancel").json()["status"] == "Cancelled"
    assert lead.get("/api/transfers/eligible").json()["total"] == 1
    assert lead.get("/api/transfers/balances").json()["not_submitted"] == "10.10"
    assert lead.get(f"/api/transfers/{row['id']}/audit").json()["total"] == 3


def test_transfer_eligibility_scope_and_boundary(staff, db_session, monkeypatch):
    from app import transfer_service

    lead, user = staff()
    branch = assigned_branch(db_session, user)
    unlocked = create(lead)
    assert lead.post("/api/transfers", json=payload(branch, [unlocked])).status_code == 409
    deadline = datetime.fromisoformat(unlocked["locks_at"])
    monkeypatch.setattr(transfer_service, "utc_now", lambda: deadline - timedelta(microseconds=1))
    assert lead.post("/api/transfers", json=payload(branch, [unlocked])).status_code == 409
    monkeypatch.setattr(transfer_service, "utc_now", lambda: deadline)
    submitted = submit(lead, branch, [unlocked])
    assert submitted["amount"] == "10.10"
    assert (
        lead.post(
            "/api/transfers", json=payload(branch, [unlocked], expected_branch_id=str(uuid.uuid4()))
        ).status_code
        == 409
    )
    branch.lead_id = None
    db_session.commit()
    assert lead.get(f"/api/transfers/{submitted['id']}").status_code == 404
    assert lead.get(f"/api/transfers/{submitted['id']}/audit").status_code == 404
    assert lead.get("/api/transfers").json()["total"] == 0
    assert lead.get("/api/transfers/balances").json()["recorded"] == "0.00"


@pytest.mark.parametrize("role", list(UserRole))
def test_transfer_role_permissions(staff, db_session, monkeypatch, role):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    rows = [locked_collection(lead, monkeypatch)]
    row = submit(lead, branch, rows)
    client, _ = staff(role)
    reader = role in {UserRole.SUPER_ADMIN, UserRole.FINANCE_REVIEWER, UserRole.BRANCH_LEAD}
    assert client.get("/api/transfers").status_code == (200 if reader else 403)
    assert client.get("/api/transfers/balances").status_code == (200 if reader else 403)
    assert client.get(f"/api/transfers/{row['id']}").status_code == (200 if reader else 403)
    if role != UserRole.BRANCH_LEAD:
        assert client.post("/api/transfers", json=payload(branch, rows)).status_code == 403
        assert action(client, row, "cancel").status_code == 403
    if role != UserRole.FINANCE_REVIEWER:
        assert action(client, row, "confirm").status_code == 403
    assert client.get("/api/transfers/eligible").status_code == (
        200 if role == UserRole.BRANCH_LEAD else 403
    )


def test_transfer_validation_and_stale_review(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    rows = [locked_collection(lead, monkeypatch)]
    data = payload(branch, rows)
    for changes in [
        {"collection_ids": []},
        {"collection_ids": [rows[0]["id"]] * 2},
        {"collection_ids": [str(uuid.uuid4())] * 101},
        {"reference": "\x00bad"},
        {"reference": "x"},
        {"transferred_on": "2999-01-01"},
        {"amount": "1.00"},
        {"transferred_on": "2019-01-01"},
    ]:
        assert lead.post("/api/transfers", json={**data, **changes}).status_code == 422
    assert (
        lead.post(
            "/api/transfers", json={**data, "collection_ids": [str(uuid.uuid4())]}
        ).status_code
        == 404
    )
    row = submit(lead, branch, rows)
    assert action(finance, row, "return", reason="x").status_code == 422
    assert action(finance, row, "confirm", expected_version=9).status_code == 409
    assert action(finance, row, "return", reason="Multiline\nreview reason").status_code == 200
    assert action(finance, row, "confirm").status_code == 409
    assert (
        finance.get("/api/transfers?status=Returned&search=SYNTHETIC&limit=1").json()["total"] == 1
    )


def test_transfer_inactive_branch_cancel_finance_and_csrf(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    rows = [locked_collection(lead, monkeypatch)]
    row = submit(lead, branch, rows)
    branch.status = "Paused"
    db_session.commit()
    assert lead.post("/api/transfers", json=payload(branch, rows)).status_code == 422
    returned = action(finance, row, "return").json()
    assert (
        action(
            lead, returned, "resubmit", transferred_on="2026-01-01", reference="RETRY", notes=""
        ).status_code
        == 422
    )
    assert action(lead, returned, "cancel").status_code == 200
    del lead.headers["X-CSRF-Token"]
    assert lead.post("/api/transfers", json=payload(branch, rows)).status_code == 403
    lead.cookies.clear()
    assert lead.get("/api/transfers").status_code == 401


def test_transfer_audit_failure_rolls_back(staff, db_session, monkeypatch):
    from app.transfer_models import Transfer, TransferEvent, TransferItem

    lead, user = staff()
    branch = assigned_branch(db_session, user)
    rows = [locked_collection(lead, monkeypatch)]
    original_add = db_session.add

    def broken_add(row, **kwargs):
        if isinstance(row, TransferEvent):
            from sqlalchemy.exc import SQLAlchemyError

            raise SQLAlchemyError("synthetic audit failure")
        return original_add(row, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "add", broken_add)
        assert lead.post("/api/transfers", json=payload(branch, rows)).status_code == 503
    db_session.rollback()
    assert db_session.scalar(select(Transfer)) is None
    assert db_session.scalar(select(TransferItem)) is None


def test_transfer_large_totals_filters_and_mixed_branch(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    rows = [locked_collection(lead, monkeypatch, amount="9999999999.99") for _ in range(2)]
    row = submit(lead, branch, rows)
    assert row["amount"] == "19999999999.98"
    admin, _ = staff(UserRole.SUPER_ADMIN)
    assert admin.get("/api/transfers/balances").json()["recorded"] == "19999999999.98"
    assert (
        admin.get(f"/api/transfers/balances?branch_id={uuid.uuid4()}").json()["recorded"] == "0.00"
    )
    assert admin.get(f"/api/transfers?search={row['code']}&limit=1").json()["total"] == 1
    assert admin.get(f"/api/transfers?branch_id={uuid.uuid4()}").json()["total"] == 0
    assert "creation_fingerprint" not in row and "request_id" not in row
    branch.lead_id = None
    db_session.commit()
    next_branch = assigned_branch(db_session, user)
    assert lead.post("/api/transfers", json=payload(next_branch, rows)).status_code == 404


def test_finance_settles_closed_branch_but_cannot_review_own_submission(
    staff, db_session, monkeypatch
):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    row = submit(lead, branch, [locked_collection(lead, monkeypatch)])
    branch.status, branch.lead_id = "Closed", None
    user.role = UserRole.FINANCE_REVIEWER
    db_session.commit()
    # The same authenticated identity must not review its own record after a role change.
    assert action(lead, row, "confirm").status_code == 403
    from app.models import User

    finance_user = db_session.scalar(select(User).where(User.email == "finance@example.test"))
    user.role = UserRole.BRANCH_LEAD
    db_session.commit()
    finance, actual = staff(UserRole.FINANCE_REVIEWER)
    assert actual.id == finance_user.id
    result = action(finance, row, "confirm")
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "Confirmed"
