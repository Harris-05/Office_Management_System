import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import String, case, func, or_, select

from app import transfer_service as service
from app.collection_contracts import CollectionView, money
from app.collection_models import Collection
from app.collection_service import scoped
from app.collections import branch_view
from app.collections import view as collection_view
from app.dependencies import Principal, require_roles
from app.login import DB
from app.membership_contracts import EventView, Limit, Offset, Page, Person, Search
from app.models import User, UserRole
from app.public_models import Branch
from app.transfer_contracts import (
    TransferBalances,
    TransferCommand,
    TransferCreate,
    TransferItemView,
    TransferResubmit,
    TransferStatus,
    TransferView,
)
from app.transfer_models import Transfer, TransferEvent, TransferItem

router = APIRouter(prefix="/api/transfers", tags=["transfers to head office"])
Reader = Annotated[
    Principal,
    Depends(require_roles(UserRole.BRANCH_LEAD, UserRole.FINANCE_REVIEWER, UserRole.SUPER_ADMIN)),
]
Lead = Annotated[Principal, Depends(require_roles(UserRole.BRANCH_LEAD))]
Finance = Annotated[Principal, Depends(require_roles(UserRole.FINANCE_REVIEWER))]


def person(row):
    return Person(id=row.id, name=row.name) if row else None


def views(db, rows, principal):
    if not rows:
        return []
    branches = {
        row.id: row
        for row in db.scalars(select(Branch).where(Branch.id.in_({r.branch_id for r in rows})))
    }
    people_ids = {value for row in rows for value in (row.created_by_id, row.reviewer_id) if value}
    people = {row.id: row for row in db.scalars(select(User).where(User.id.in_(people_ids)))}
    items = defaultdict(list)
    for item, collection in db.execute(
        select(TransferItem, Collection)
        .join(Collection)
        .where(TransferItem.transfer_id.in_([row.id for row in rows]))
        .order_by(Collection.number)
    ):
        items[item.transfer_id].append(
            TransferItemView(
                collection_id=collection.id,
                code=collection.code,
                amount=money(item.amount),
                collection_version=item.collection_version,
                collected_on=collection.collected_on,
            )
        )
    result = []
    for row in rows:
        branch = branches[row.branch_id]
        lead = principal.user.role == UserRole.BRANCH_LEAD and branch.lead_id == principal.user.id
        review = (
            principal.user.role == UserRole.FINANCE_REVIEWER
            and row.created_by_id != principal.user.id
            and row.status == "Submitted"
        )
        result.append(
            TransferView(
                id=row.id,
                code=row.code,
                branch=branch_view(branch),
                amount=money(row.amount),
                transferred_on=row.transferred_on,
                reference=row.reference,
                notes=row.notes,
                status=row.status,
                version=row.version,
                creator=person(people.get(row.created_by_id)),
                reviewer=person(people.get(row.reviewer_id)),
                created_at=row.created_at,
                updated_at=row.updated_at,
                confirmed_at=row.confirmed_at,
                items=items[row.id],
                can_confirm=review,
                can_return=review,
                can_cancel=lead and row.status in {"Submitted", "Returned"},
                can_resubmit=lead and row.status == "Returned" and branch.status == "Active",
            )
        )
    return result


