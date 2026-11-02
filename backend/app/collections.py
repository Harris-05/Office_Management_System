import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String, func, or_, select

from app import collection_service as service
from app.collection_contracts import (
    CollectionCreate,
    CollectionPage,
    CollectionUpdate,
    CollectionView,
    money,
)
from app.collection_models import Collection, CollectionEvent
from app.dependencies import Principal, require_roles
from app.login import DB
from app.membership_contracts import BranchOption, EventView, Limit, Offset, Page, Person, Search
from app.models import User, UserRole
from app.public_models import Branch

router = APIRouter(prefix="/api/collections", tags=["offline collections"])
Reader = Annotated[
    Principal,
    Depends(require_roles(UserRole.BRANCH_LEAD, UserRole.SUPER_ADMIN, UserRole.FINANCE_REVIEWER)),
]
Lead = Annotated[Principal, Depends(require_roles(UserRole.BRANCH_LEAD))]


def branch_view(row):
    return BranchOption(id=row.id, code=row.code, name=row.name, status=row.status)


def view(db, row, principal, now, branch=None, creator=None):
    branch = branch if branch is not None else db.get(Branch, row.branch_id)
    creator = (
        creator
        if creator is not None
        else (db.get(User, row.created_by_id) if row.created_by_id else None)
    )
    locked = now >= row.locks_at
    return CollectionView(
        id=row.id,
        code=row.code,
        branch=branch_view(branch),
        amount=money(row.amount),
        currency=row.currency,
        collected_on=row.collected_on,
        collector_name=row.collector_name,
        notes=row.notes,
        creator=Person(id=creator.id, name=creator.name) if creator else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        locks_at=row.locks_at,
        version=row.version,
        is_locked=locked,
        can_edit=not locked
        and branch.status == "Active"
        and branch.lead_id == principal.user.id
        and principal.user.role == UserRole.BRANCH_LEAD,
        server_time=now,
    )


@router.get("", response_model=CollectionPage)
def collections(
    db: DB,
    principal: Reader,
    search: Search = "",
    branch_id: uuid.UUID | None = None,
    window: Literal["All", "Open", "Locked"] = "All",
    from_date: date | None = None,
    to_date: date | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(422, "The start date must be on or before the end date.")
    now = service.utc_now()
    query = service.scoped(
        select(Collection).select_from(Collection).join(Branch, Branch.id == Collection.branch_id),
        principal,
    )
    if branch_id:
        query = query.where(Collection.branch_id == branch_id)
    if window != "All":
        query = query.where(
            Collection.locks_at <= now if window == "Locked" else Collection.locks_at > now
        )
    if from_date:
        query = query.where(Collection.collected_on >= from_date)
    if to_date:
        query = query.where(Collection.collected_on <= to_date)
    if search.strip():
        code = "COL-" + func.lpad(
            Collection.number.cast(String),
            func.greatest(6, func.length(Collection.number.cast(String))),
            "0",
        )
        query = query.where(
            or_(
                code.icontains(search.strip(), autoescape=True),
                Collection.collector_name.icontains(search.strip(), autoescape=True),
            )
        )
    filtered = query.subquery()
    total, amount = db.execute(
        select(
            func.count(), func.coalesce(func.sum(filtered.c.amount), Decimal("0.00"))
        ).select_from(filtered)
    ).one()
    rows = db.execute(
        query.add_columns(Branch, User)
        .outerjoin(User, User.id == Collection.created_by_id)
        .order_by(Collection.created_at.desc(), Collection.id)
        .offset(offset)
        .limit(limit)
    ).all()
    result = CollectionPage(
        items=[view(db, row, principal, now, branch, creator) for row, branch, creator in rows],
        total=total,
        total_amount=amount,
        offset=offset,
        limit=limit,
        server_time=now,
    )
    db.commit()
    return result


@router.get("/branches", response_model=Page[BranchOption])
def branches(db: DB, principal: Reader, offset: Offset = 0, limit: Limit = 25):
    query = service.scoped(select(Branch), principal)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Branch.name, Branch.id).offset(offset).limit(limit)).all()
    result = {
        "items": [branch_view(row) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
    db.commit()
    return result


@router.post("", response_model=CollectionView, status_code=201)
def create(body: CollectionCreate, db: DB, principal: Lead):
    row = service.create_collection(db, principal, body)
    result = view(db, row, principal, service.utc_now())
    db.commit()
    return result


@router.get("/{record_id}", response_model=CollectionView)
def detail(record_id: uuid.UUID, db: DB, principal: Reader):
    result = view(
        db, service.collection_record(db, principal, record_id), principal, service.utc_now()
    )
    db.commit()
    return result


@router.post("/{record_id}/update", response_model=CollectionView)
def update(record_id: uuid.UUID, body: CollectionUpdate, db: DB, principal: Lead):
    row = service.update_collection(db, principal, record_id, body)
    result = view(db, row, principal, service.utc_now())
    db.commit()
    return result


@router.get("/{record_id}/audit", response_model=Page[EventView])
def history(record_id: uuid.UUID, db: DB, principal: Reader, offset: Offset = 0, limit: Limit = 25):
    service.collection_record(db, principal, record_id)
    query = select(CollectionEvent).where(CollectionEvent.collection_id == record_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(CollectionEvent.created_at.desc(), CollectionEvent.id)
        .offset(offset)
        .limit(limit)
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
