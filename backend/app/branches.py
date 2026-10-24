import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.branch_contracts import (
    AuditPage,
    AuditView,
    BranchFields,
    BranchPage,
    BranchStatus,
    BranchUpdate,
    BranchView,
    LeadChange,
    LeadOption,
    LeadPage,
    LeadSummary,
    PublicationChange,
    StatusChange,
)
from app.dependencies import Principal, require_roles
from app.login import DB
from app.models import User, UserRole
from app.public_models import Branch, BranchAudit
from app.sessions import utc_now

router = APIRouter(prefix="/api/branches", tags=["branches"])
Reader = Annotated[Principal, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.BRANCH_LEAD))]
Admin = Annotated[Principal, Depends(require_roles(UserRole.SUPER_ADMIN))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=160, pattern=r"^[^\x00-\x1f\x7f]*$")]
TRANSITIONS = {
    "Forming": {"Active", "Closed"},
    "Active": {"Paused", "Closed"},
    "Paused": {"Active", "Closed"},
    "Closed": set(),
}


def scoped(query, principal):
    return (
        query.where(Branch.lead_id == principal.user.id)
        if principal.user.role == UserRole.BRANCH_LEAD
        else query
    )


def branch_record(db, branch_id, principal, lock=False):
    query = scoped(select(Branch).where(Branch.id == branch_id), principal)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Branch not found.")
    return row


def summary(user):
    return LeadSummary(id=user.id, name=user.name) if user else None


def view(db, row):
    return BranchView(
        **{name: getattr(row, name) for name in BranchFields.model_fields},
        id=row.id,
        code=row.code,
        slug=row.slug,
        status=row.status,
        is_published=row.is_published,
        is_demo=row.is_demo,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        lead=summary(db.get(User, row.lead_id)) if row.lead_id else None,
    )


def snapshot(row):
    return {
        **{name: getattr(row, name) for name in BranchFields.model_fields},
        "code": row.code,
        "status": row.status,
        "is_published": row.is_published,
        "lead_id": str(row.lead_id) if row.lead_id else None,
        "is_demo": row.is_demo,
    }


def check_version(row, expected):
    if row.version != expected:
        raise HTTPException(
            409, "This branch changed since you opened it. Reload before trying again."
        )


def editable(row):
    if row.status == "Closed":
        raise HTTPException(422, "Closed branches are archived and cannot be edited.")


def save(db, row, principal, action, before, reason=None):
    after = snapshot(row)
    if before != after:
        if before is not None:
            row.version += 1
        row.updated_at = utc_now()
        db.add(
            BranchAudit(
                branch_id=row.id,
                actor_id=principal.user.id,
                action=action,
                reason=reason,
                created_at=utc_now(),
                before=before,
                after=after,
            )
        )
    try:
        db.flush()
        result = view(db, row)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "This lead is already assigned to another branch. Reload and choose an available lead.",
        ) from None
    return result


@router.get("", response_model=BranchPage)
def list_branches(
    db: DB,
    principal: Reader,
    offset: Offset = 0,
    limit: Limit = 25,
    search: Search = "",
    status: BranchStatus | None = None,
):
    query = scoped(select(Branch), principal)
    term = search.strip()
    if term:
        query = query.where(
            or_(
                Branch.name.icontains(term, autoescape=True),
                Branch.name_ur.icontains(term, autoescape=True),
                Branch.city.icontains(term, autoescape=True),
                Branch.city_ur.icontains(term, autoescape=True),
                (
                    "BR-"
                    + func.lpad(
                        Branch.number.cast(String),
                        func.greatest(6, func.length(Branch.number.cast(String))),
                        "0",
                    )
                ).icontains(term, autoescape=True),
            )
        )
    if status:
        query = query.where(Branch.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Branch.number).offset(offset).limit(limit)).all()
    result = BranchPage(
        items=[view(db, row) for row in rows], total=total, offset=offset, limit=limit
    )
    db.commit()
    return result


@router.post("", response_model=BranchView, status_code=201)
def create_branch(data: BranchFields, db: DB, principal: Admin):
    row = Branch(
        **data.model_dump(),
        slug=f"branch-{uuid.uuid4().hex}",
        status="Forming",
        is_published=False,
        is_demo=False,
    )
    db.add(row)
    db.flush()
    return save(db, row, principal, "created", None)


