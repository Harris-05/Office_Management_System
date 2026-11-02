"""Independent synthetic ledger acceptance for dashboard totals and complete exports."""

import csv
import io
import uuid
from contextlib import ExitStack
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_collections import assigned_branch, create

from app.collection_models import Collection
from app.config import get_settings
from app.main import app
from app.models import User, UserRole
from app.report_models import Report
from app.report_service import source_snapshot
from app.sessions import create_session, utc_now


@pytest.fixture
def staff(db_session):
    with ExitStack() as stack:

        def client(role=UserRole.BRANCH_LEAD):
            user = db_session.scalar(select(User).where(User.role == role))
            session, token = create_session(db_session, user, utc_now())
            browser = stack.enter_context(TestClient(app, headers={"Origin": "http://testserver"}))
            browser.cookies.set(get_settings().cookie_name, token)
            browser.headers["X-CSRF-Token"] = session.csrf_token
            return browser, user

        yield client


@pytest.fixture
def ledger(staff, db_session):
    lead, user = staff()
    branch = assigned_branch(db_session, user)
    records = [
        create(lead, amount="0.10", collected_on="2020-01-31"),
        create(lead, amount="0.20", collected_on="2020-02-01"),
        create(lead, amount="1234.56", collected_on="2020-02-29"),
    ]
    # Business dates stay in 2020; entry locking is determined by creation time.
    oldest = db_session.get(Collection, uuid.UUID(records[0]["id"]))
    oldest.created_at = utc_now() - timedelta(days=8)
    oldest.locks_at = oldest.created_at + timedelta(days=7)
    db_session.commit()
    return lead, user, branch, records


def test_dashboard_exact_monthly_totals_and_paging_are_independent(ledger):
    lead, _, _, _ = ledger
    response = lead.get("/api/dashboard", params={"limit": 1})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["live_collections"] == {"count": 3, "amount": "1234.86", "currency": "PKR"}
    assert result["monthly"] == [
        {"month": "2020-01", "count": 1, "amount": "0.10"},
        {"month": "2020-02", "count": 2, "amount": "1234.76"},
    ]
    assert result["outstanding"]["total"] == 3
    assert len(result["outstanding"]["items"]) == 1
    assert result["outstanding"]["items"][0]["eligible"] is True
    next_page = lead.get("/api/dashboard", params={"offset": 1, "limit": 2}).json()
    assert all(not item["eligible"] for item in next_page["outstanding"]["items"])
    assert result["reconciliation"]["recorded"] == "1234.86"
    assert result["reconciliation"]["eligible"] == "0.10"


def test_date_filter_uses_business_date_but_balances_remain_cumulative(ledger):
    lead, _, _, _ = ledger
    result = lead.get("/api/dashboard?date_from=2020-02-01&date_to=2020-02-29").json()
    assert result["live_collections"]["count"] == 2
    assert result["live_collections"]["amount"] == "1234.76"
    assert result["monthly"] == [{"month": "2020-02", "count": 2, "amount": "1234.76"}]
    assert result["reconciliation"]["recorded"] == "1234.86"
    assert result["outstanding"]["total"] == 3
    assert lead.get("/api/dashboard?date_from=2020-03-01&date_to=2020-01-01").status_code == 422


def test_scope_is_server_enforced_and_revoked_assignment_removes_access(ledger, staff, db_session):
    lead, _, branch, _ = ledger
    other = assigned_branch(db_session, type("Lead", (), {"id": None})())
    assert lead.get(f"/api/dashboard?branch_id={other.id}").json()["live_collections"]["count"] == 0
    assert (
        len(
            list(
                csv.reader(
                    io.StringIO(
                        lead.get(f"/api/dashboard/export.csv?branch_id={other.id}").text.lstrip(
                            "\ufeff"
                        )
                    )
                )
            )
        )
        == 1
    )
    for role in [UserRole.SUPER_ADMIN, UserRole.FINANCE_REVIEWER]:
        browser, _ = staff(role)
        assert browser.get("/api/dashboard").json()["live_collections"]["count"] == 3
    branch.lead_id = None
    db_session.commit()
    assert lead.get("/api/dashboard").json()["live_collections"]["count"] == 0
    assert (
        len(
            list(
                csv.reader(io.StringIO(lead.get("/api/dashboard/export.csv").text.lstrip("\ufeff")))
            )
        )
        == 1
    )


@pytest.mark.parametrize("role", [UserRole.HR_LEAD, UserRole.CONTENT_EDITOR])
def test_dashboard_and_exports_deny_nonfinancial_roles(staff, role):
    browser, _ = staff(role)
    assert browser.get("/api/dashboard").status_code == 403
    assert browser.get("/api/dashboard/export.csv").status_code == 403


