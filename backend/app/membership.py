"""HR-only application review and member register."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, func, or_, select

from app.dependencies import Principal, require_roles
from app.login import DB
from app.membership_contracts import (
    ApplicationView,
    BranchOption,
    EventView,
    Limit,
    MemberCommand,
    MemberStatus,
    MemberSummary,
    MemberView,
    Offset,
    Page,
    Person,
    ReviewCommand,
    Search,
)
from app.membership_models import ApplicationEvent, Member, MemberEvent
from app.membership_service import (
    application_record,
    member_record,
    review_application,
    update_member,
)
from app.models import User, UserRole
from app.public_models import Branch, PublicSubmission
from app.sessions import utc_now

router = APIRouter(prefix="/api", tags=["applications and members"])
HR = Annotated[Principal, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_LEAD))]


def person(row):
    return Person(id=row.id, name=row.name) if row else None


def branch_view(row):
    return BranchOption(id=row.id, code=row.code, name=row.name, status=row.status) if row else None


def application_view(db, row):
    member = db.scalar(select(Member).where(Member.source_id == row.id))
    return ApplicationView(
        id=row.id,
        name=row.name,
        email=row.email,
        subject=row.subject,
        message=row.message,
        branch=branch_view(db.get(Branch, row.branch_id)),
        status=row.review_status,
        version=row.review_version,
        created_at=row.created_at,
        expires_at=row.expires_at,
        reviewed_at=row.reviewed_at,
        reviewer=person(db.get(User, row.reviewer_id)) if row.reviewer_id else None,
        reason=row.review_reason,
        member=MemberSummary(id=member.id, code=member.code, name=member.name) if member else None,
    )


def member_view(db, row):
    source = db.get(PublicSubmission, row.source_id) if row.source_id else None
    return MemberView(
        id=row.id,
        code=row.code,
        name=row.name,
        email=row.email,
        branch=branch_view(db.get(Branch, row.branch_id)),
        source_id=source.id if source and source.expires_at > utc_now() else None,
        status=row.status,
        team=row.team,
        organisational_role=row.organisational_role,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def page(db, query, offset, limit, mapper):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items = [mapper(row) for row in db.scalars(query.offset(offset).limit(limit)).all()]
    result = {"items": items, "total": total, "offset": offset, "limit": limit}
    db.commit()
    return result


def event_view(db, row):
    return EventView(
        id=row.id,
        actor=person(db.get(User, row.actor_id)) if row.actor_id else None,
        action=row.action,
        reason=row.reason,
        before=row.before,
        after=row.after,
        created_at=row.created_at,
    )


@router.get("/applications", response_model=Page[ApplicationView])
def applications(
    db: DB,
    principal: HR,
    search: Search = "",
    status: Literal["Pending", "Accepted", "Declined", "All"] = "Pending",
    branch_id: uuid.UUID | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = select(PublicSubmission).where(
        PublicSubmission.kind == "volunteer", PublicSubmission.expires_at > utc_now()
    )
    if status != "All":
        query = query.where(PublicSubmission.review_status == status)
    if branch_id:
        query = query.where(PublicSubmission.branch_id == branch_id)
    if search.strip():
        query = query.where(
            or_(
                PublicSubmission.name.icontains(search.strip(), autoescape=True),
                PublicSubmission.email.icontains(search.strip(), autoescape=True),
            )
        )
    return page(
        db,
        query.order_by(PublicSubmission.created_at.desc(), PublicSubmission.id),
        offset,
        limit,
        lambda row: application_view(db, row),
    )


@router.get("/applications/{record_id}", response_model=ApplicationView)
def application_detail(record_id: uuid.UUID, db: DB, principal: HR):
    result = application_view(db, application_record(db, record_id))
    db.commit()
    return result


@router.post("/applications/{record_id}/review", response_model=ApplicationView)
def decide(record_id: uuid.UUID, body: ReviewCommand, db: DB, principal: HR):
    result = application_view(db, review_application(db, principal, record_id, body))
    db.commit()
    return result


@router.get("/applications/{record_id}/audit", response_model=Page[EventView])
def application_audit(
    record_id: uuid.UUID, db: DB, principal: HR, offset: Offset = 0, limit: Limit = 25
):
    application_record(db, record_id)
    query = select(ApplicationEvent).where(ApplicationEvent.application_id == record_id)
    return page(
        db,
        query.order_by(ApplicationEvent.created_at.desc(), ApplicationEvent.id),
        offset,
        limit,
        lambda row: event_view(db, row),
    )


@router.get("/hr/branches", response_model=Page[BranchOption])
def branches(
    db: DB,
    principal: HR,
    search: Search = "",
    status: Literal["Forming", "Active", "Paused", "Closed"] | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = select(Branch)
    if status:
        query = query.where(Branch.status == status)
    if search.strip():
        query = query.where(
            or_(
                Branch.name.icontains(search.strip(), autoescape=True),
                Branch.name_ur.icontains(search.strip(), autoescape=True),
            )
        )
    return page(db, query.order_by(Branch.name, Branch.id), offset, limit, branch_view)


@router.get("/members", response_model=Page[MemberView])
def members(
    db: DB,
    principal: HR,
    search: Search = "",
    status: MemberStatus | None = None,
    branch_id: uuid.UUID | None = None,
    team: Annotated[str, Query(max_length=80, pattern=r"^[^\x00-\x1f\x7f]*$")] = "",
    organisational_role: Annotated[str, Query(max_length=100, pattern=r"^[^\x00-\x1f\x7f]*$")] = "",
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = select(Member)
    for column, value in [
        (Member.status, status),
        (Member.branch_id, branch_id),
        (Member.team, team.strip()),
        (Member.organisational_role, organisational_role.strip()),
    ]:
        if value:
            query = query.where(column == value)
    if search.strip():
        code = "MEM-" + func.lpad(
            Member.number.cast(String),
            func.greatest(6, func.length(Member.number.cast(String))),
            "0",
        )
        query = query.where(
            or_(
                Member.name.icontains(search.strip(), autoescape=True),
                Member.email.icontains(search.strip(), autoescape=True),
                code.icontains(search.strip(), autoescape=True),
            )
        )
    return page(
        db,
        query.order_by(Member.created_at.desc(), Member.id),
        offset,
        limit,
        lambda row: member_view(db, row),
    )


@router.get("/members/{record_id}", response_model=MemberView)
def member_detail(record_id: uuid.UUID, db: DB, principal: HR):
    result = member_view(db, member_record(db, record_id))
    db.commit()
    return result


@router.post("/members/{record_id}/update", response_model=MemberView)
def edit_member(record_id: uuid.UUID, body: MemberCommand, db: DB, principal: HR):
    result = member_view(db, update_member(db, principal, record_id, body))
    db.commit()
    return result


@router.get("/members/{record_id}/audit", response_model=Page[EventView])
def member_audit(
    record_id: uuid.UUID, db: DB, principal: HR, offset: Offset = 0, limit: Limit = 25
):
    member_record(db, record_id)
    query = select(MemberEvent).where(MemberEvent.member_id == record_id)
    return page(
        db,
        query.order_by(MemberEvent.created_at.desc(), MemberEvent.id),
        offset,
        limit,
        lambda row: event_view(db, row),
    )
