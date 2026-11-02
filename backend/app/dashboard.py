"""Read-only scoped ledger overview and complete, bounded collection exports."""

import csv
import io
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import case, func, select

from app.collection_contracts import money
from app.collection_models import Collection
from app.collection_service import scoped
from app.collections import branch_view
from app.dependencies import Principal, require_roles
from app.login import DB
from app.membership_contracts import BranchOption, Limit, Offset, Page
from app.models import UserRole
from app.public_models import Branch
from app.sessions import utc_now
from app.transfer_contracts import TransferBalances
from app.transfer_models import Transfer, TransferItem

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
Reader = Annotated[
    Principal,
    Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.FINANCE_REVIEWER, UserRole.BRANCH_LEAD)),
]
EXPORT_LIMIT = 10_000


class LiveTotal(BaseModel):
    count: int
    amount: str
    currency: str = "PKR"


class MonthlyTotal(BaseModel):
    month: str
    count: int
    amount: str


class OutstandingCollection(BaseModel):
    id: uuid.UUID
    code: str
    branch: BranchOption
    amount: str
    collected_on: date
    locks_at: datetime
    eligible: bool


class ReportSummary(BaseModel):
    statuses: dict[str, int]
    approved_collection_total: str
    approved_transfer_total: str
    approved_discrepancies: int


class DashboardView(BaseModel):
    live_collections: LiveTotal
    monthly: list[MonthlyTotal]
    reconciliation: TransferBalances
    outstanding: Page[OutstandingCollection]
    reports: ReportSummary
    server_time: datetime


def validate_dates(date_from, date_to):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "The start date must be on or before the end date.")


def collection_query(principal, branch_id=None, date_from=None, date_to=None):
    query = scoped(select(Collection).join(Branch, Branch.id == Collection.branch_id), principal)
    if branch_id:
        query = query.where(Collection.branch_id == branch_id)
    if date_from:
        query = query.where(Collection.collected_on >= date_from)
    if date_to:
        query = query.where(Collection.collected_on <= date_to)
    return query


def report_summary(db, principal, branch_id, date_from, date_to):
    # Imports are local so the ledger/export module also works during report maintenance.
    from app.report_models import Report
    from app.report_service import has_discrepancy

    query = scoped(select(Report).join(Branch, Branch.id == Report.branch_id), principal)
    if branch_id:
        query = query.where(Report.branch_id == branch_id)
    if date_from:
        query = query.where(Report.week_start >= date_from)
    if date_to:
        query = query.where(Report.week_start <= date_to)
    statuses = dict.fromkeys(["Draft", "Submitted", "Returned", "Approved"], 0)
    collection_total = transfer_total = Decimal("0.00")
    discrepancies = 0
    for report in db.scalars(query.order_by(Report.week_start, Report.id)):
        statuses[report.status] += 1
        if report.status == "Approved":
            collection_total += Decimal(report.snapshot["collection_total"])
            transfer_total += Decimal(report.snapshot["transfer_total"])
            discrepancies += has_discrepancy(db, report)
    return ReportSummary(
        statuses=statuses,
        approved_collection_total=money(collection_total),
        approved_transfer_total=money(transfer_total),
        approved_discrepancies=discrepancies,
    )