def test_exports_require_session():
    with TestClient(app) as browser:
        assert browser.get("/api/dashboard/export.csv").status_code == 401


def test_complete_filtered_csv_quotes_unicode_and_neutralizes_formulas(ledger):
    lead, _, _, records = ledger
    unsafe = create(
        lead,
        amount="2.01",
        collected_on="2020-02-20",
        collector_name="=1+1",
        notes='\t@SUM(1,2)\nاردو, "quoted"',
    )
    response = lead.get("/api/dashboard/export.csv?date_from=2020-02-01&date_to=2020-02-29")
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 3
    assert {row["Collection code"] for row in rows} == {
        records[1]["code"],
        records[2]["code"],
        unsafe["code"],
    }
    assert sum(Decimal(row["Amount (PKR)"]) for row in rows) == Decimal("1236.77")
    formula = next(row for row in rows if row["Collection code"] == unsafe["code"])
    assert formula["Collector"].startswith("'=1+1")
    assert formula["Notes"].startswith("'@SUM")
    assert 'اردو, "quoted"' in formula["Notes"]


def test_export_bound_rejects_instead_of_truncating(ledger, monkeypatch):
    from app import dashboard

    lead, _, _, _ = ledger
    monkeypatch.setattr(dashboard, "EXPORT_LIMIT", 2)
    response = lead.get("/api/dashboard/export.csv")
    assert response.status_code == 422
    assert "narrow" in response.json()["detail"].lower()


def test_transfer_states_reconcile_without_hiding_open_unallocated_entries(ledger, staff):
    lead, _, branch, records = ledger
    finance, _ = staff(UserRole.FINANCE_REVIEWER)
    response = lead.post(
        "/api/transfers",
        json={
            "request_id": str(uuid.uuid4()),
            "expected_branch_id": str(branch.id),
            "collection_ids": [records[0]["id"]],
            "transferred_on": "2020-02-01",
            "reference": "SYNTHETIC-DASHBOARD",
            "notes": "Acceptance fixture",
        },
    )
    assert response.status_code == 201, response.text
    transfer = response.json()
    expected = {
        "recorded": "1234.86",
        "not_submitted": "1234.76",
        "eligible": "0.00",
        "awaiting_confirmation": "0.10",
        "confirmed_received": "0.00",
        "currency": "PKR",
    }
    dashboard = lead.get("/api/dashboard").json()
    assert dashboard["reconciliation"] == expected
    assert dashboard["outstanding"]["total"] == 2
    assert all(not row["eligible"] for row in dashboard["outstanding"]["items"])
    confirmed = finance.post(
        f"/api/transfers/{transfer['id']}/confirm",
        json={
            "expected_version": transfer["version"],
            "reason": "Independent synthetic review",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    expected.update(awaiting_confirmation="0.00", confirmed_received="0.10")
    assert lead.get("/api/dashboard").json()["reconciliation"] == expected
    assert lead.get("/api/transfers/balances").json() == expected


def test_approved_summary_retains_frozen_values_and_flags_late_source_changes(ledger, db_session):
    lead, user, branch, _ = ledger
    report = Report(
        branch_id=branch.id,
        week_start=date(2020, 1, 27),
        status="Approved",
        approved_at=utc_now(),
        submitted_by_id=user.id,
    )
    report.snapshot = source_snapshot(db_session, report)
    db_session.add_all(
        [
            report,
            Report(branch_id=branch.id, week_start=date(2020, 2, 3), status="Draft"),
            Report(branch_id=branch.id, week_start=date(2020, 2, 10), status="Returned"),
        ]
    )
    db_session.commit()
    first = lead.get("/api/dashboard").json()["reports"]
    assert first == {
        "statuses": {"Draft": 1, "Submitted": 0, "Returned": 1, "Approved": 1},
        "approved_collection_total": "0.30",
        "approved_transfer_total": "0.00",
        "approved_discrepancies": 0,
    }
    create(lead, amount="1.11", collected_on="2020-02-01")
    changed = lead.get("/api/dashboard").json()["reports"]
    assert changed["approved_collection_total"] == "0.30"
    assert changed["approved_discrepancies"] == 1
    # Report status filters use the week start, while live rows use business dates.
    filtered = lead.get("/api/dashboard?date_from=2020-02-01&date_to=2020-02-29").json()
    assert filtered["live_collections"]["amount"] == "1235.87"
    assert filtered["reports"]["statuses"]["Approved"] == 0
    assert filtered["reports"]["statuses"]["Draft"] == 1
    assert filtered["reports"]["approved_collection_total"] == "0.00"