@router.get("", response_model=Page[TransferView])
def register(
    db: DB,
    principal: Reader,
    search: Search = "",
    branch_id: uuid.UUID | None = None,
    status: TransferStatus | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = scoped(select(Transfer).join(Branch), principal)
    if branch_id:
        query = query.where(Transfer.branch_id == branch_id)
    if status:
        query = query.where(Transfer.status == status)
    if search.strip():
        number = Transfer.number.cast(String)
        code = "TRF-" + func.lpad(number, func.greatest(6, func.length(number)), "0")
        query = query.where(
            or_(
                code.icontains(search.strip(), autoescape=True),
                Transfer.reference.icontains(search.strip(), autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(Transfer.created_at.desc(), Transfer.id).offset(offset).limit(limit)
    ).all()
    result = {"items": views(db, rows, principal), "total": total, "offset": offset, "limit": limit}
    db.commit()
    return result


@router.get("/balances", response_model=TransferBalances)
def balances(db: DB, principal: Reader, branch_id: uuid.UUID | None = None):
    query = scoped(
        select(
            Collection.amount.label("amount"),
            Collection.locks_at.label("locks_at"),
            Transfer.status.label("status"),
        )
        .select_from(Collection)
        .join(Branch, Branch.id == Collection.branch_id)
        .outerjoin(
            TransferItem, (TransferItem.collection_id == Collection.id) & TransferItem.is_active
        )
        .outerjoin(Transfer, Transfer.id == TransferItem.transfer_id),
        principal,
    )
    if branch_id:
        query = query.where(Collection.branch_id == branch_id)
    rows = query.subquery()
    now = service.utc_now()

    def total(expr):
        return func.coalesce(func.sum(expr), Decimal("0.00"))

    recorded, pending, confirmed, eligible = db.execute(
        select(
            total(rows.c.amount),
            total(case((rows.c.status == "Submitted", rows.c.amount), else_=0)),
            total(case((rows.c.status == "Confirmed", rows.c.amount), else_=0)),
            total(
                case(((rows.c.status.is_(None)) & (rows.c.locks_at <= now), rows.c.amount), else_=0)
            ),
        ).select_from(rows)
    ).one()
    result = TransferBalances(
        recorded=money(recorded),
        not_submitted=money(recorded - pending - confirmed),
        eligible=money(eligible),
        awaiting_confirmation=money(pending),
        confirmed_received=money(confirmed),
    )
    db.commit()
    return result


@router.get("/eligible", response_model=Page[CollectionView])
def eligible(db: DB, principal: Lead, offset: Offset = 0, limit: Limit = 25):
    now = service.utc_now()
    query = service.eligible_query(principal, now)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.add_columns(Branch, User)
        .outerjoin(User, User.id == Collection.created_by_id)
        .order_by(Collection.locks_at, Collection.id)
        .offset(offset)
        .limit(limit)
    ).all()
    result = {
        "items": [
            collection_view(db, row, principal, now, branch, creator)
            for row, branch, creator in rows
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
    db.commit()
    return result


def saved(db, row, principal):
    result = views(db, [row], principal)[0]
    db.commit()
    return result


@router.post("", response_model=TransferView, status_code=201)
def create(body: TransferCreate, db: DB, principal: Lead):
    return saved(db, service.create_transfer(db, principal, body), principal)


@router.get("/{record_id}", response_model=TransferView)
def detail(record_id: uuid.UUID, db: DB, principal: Reader):
    return saved(db, service.transfer_record(db, principal, record_id), principal)


@router.post("/{record_id}/confirm", response_model=TransferView)
def confirm(record_id: uuid.UUID, body: TransferCommand, db: DB, principal: Finance):
    return saved(db, service.transition(db, principal, record_id, "confirm", body), principal)


@router.post("/{record_id}/return", response_model=TransferView)
def return_transfer(record_id: uuid.UUID, body: TransferCommand, db: DB, principal: Finance):
    return saved(db, service.transition(db, principal, record_id, "return", body), principal)


@router.post("/{record_id}/cancel", response_model=TransferView)
def cancel(record_id: uuid.UUID, body: TransferCommand, db: DB, principal: Lead):
    return saved(db, service.transition(db, principal, record_id, "cancel", body), principal)


@router.post("/{record_id}/resubmit", response_model=TransferView)
def resubmit(record_id: uuid.UUID, body: TransferResubmit, db: DB, principal: Lead):
    return saved(db, service.transition(db, principal, record_id, "resubmit", body), principal)


@router.get("/{record_id}/audit", response_model=Page[EventView])
def history(record_id: uuid.UUID, db: DB, principal: Reader, offset: Offset = 0, limit: Limit = 25):
    service.transfer_record(db, principal, record_id)
    query = select(TransferEvent).where(TransferEvent.transfer_id == record_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.add_columns(User)
        .outerjoin(User, User.id == TransferEvent.actor_id)
        .order_by(TransferEvent.created_at.desc(), TransferEvent.id)
        .offset(offset)
        .limit(limit)
    ).all()
    result = {
        "items": [
            EventView(
                id=row.id,
                actor=person(actor),
                action=row.action,
                reason=row.reason,
                before=row.before,
                after=row.after,
                created_at=row.created_at,
            )
            for row, actor in rows
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
    db.commit()
    return result
