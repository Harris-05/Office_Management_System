"""Authorized report preview, frozen workflow, history, and export endpoints."""

import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import defer

from app import report_service as service
from app.collections import branch_view
from app.dependencies import Principal, require_roles
from app.login import DB
from app.membership_contracts import Command, EventView, Limit, Offset, Person
from app.models import User, UserRole
from app.public_models import Branch
from app.report_contracts import NarrativeCommand, ReportReview, ReportStatus
from app.report_models import Report, ReportEvent, ReportRevision

router = APIRouter(prefix="/api/reports", tags=["weekly reports"])
Reader = Annotated[
    Principal,
    Depends(require_roles(UserRole.BRANCH_LEAD, UserRole.SUPER_ADMIN, UserRole.FINANCE_REVIEWER)),
]
Lead = Annotated[Principal, Depends(require_roles(UserRole.BRANCH_LEAD))]
Finance = Annotated[Principal, Depends(require_roles(UserRole.FINANCE_REVIEWER))]


def view(db, row, principal, with_sources=True):
    branch = db.get(Branch, row.branch_id)
    live = None
    preview_unavailable = False
    preview_reason = None
    if with_sources and row.status in {"Draft", "Returned"}:
        try:
            live = service.source_snapshot(db, row)
        except HTTPException as error:
            if error.status_code != 422 or row.status != "Returned" or row.snapshot is None:
                raise
            preview_unavailable = True
            preview_reason = (
                f"Live preview unavailable: {error.detail} "
                "The last submitted figures are shown. Resubmission is unavailable "
                "until a complete live preview can be produced."
            )
    editing = (
        principal.user.role == UserRole.BRANCH_LEAD
        and branch.lead_id == principal.user.id
        and branch.status == "Active"
        and row.status in {"Draft", "Returned"}
    )
    self_submitted = bool(
        db.scalar(
            select(ReportRevision.id)
            .where(ReportRevision.report_id == row.id, ReportRevision.actor_id == principal.user.id)
            .limit(1)
        )
    )
    result = {
        "id": row.id,
        "code": f"RPT-{branch.code}-{row.week_start.isoformat()}",
        "branch": branch_view(branch),
        "week_start": row.week_start,
        "week_end": row.week_start + timedelta(days=7),
        "status": row.status,
        "version": row.version,
        "revision_number": row.revision_number,
        "narrative": row.narrative,
        "preview_unavailable": preview_unavailable,
        "preview_unavailable_reason": preview_reason,
        "snapshot_basis": None,
        "discrepancy": preview_unavailable
        or (service.has_discrepancy(db, row) if with_sources else False),
        "can_edit": editing,
        "can_submit": editing
        and not preview_unavailable
        and row.week_start < service.monday(service.utc_now()),
        "can_review": principal.user.role == UserRole.FINANCE_REVIEWER
        and row.status == "Submitted"
        and not self_submitted,
        "submitted_at": row.submitted_at,
        "approved_at": row.approved_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if with_sources:
        result["snapshot"] = live if live is not None else row.snapshot
        result["snapshot_basis"] = (
            "last_submission"
            if preview_unavailable
            else "live_preview"
            if row.status in {"Draft", "Returned"}
            else "frozen_submission"
        )
    return result


@router.get("")
def register(
    db: DB,
    principal: Reader,
    branch_id: uuid.UUID | None = None,
    status: ReportStatus | None = None,
    from_week: date | None = None,
    to_week: date | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    if from_week and to_week and from_week > to_week:
        raise HTTPException(422, "The start week must be on or before the end week.")
    query = service.scoped(select(Report).options(defer(Report.snapshot)).join(Branch), principal)
    if branch_id:
        query = query.where(Report.branch_id == branch_id)
    if status:
        query = query.where(Report.status == status)
    if from_week:
        query = query.where(Report.week_start >= from_week)
    if to_week:
        query = query.where(Report.week_start <= to_week)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Report.week_start.desc(), Report.id).offset(offset).limit(limit)
    ).all()
    result = {
        "items": [view(db, row, principal, with_sources=False) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
    db.commit()
    return result


@router.get("/{record_id}")
def detail(record_id: uuid.UUID, db: DB, principal: Reader):
    result = view(db, service.record(db, principal, record_id), principal)
    db.commit()
    return result


def mutate(db, principal, record_id, action, body):
    row = service.transition(db, principal, record_id, action, body)
    result = view(db, row, principal)
    db.commit()
    return result


@router.post("/{record_id}/narrative")
def narrative(record_id: uuid.UUID, body: NarrativeCommand, db: DB, principal: Lead):
    return mutate(db, principal, record_id, "narrative", body)


@router.post("/{record_id}/submit")
def submit(record_id: uuid.UUID, body: Command, db: DB, principal: Lead):
    return mutate(db, principal, record_id, "submit", body)


@router.post("/{record_id}/approve")
def approve(record_id: uuid.UUID, body: ReportReview, db: DB, principal: Finance):
    return mutate(db, principal, record_id, "approve", body)


@router.post("/{record_id}/return")
def return_report(record_id: uuid.UUID, body: ReportReview, db: DB, principal: Finance):
    return mutate(db, principal, record_id, "return", body)


@router.get("/{record_id}/audit")
def history(record_id: uuid.UUID, db: DB, principal: Reader, offset: Offset = 0, limit: Limit = 25):
    service.record(db, principal, record_id)
    query = select(ReportEvent).where(ReportEvent.report_id == record_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(ReportEvent.created_at.desc(), ReportEvent.id).offset(offset).limit(limit)
    ).all()
    items = []
    for row in rows:
        actor = db.get(User, row.actor_id) if row.actor_id else None
        items.append(
            EventView(
                id=row.id,
                actor=Person(id=actor.id, name=actor.name) if actor else None,
                action=row.action,
                reason=row.reason,
                before=row.before,
                after=row.after,
                created_at=row.created_at,
            )
        )
    db.commit()
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@router.get("/{record_id}/revisions")
def revisions(
    record_id: uuid.UUID, db: DB, principal: Reader, offset: Offset = 0, limit: Limit = 25
):
    service.record(db, principal, record_id)
    query = select(ReportRevision).where(ReportRevision.report_id == record_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(ReportRevision.number.desc()).offset(offset).limit(limit)
    ).all()
    result = {
        "items": [
            {
                "id": row.id,
                "number": row.number,
                "narrative": row.narrative,
                "snapshot": row.snapshot,
                "submitted_at": row.submitted_at,
            }
            for row in rows
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
    db.commit()
    return result


@router.get("/{record_id}/export.pdf")
def pdf(record_id: uuid.UUID, db: DB, principal: Reader):
    from app.report_export import pdf_document

    result = view(db, service.record(db, principal, record_id), principal)
    content = pdf_document(result)
    db.commit()
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{result["code"]}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{record_id}/export.csv")
def csv(record_id: uuid.UUID, db: DB, principal: Reader):
    from app.report_export import csv_document

    result = view(db, service.record(db, principal, record_id), principal)
    content = csv_document(result)
    db.commit()
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{result["code"]}.csv"',
            "Cache-Control": "no-store",
        },
    )
