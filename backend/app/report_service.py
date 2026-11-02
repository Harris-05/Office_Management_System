"""Branch-first locked report lifecycle; callers own the transaction."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert

from app.collection_contracts import money
from app.collection_models import Collection
from app.collection_service import require_active, scoped
from app.models import UserRole
from app.public_models import Branch
from app.report_models import Report, ReportEvent, ReportRevision
from app.sessions import utc_now
from app.transfer_models import Transfer

PKT = ZoneInfo("Asia/Karachi")
EXPORT_LIMIT = 10000


def monday(value: date | datetime) -> date:
    value = value.astimezone(PKT).date() if isinstance(value, datetime) else value
    return value - timedelta(days=value.weekday())


def generate_drafts(db, now=None, from_week=None, limit=100):
    """Create at most limit missing weeks, oldest first; never commit or refresh reports.

    All registered branches remain eligible, including later paused/closed branches.
    NOT EXISTS avoids repeatedly scanning existing weeks; uniqueness handles workers.
    """
    if not 1 <= limit <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    now = now or utc_now()
    current = monday(now)
    if from_week is not None and monday(from_week) != from_week:
        raise ValueError("from_week must be a Monday")
    # Missing-week selection is bounded in SQL; no write occurs during HTTP reads.
    from sqlalchemy import Date, Interval, cast, func, literal, true

    start = (
        literal(from_week, type_=Date)
        if from_week
        else cast(
            func.date_trunc("week", Branch.created_at.op("AT TIME ZONE")("Asia/Karachi")), Date
        )
    )
    weeks = (
        func.generate_series(
            start, literal(current, type_=Date), literal(timedelta(days=7), type_=Interval)
        )
        .table_valued("week", with_ordinality="ordinality")
        .render_derived()
        .lateral()
    )
    week = cast(weeks.c.week, Date)
    candidates = db.execute(
        select(Branch.id, week.label("week_start"))
        .join(weeks, true())
        .where(
            ~exists(
                select(Report.id).where(Report.branch_id == Branch.id, Report.week_start == week)
            )
        )
        .order_by(week, Branch.id)
        .limit(limit)
    ).all()
    count = 0
    for branch_id, week_start in candidates:
        record_id = uuid.uuid4()
        created = db.scalar(
            insert(Report)
            .values(
                id=record_id,
                branch_id=branch_id,
                week_start=week_start,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_report_branch_week")
            .returning(Report.id)
        )
        if created:
            db.add(
                ReportEvent(
                    report_id=created,
                    actor_id=None,
                    action="report_generated",
                    reason="Scheduled weekly draft generation",
                    before=None,
                    after={"status": "Draft", "version": 1, "week_start": week_start.isoformat()},
                    created_at=now,
                )
            )
            count += 1
    db.flush()
    return count


def source_snapshot(db, report):
    end = report.week_start + timedelta(days=7)
    collections = db.scalars(
        select(Collection)
        .where(
            Collection.branch_id == report.branch_id,
            Collection.collected_on >= report.week_start,
            Collection.collected_on < end,
        )
        .order_by(Collection.id)
        .limit(EXPORT_LIMIT + 1)
        .execution_options(populate_existing=True)
    ).all()
    transfers = db.scalars(
        select(Transfer)
        .where(
            Transfer.branch_id == report.branch_id,
            Transfer.transferred_on >= report.week_start,
            Transfer.transferred_on < end,
        )
        .order_by(Transfer.id)
        .limit(EXPORT_LIMIT + 1)
        .execution_options(populate_existing=True)
    ).all()
    if len(collections) + len(transfers) > EXPORT_LIMIT:
        raise HTTPException(
            422,
            f"This report exceeds the {EXPORT_LIMIT:,} source record limit. "
            "Contact your administrator.",
        )
    return {
        "collections": [
            {
                "id": str(row.id),
                "version": row.version,
                "code": row.code,
                "amount": money(row.amount),
                "collected_on": row.collected_on.isoformat(),
                "collector_name": row.collector_name,
                "notes": row.notes,
            }
            for row in collections
        ],
        "transfers": [
            {
                "id": str(row.id),
                "version": row.version,
                "code": row.code,
                "amount": money(row.amount),
                "transferred_on": row.transferred_on.isoformat(),
                "status": row.status,
                "reference": row.reference,
                "notes": row.notes,
            }
            for row in transfers
        ],
        "collection_total": money(sum((row.amount for row in collections), Decimal("0.00"))),
        "collection_count": len(collections),
        "transfer_total": money(sum((row.amount for row in transfers), Decimal("0.00"))),
        "transfer_count": len(transfers),
        "transfer_status_totals": {
            status: money(
                sum((row.amount for row in transfers if row.status == status), Decimal("0.00"))
            )
            for status in ["Submitted", "Returned", "Confirmed", "Cancelled"]
        },
    }


def has_discrepancy(db, report):
    """An oversized live period still differs from a bounded frozen submission."""
    if report.status not in {"Submitted", "Approved"}:
        return False
    try:
        return report.snapshot != source_snapshot(db, report)
    except HTTPException as error:
        if error.status_code == 422:
            return True
        raise


def record(db, principal, record_id, lock=False):
    query = scoped(select(Report).join(Branch).where(Report.id == record_id), principal)
    if lock:
        query = query.with_for_update(of=Report).execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Report not found.")
    return row


def evidence(row):
    return {
        "status": row.status,
        "version": row.version,
        "revision_number": row.revision_number,
        "narrative": row.narrative,
    }


def transition(db, principal, record_id, action, body):
    candidate = record(db, principal, record_id)
    branch = db.scalar(
        select(Branch)
        .where(Branch.id == candidate.branch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    row = record(db, principal, record_id, lock=True)
    if row.version != body.expected_version:
        raise HTTPException(
            409, "This report changed. Reload the latest record; your inputs are preserved."
        )
    now = utc_now()
    before = evidence(row)
    if action in {"narrative", "submit"}:
        if principal.user.role != UserRole.BRANCH_LEAD or branch.lead_id != principal.user.id:
            raise HTTPException(
                403, "Only the assigned Branch Lead can edit or submit this report."
            )
        if row.status not in {"Draft", "Returned"}:
            raise HTTPException(409, "Only Draft or Returned reports can be edited or submitted.")
        require_active(branch)
        if action == "narrative":
            row.narrative = body.narrative
        else:
            if row.week_start >= monday(now):
                raise HTTPException(
                    409, "The reporting week is still open. Submit after Monday 00:00 Asia/Karachi."
                )
            row.snapshot = source_snapshot(db, row)
            row.revision_number += 1
            row.submitted_at, row.submitted_by_id = now, principal.user.id
            db.add(
                ReportRevision(
                    report_id=row.id,
                    number=row.revision_number,
                    actor_id=principal.user.id,
                    narrative=row.narrative,
                    snapshot=row.snapshot,
                    submitted_at=now,
                )
            )
            row.status = "Submitted"
    elif action in {"approve", "return"}:
        if principal.user.role != UserRole.FINANCE_REVIEWER or db.scalar(
            select(ReportRevision.id)
            .where(ReportRevision.report_id == row.id, ReportRevision.actor_id == principal.user.id)
            .limit(1)
        ):
            raise HTTPException(403, "An independent Finance Reviewer must review this report.")
        if row.status != "Submitted":
            raise HTTPException(409, "Only Submitted reports can be reviewed.")
        if action == "approve" and has_discrepancy(db, row):
            raise HTTPException(
                409,
                "Source figures changed. Return this report and request "
                "resubmission before approval.",
            )
        row.status = "Approved" if action == "approve" else "Returned"
        row.reviewer_id = principal.user.id
        if action == "approve":
            row.approved_at = now
    else:
        raise HTTPException(404, "Unknown report action.")
    row.version += 1
    row.updated_at = now
    action_name = (
        "resubmitted"
        if action == "submit" and row.revision_number > 1
        else {
            "narrative": "edited",
            "submit": "submitted",
            "approve": "approved",
            "return": "returned",
        }[action]
    )
    db.add(
        ReportEvent(
            report_id=row.id,
            actor_id=principal.user.id,
            action=f"report_{action_name}",
            reason=body.reason,
            before=before,
            after=evidence(row),
            created_at=now,
        )
    )
    db.flush()
    return row
