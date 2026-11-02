import hashlib
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import exists, select

from app.collection_contracts import money
from app.collection_models import Collection
from app.collection_service import lock_branch, scoped
from app.models import UserRole
from app.public_models import Branch
from app.sessions import utc_now
from app.transfer_models import Transfer, TransferEvent, TransferItem


def transfer_record(db, principal, record_id, lock=False):
    query = scoped(select(Transfer).join(Branch).where(Transfer.id == record_id), principal)
    if lock:
        query = query.with_for_update(of=Transfer).execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Transfer not found.")
    return row


def eligible_query(principal, now):
    allocated = exists().where(TransferItem.collection_id == Collection.id, TransferItem.is_active)
    return scoped(
        select(Collection).select_from(Collection).join(Branch, Branch.id == Collection.branch_id),
        principal,
    ).where(Collection.locks_at <= now, ~allocated)


def require_active(branch):
    if branch.status != "Active":
        raise HTTPException(422, "Transfers can only be submitted while the branch is Active.")


def metadata(body):
    return {
        "transferred_on": body.transferred_on.isoformat(),
        "reference": body.reference,
        "notes": body.notes,
    }


def snapshot(row):
    return {"status": row.status, "amount": money(row.amount), **metadata(row)}


def reserve_collections(db, branch, collection_ids, transferred_on):
    rows = db.scalars(
        select(Collection)
        .where(Collection.id.in_(collection_ids), Collection.branch_id == branch.id)
        .order_by(Collection.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    if len(rows) != len(collection_ids):
        raise HTTPException(404, "One or more collections are unavailable for this branch.")
    now = utc_now()
    if any(row.locks_at > now for row in rows):
        raise HTTPException(
            409, "Only collections whose seven-day editing window has ended can be transferred."
        )
    if any(row.collected_on > transferred_on for row in rows):
        raise HTTPException(422, "Transfer date cannot precede the collection date.")
    if db.scalar(
        select(TransferItem.id)
        .where(TransferItem.collection_id.in_(collection_ids), TransferItem.is_active)
        .limit(1)
    ):
        raise HTTPException(
            409, "A selected collection is already reserved or confirmed in another transfer."
        )
    return rows


def create_transfer(db, principal, body):
    branch = lock_branch(db, principal)
    if branch.id != body.expected_branch_id:
        raise HTTPException(409, "Your branch assignment changed. Reload before submitting.")
    canonical = {
        **metadata(body),
        "collection_ids": sorted(str(i) for i in body.collection_ids),
        "branch_id": str(branch.id),
    }
    fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(
        select(Transfer).where(
            Transfer.created_by_id == principal.user.id, Transfer.request_id == body.request_id
        )
    )
    if existing:
        if existing.creation_fingerprint != fingerprint or existing.branch_id != branch.id:
            raise HTTPException(
                409, "This request reference has already been used with different details."
            )
        return existing
    require_active(branch)
    rows = reserve_collections(db, branch, body.collection_ids, body.transferred_on)
    now = utc_now()
    row = Transfer(
        branch_id=branch.id,
        created_by_id=principal.user.id,
        request_id=body.request_id,
        creation_fingerprint=fingerprint,
        amount=sum((item.amount for item in rows), Decimal("0.00")),
        transferred_on=body.transferred_on,
        reference=body.reference,
        notes=body.notes,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    for item in rows:
        db.add(
            TransferItem(
                transfer_id=row.id,
                collection_id=item.id,
                amount=item.amount,
                collection_version=item.version,
            )
        )
    db.add(
        TransferEvent(
            transfer_id=row.id,
            actor_id=principal.user.id,
            action="transfer_submitted",
            before=None,
            after={**snapshot(row), "collections": ", ".join(item.code for item in rows)},
            created_at=now,
        )
    )
    db.flush()
    return row


def transition(db, principal, record_id, action, body):
    candidate = transfer_record(db, principal, record_id)
    if principal.user.role == UserRole.BRANCH_LEAD:
        branch = lock_branch(db, principal, candidate.branch_id)
    else:
        branch = db.scalar(
            select(Branch)
            .where(Branch.id == candidate.branch_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    row = transfer_record(db, principal, record_id, lock=True)
    if row.version != body.expected_version:
        raise HTTPException(
            409, "This transfer changed. Reload the latest record before reviewing."
        )
    if action in {"confirm", "return"}:
        if (
            principal.user.role != UserRole.FINANCE_REVIEWER
            or row.created_by_id == principal.user.id
        ):
            raise HTTPException(403, "An independent Finance Reviewer must review this transfer.")
        if row.status != "Submitted":
            raise HTTPException(409, "Only Submitted transfers can be reviewed.")
    elif action in {"cancel", "resubmit"}:
        if principal.user.role != UserRole.BRANCH_LEAD:
            raise HTTPException(403, "Only the assigned Branch Lead can change this submission.")
        if row.status not in ({"Returned"} if action == "resubmit" else {"Submitted", "Returned"}):
            raise HTTPException(409, "This transfer cannot make that transition.")
    else:
        raise HTTPException(404, "Unknown transfer action.")
    items = db.scalars(
        select(TransferItem)
        .where(TransferItem.transfer_id == row.id)
        .order_by(TransferItem.collection_id)
    ).all()
    before = snapshot(row)
    if action == "resubmit":
        require_active(branch)
        reserve_collections(db, branch, [item.collection_id for item in items], body.transferred_on)
        row.transferred_on, row.reference, row.notes = (
            body.transferred_on,
            body.reference,
            body.notes,
        )
    row.status = {
        "confirm": "Confirmed",
        "return": "Returned",
        "cancel": "Cancelled",
        "resubmit": "Submitted",
    }[action]
    for item in items:
        item.is_active = row.status in {"Submitted", "Confirmed"}
    now = utc_now()
    if action in {"confirm", "return"}:
        row.reviewer_id = principal.user.id
    if action == "confirm":
        row.confirmed_at = now
    row.version += 1
    row.updated_at = now
    db.add(
        TransferEvent(
            transfer_id=row.id,
            actor_id=principal.user.id,
            action={
                "confirm": "transfer_confirmed",
                "return": "transfer_returned",
                "cancel": "transfer_cancelled",
                "resubmit": "transfer_resubmitted",
            }[action],
            reason=body.reason,
            before=before,
            after=snapshot(row),
            created_at=now,
        )
    )
    db.flush()
    return row