@router.get("/eligible-leads", response_model=LeadPage)
def eligible_leads(
    db: DB,
    principal: Admin,
    offset: Offset = 0,
    limit: Limit = 25,
    search: Search = "",
):
    query = (
        select(User, Branch)
        .outerjoin(Branch, Branch.lead_id == User.id)
        .where(User.role == UserRole.BRANCH_LEAD, User.is_active)
    )
    if search.strip():
        query = query.where(
            or_(
                User.name.icontains(search.strip(), autoescape=True),
                User.email.icontains(search.strip(), autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = [
        LeadOption(
            id=user.id,
            name=user.name,
            email=user.email,
            branch_id=branch.id if branch else None,
            branch_code=branch.code if branch else None,
        )
        for user, branch in db.execute(
            query.order_by(User.name, User.id).offset(offset).limit(limit)
        )
    ]
    result = LeadPage(items=items, total=total, offset=offset, limit=limit)
    db.commit()
    return result


@router.get("/{branch_id}", response_model=BranchView)
def get_branch(branch_id: uuid.UUID, db: DB, principal: Reader):
    result = view(db, branch_record(db, branch_id, principal))
    db.commit()
    return result


@router.post("/{branch_id}/update", response_model=BranchView)
def update_branch(branch_id: uuid.UUID, data: BranchUpdate, db: DB, principal: Admin):
    row = branch_record(db, branch_id, principal, lock=True)
    check_version(row, data.expected_version)
    editable(row)
    before = snapshot(row)
    for key, value in data.model_dump(exclude={"expected_version"}).items():
        setattr(row, key, value)
    return save(db, row, principal, "details_updated", before)


@router.post("/{branch_id}/status", response_model=BranchView)
def change_status(branch_id: uuid.UUID, data: StatusChange, db: DB, principal: Admin):
    row = branch_record(db, branch_id, principal, lock=True)
    check_version(row, data.expected_version)
    before = snapshot(row)
    if data.status != row.status:
        if data.status not in TRANSITIONS[row.status]:
            raise HTTPException(422, "This status transition is not allowed.")
        row.status = data.status
        if row.status != "Active":
            row.is_published = False
        if row.status == "Closed":
            row.lead_id = None
    return save(db, row, principal, "status_changed", before, data.reason)


@router.post("/{branch_id}/lead", response_model=BranchView)
def change_lead(branch_id: uuid.UUID, data: LeadChange, db: DB, principal: Admin):
    row = branch_record(db, branch_id, principal, lock=True)
    check_version(row, data.expected_version)
    editable(row)
    if data.lead_id is not None:
        lead = db.get(User, data.lead_id)
        if not lead or not lead.is_active or lead.role != UserRole.BRANCH_LEAD:
            raise HTTPException(422, "Choose an active Branch Lead account.")
    before = snapshot(row)
    row.lead_id = data.lead_id
    return save(db, row, principal, "lead_changed", before)


@router.post("/{branch_id}/publication", response_model=BranchView)
def change_publication(branch_id: uuid.UUID, data: PublicationChange, db: DB, principal: Admin):
    row = branch_record(db, branch_id, principal, lock=True)
    check_version(row, data.expected_version)
    editable(row)
    if data.is_published and row.status != "Active":
        raise HTTPException(422, "Only Active branches can be published.")
    before = snapshot(row)
    row.is_published = data.is_published
    return save(db, row, principal, "publication_changed", before)


@router.get("/{branch_id}/audit", response_model=AuditPage)
def audit_history(
    branch_id: uuid.UUID, db: DB, principal: Reader, offset: Offset = 0, limit: Limit = 25
):
    branch_record(db, branch_id, principal)
    query = (
        select(BranchAudit, User)
        .outerjoin(User, User.id == BranchAudit.actor_id)
        .where(BranchAudit.branch_id == branch_id)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = [
        AuditView(
            id=row.id,
            actor=summary(actor),
            action=row.action,
            reason=row.reason,
            before=row.before,
            after=row.after,
            created_at=row.created_at,
        )
        for row, actor in db.execute(
            query.order_by(BranchAudit.created_at.desc(), BranchAudit.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]
    result = AuditPage(items=items, total=total, offset=offset, limit=limit)
    db.commit()
    return result