def reconciliation_and_outstanding(db, principal, branch_id, now, offset, limit):
    query = (
        collection_query(principal, branch_id)
        .outerjoin(
            TransferItem, (TransferItem.collection_id == Collection.id) & TransferItem.is_active
        )
        .outerjoin(Transfer, Transfer.id == TransferItem.transfer_id)
    )
    rows = query.with_only_columns(
        Collection.amount.label("amount"),
        Collection.locks_at.label("locks_at"),
        Transfer.status.label("status"),
    ).subquery()

    def total(expression):
        return func.coalesce(func.sum(expression), Decimal("0.00"))

    recorded, pending, confirmed, eligible = db.execute(
        select(
            total(rows.c.amount),
            total(case((rows.c.status == "Submitted", rows.c.amount), else_=0)),
            total(case((rows.c.status == "Confirmed", rows.c.amount), else_=0)),
            total(
                case((rows.c.status.is_(None) & (rows.c.locks_at <= now), rows.c.amount), else_=0)
            ),
        )
    ).one()
    balances = TransferBalances(
        recorded=money(recorded),
        not_submitted=money(recorded - pending - confirmed),
        eligible=money(eligible),
        awaiting_confirmation=money(pending),
        confirmed_received=money(confirmed),
    )
    outstanding_query = query.where(TransferItem.id.is_(None))
    count = db.scalar(select(func.count()).select_from(outstanding_query.subquery()))
    outstanding = db.execute(
        outstanding_query.add_columns(Branch)
        .order_by(Collection.locks_at, Collection.number)
        .offset(offset)
        .limit(limit)
    ).all()
    return balances, {
        "items": [
            OutstandingCollection(
                id=row.id,
                code=row.code,
                branch=branch_view(branch),
                amount=money(row.amount),
                collected_on=row.collected_on,
                locks_at=row.locks_at,
                eligible=row.locks_at <= now,
            )
            for row, branch in outstanding
        ],
        "total": count,
        "offset": offset,
        "limit": limit,
    }


@router.get("", response_model=DashboardView)
def dashboard(
    db: DB,
    principal: Reader,
    branch_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    validate_dates(date_from, date_to)
    now = utc_now()
    filtered = collection_query(principal, branch_id, date_from, date_to).subquery()
    count, amount = db.execute(
        select(
            func.count(), func.coalesce(func.sum(filtered.c.amount), Decimal("0.00"))
        ).select_from(filtered)
    ).one()
    month = func.to_char(filtered.c.collected_on, "YYYY-MM")
    monthly = db.execute(
        select(month, func.count(), func.sum(filtered.c.amount)).group_by(month).order_by(month)
    ).all()
    balances, outstanding = reconciliation_and_outstanding(
        db, principal, branch_id, now, offset, limit
    )
    result = DashboardView(
        live_collections=LiveTotal(count=count, amount=money(amount)),
        monthly=[
            MonthlyTotal(month=month, count=count, amount=money(amount))
            for month, count, amount in monthly
        ],
        reconciliation=balances,
        outstanding=outstanding,
        reports=report_summary(db, principal, branch_id, date_from, date_to),
        server_time=now,
    )
    db.commit()
    return result


def csv_cell(value):
    text = str(value)
    # Spreadsheet applications ignore initial whitespace before formula introducers.
    stripped = text.lstrip()
    return "'" + stripped if stripped.startswith(("=", "+", "-", "@")) else text


@router.get("/export.csv")
def export_collections(
    db: DB,
    principal: Reader,
    branch_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    validate_dates(date_from, date_to)
    rows = db.execute(
        collection_query(principal, branch_id, date_from, date_to)
        .add_columns(Branch)
        .order_by(Collection.collected_on, Collection.number)
        .limit(EXPORT_LIMIT + 1)
    ).all()
    if len(rows) > EXPORT_LIMIT:
        raise HTTPException(
            422,
            f"This export exceeds {EXPORT_LIMIT:,} collections. Narrow the date range or branch.",
        )
    output = io.StringIO(newline="")
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(
        [
            "Collection code",
            "Branch code",
            "Branch",
            "Amount (PKR)",
            "Collected on",
            "Collector",
            "Notes",
            "Version",
            "Created at",
            "Locks at",
        ]
    )
    for row, branch in rows:
        writer.writerow(
            [
                csv_cell(value)
                for value in [
                    row.code,
                    branch.code,
                    branch.name,
                    money(row.amount),
                    row.collected_on.isoformat(),
                    row.collector_name,
                    row.notes,
                    row.version,
                    row.created_at.isoformat(),
                    row.locks_at.isoformat(),
                ]
            ]
        )
    db.commit()
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="collections.csv"',
            "Cache-Control": "no-store",
        },
    )
