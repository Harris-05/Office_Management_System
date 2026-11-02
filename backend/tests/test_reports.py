"""Synthetic weekly-report lifecycle, boundary, and independence acceptance tests."""

from datetime import UTC, date, datetime, timedelta

import pytest
import test_collections as collection_tests
from sqlalchemy import func, select
from test_collections import assigned_branch, create

from app import report_service as service
from app.models import UserRole
from app.report_models import Report, ReportEvent, ReportRevision

NOW = datetime(2026, 11, 2, 8, tzinfo=UTC)
staff = collection_tests.staff


def draft(db, branch, monkeypatch):
    branch.created_at = NOW - timedelta(days=7)
    db.flush()
    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    assert service.generate_drafts(db, now=NOW) == 2
    db.commit()
    return db.scalar(select(Report).where(Report.week_start == date(2026, 10, 26)))


def command(client, row, action, **changes):
    return client.post(
        f"/api/reports/{row['id']}/{action}",
        json={"expected_version": row["version"], "reason": "Synthetic test decision", **changes},
    )


def test_repeat_safe_bounded_generation_and_get_is_read_only(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    branch.created_at = NOW - timedelta(days=21)
    db_session.flush()
    assert service.generate_drafts(db_session, now=NOW, limit=2) == 2
    assert service.generate_drafts(db_session, now=NOW, limit=2) == 2
    assert service.generate_drafts(db_session, now=NOW, limit=2) == 0
    db_session.commit()
    count = db_session.scalar(select(func.count()).select_from(Report))
    assert lead.get("/api/reports").status_code == 200
    assert db_session.scalar(select(func.count()).select_from(Report)) == count == 4
    events = db_session.scalars(select(ReportEvent)).all()
    assert len(events) == 4 and all(event.actor_id is None for event in events)


def test_report_frozen_revisions_stale_approval_and_discrepancy(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    record = draft(db_session, branch, monkeypatch)
    create(lead, amount="0.01", collected_on="2026-10-26")
    create(lead, amount="0.02", collected_on="2026-11-01")
    create(lead, amount="9.99", collected_on="2026-11-02")
    row = lead.get(f"/api/reports/{record.id}").json()
    assert row["snapshot"]["collection_total"] == "0.03"
    edited = command(lead, row, "narrative", narrative="Synthetic narrative / ہفتہ وار رپورٹ")
    assert edited.status_code == 200, edited.text
    submitted = command(lead, edited.json(), "submit")
    assert submitted.status_code == 200, submitted.text
    row = submitted.json()
    create(lead, amount="0.03", collected_on="2026-10-29")
    stale = command(finance, row, "approve", acknowledge=True)
    assert stale.status_code == 409, stale.text
    returned = command(finance, row, "return", acknowledge=True)
    assert returned.status_code == 200, returned.text
    refreshed = command(lead, returned.json(), "submit")
    assert refreshed.status_code == 200, refreshed.text
    approved = command(finance, refreshed.json(), "approve", acknowledge=True)
    assert approved.status_code == 200, approved.text
    assert approved.json()["snapshot"]["collection_total"] == "0.06"
    create(lead, amount="0.04", collected_on="2026-10-30")
    frozen = lead.get(f"/api/reports/{record.id}").json()
    assert frozen["snapshot"]["collection_total"] == "0.06" and frozen["discrepancy"]
    revisions = lead.get(f"/api/reports/{record.id}/revisions").json()
    assert revisions["total"] == 2
    assert db_session.scalar(select(func.count()).select_from(ReportRevision)) == 2
    assert command(lead, frozen, "narrative", narrative="Cannot rewrite").status_code == 409
    pdf = lead.get(f"/api/reports/{record.id}/export.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    csv = lead.get(f"/api/reports/{record.id}/export.csv")
    assert csv.status_code == 200 and "0.06" in csv.text


def test_closed_week_active_writes_and_independent_review(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    record = draft(db_session, branch, monkeypatch)
    current = db_session.scalar(select(Report).where(Report.week_start == date(2026, 11, 2)))
    row = lead.get(f"/api/reports/{current.id}").json()
    assert command(lead, row, "submit").status_code == 409
    row = lead.get(f"/api/reports/{record.id}").json()
    row = command(lead, row, "submit").json()
    user.role = UserRole.FINANCE_REVIEWER
    db_session.commit()
    assert command(lead, row, "approve", acknowledge=True).status_code == 403
    user.role = UserRole.BRANCH_LEAD
    branch.status = "Paused"
    db_session.commit()
    assert command(finance, row, "approve", acknowledge=True).status_code == 200


@pytest.mark.parametrize("role", list(UserRole))
def test_report_role_scope(staff, db_session, monkeypatch, role):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    report = draft(db_session, branch, monkeypatch)
    client, _ = staff(role)
    allowed = role in {UserRole.BRANCH_LEAD, UserRole.FINANCE_REVIEWER, UserRole.SUPER_ADMIN}
    assert client.get("/api/reports").status_code == (200 if allowed else 403)
    assert client.get(f"/api/reports/{report.id}/export.pdf").status_code == (
        200 if allowed else 403
    )
    if role != UserRole.BRANCH_LEAD:
        response = client.post(
            f"/api/reports/{report.id}/narrative",
            json={"expected_version": 1, "reason": "Test reason", "narrative": "Changed"},
        )
        assert response.status_code == 403


def test_report_scope_reassignment_and_review_acknowledgement(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    report = draft(db_session, branch, monkeypatch)
    row = lead.get(f"/api/reports/{report.id}").json()
    submitted = command(lead, row, "submit").json()
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    assert command(finance, submitted, "approve").status_code == 422
    branch.lead_id = None
    db_session.commit()
    assert lead.get(f"/api/reports/{report.id}").status_code == 404
    assert lead.get(f"/api/reports/{report.id}/export.csv").status_code == 404
    assert lead.get("/api/reports").json()["total"] == 0
    assert command(finance, submitted, "approve", acknowledge=True).status_code == 200


def test_submission_audit_failure_rolls_back_revision(staff, db_session, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    lead, user = staff()
    branch = assigned_branch(db_session, user)
    report = draft(db_session, branch, monkeypatch)
    row = lead.get(f"/api/reports/{report.id}").json()
    add = db_session.add

    def broken_add(value, **kwargs):
        if isinstance(value, ReportEvent):
            raise SQLAlchemyError("Synthetic report audit failure")
        return add(value, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "add", broken_add)
        assert command(lead, row, "submit").status_code == 503
    db_session.rollback()
    assert db_session.get(Report, report.id).status == "Draft"
    assert db_session.scalar(select(func.count()).select_from(ReportRevision)) == 0


def test_snapshot_transfer_status_revisions_and_backfill(staff, db_session, monkeypatch):
    import uuid
    from decimal import Decimal

    from app.transfer_models import Transfer

    lead, user = staff()
    branch = assigned_branch(db_session, user)
    report = draft(db_session, branch, monkeypatch)
    for number, status in enumerate(["Submitted", "Returned", "Confirmed", "Cancelled"], start=1):
        db_session.add(
            Transfer(
                branch_id=branch.id,
                created_by_id=user.id,
                request_id=uuid.uuid4(),
                creation_fingerprint="0" * 64,
                amount=Decimal(f"0.0{number}"),
                transferred_on=date(2026, 10, 28),
                reference="Synthetic transfer",
                notes="",
                status=status,
                confirmed_at=NOW if status == "Confirmed" else None,
            )
        )
    db_session.commit()
    snapshot = lead.get(f"/api/reports/{report.id}").json()["snapshot"]
    assert snapshot["transfer_total"] == "0.10"
    assert snapshot["transfer_status_totals"] == {
        "Submitted": "0.01",
        "Returned": "0.02",
        "Confirmed": "0.03",
        "Cancelled": "0.04",
    }
    branch.status = "Paused"
    db_session.commit()
    assert service.generate_drafts(db_session, now=NOW + timedelta(days=7), limit=1) == 1
    assert service.generate_drafts(db_session, now=NOW, from_week=date(2026, 10, 19), limit=1) == 1
    with pytest.raises(ValueError):
        service.generate_drafts(db_session, from_week=date(2026, 10, 20))


def test_week_boundary_is_monday_in_pakistan():
    assert service.monday(datetime(2026, 11, 1, 18, 59, 59, tzinfo=UTC)) == date(2026, 10, 26)
    assert service.monday(datetime(2026, 11, 1, 19, 0, 0, tzinfo=UTC)) == date(2026, 11, 2)


def test_oversized_live_period_can_be_returned_without_losing_frozen_history(
    staff, db_session, monkeypatch
):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    report = draft(db_session, branch, monkeypatch)
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    monkeypatch.setattr(service, "EXPORT_LIMIT", 1)
    create(lead, amount="0.01", collected_on="2026-10-27")
    row = lead.get(f"/api/reports/{report.id}").json()
    submitted = command(lead, row, "submit")
    assert submitted.status_code == 200, submitted.text
    frozen = submitted.json()
    create(lead, amount="0.02", collected_on="2026-10-28")
    assert command(finance, frozen, "approve", acknowledge=True).status_code == 409
    returned = command(finance, frozen, "return", acknowledge=True)
    assert returned.status_code == 200, returned.text
    row = returned.json()
    assert row["status"] == "Returned"
    assert row["preview_unavailable"] and row["preview_unavailable_reason"]
    assert row["snapshot_basis"] == "last_submission"
    assert row["discrepancy"] and not row["can_submit"]
    assert row["snapshot"]["collection_total"] == "0.01"
    detail = lead.get(f"/api/reports/{report.id}")
    assert detail.status_code == 200
    revisions = lead.get(f"/api/reports/{report.id}/revisions").json()
    assert revisions["total"] == 1
    assert revisions["items"][0]["snapshot"]["collection_total"] == "0.01"
    assert lead.get(f"/api/reports/{report.id}/export.pdf").status_code == 200
    csv = lead.get(f"/api/reports/{report.id}/export.csv")
    assert csv.status_code == 200
    assert "Last submitted figures" in csv.text and "0.01" in csv.text


def test_register_omits_source_snapshots_but_detail_keeps_them(staff, db_session, monkeypatch):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    report = draft(db_session, branch, monkeypatch)
    create(lead, amount="0.01", collected_on="2026-10-27")
    row = lead.get(f"/api/reports/{report.id}").json()
    submitted = command(lead, row, "submit")
    assert submitted.status_code == 200
    register = lead.get("/api/reports").json()
    assert all("snapshot" not in item for item in register["items"])
    detail = lead.get(f"/api/reports/{report.id}").json()
    assert detail["snapshot"]["collection_total"] == "0.01"
