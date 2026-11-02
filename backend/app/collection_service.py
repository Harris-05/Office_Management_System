import hashlib
import json
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.collection_contracts import money
from app.collection_models import Collection, CollectionEvent
from app.models import UserRole
from app.public_models import Branch
from app.sessions import utc_now


def scoped(query, principal):
    return (
        query.where(Branch.lead_id == principal.user.id)
        if principal.user.role == UserRole.BRANCH_LEAD
        else query
    )


def collection_record(db, principal, record_id, lock=False):
    query = scoped(select(Collection).join(Branch).where(Collection.id == record_id), principal)
    if lock:
        query = query.with_for_update(of=Collection).execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Collection not found.")
    return row


def require_active(branch):
    if branch.status != "Active":
        raise HTTPException(
            422, "Collections can only be created or edited while the branch is Active."
        )


def lock_branch(db, principal, branch_id=None):
    query = select(Branch).where(Branch.lead_id == principal.user.id)
    if branch_id:
        query = query.where(Branch.id == branch_id)
    branch = db.scalar(query.with_for_update().execution_options(populate_existing=True))
    if branch is None:
        raise HTTPException(
            404 if branch_id else 403, "No permitted branch assignment. Ask your Super Admin."
        )
    return branch


def values(row):
    return {
        "amount": money(row.amount),
        "collected_on": row.collected_on.isoformat(),
        "collector_name": row.collector_name,
        "notes": row.notes,
    }


def canonical(body):
    return {
        "amount": money(body.amount),
        "collected_on": body.collected_on.isoformat(),
        "collector_name": body.collector_name,
        "notes": body.notes,
    }


def create_collection(db, principal, body):
    branch = lock_branch(db, principal)
    if branch.id != body.expected_branch_id:
        raise HTTPException(
            409, "Your branch assignment changed. Reload branch details before recording."
        )
    payload = canonical(body)
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(
        select(Collection).where(
            Collection.created_by_id == principal.user.id, Collection.request_id == body.request_id
        )
    )

    def retry(row):
        if row.branch_id != branch.id or row.creation_fingerprint != fingerprint:
            raise HTTPException(
                409, "This request reference has already been used. Reload to start a new entry."
            )
        return row

    if existing:
        return retry(existing)
    require_active(branch)
    now = utc_now()
    record_id = uuid.uuid4()
    created = db.scalar(
        insert(Collection)
        .values(
            id=record_id,
            branch_id=branch.id,
            created_by_id=principal.user.id,
            request_id=body.request_id,
            creation_fingerprint=fingerprint,
            amount=body.amount,
            collected_on=body.collected_on,
            collector_name=body.collector_name,
            notes=body.notes,
            created_at=now,
            updated_at=now,
            locks_at=now + timedelta(days=7),
        )
        .on_conflict_do_nothing(constraint="uq_collection_request")
        .returning(Collection.id)
    )
    if not created:
        return retry(
            db.scalar(
                select(Collection).where(
                    Collection.created_by_id == principal.user.id,
                    Collection.request_id == body.request_id,
                )
            )
        )
    row = db.get(Collection, record_id)
    db.add(
        CollectionEvent(
            collection_id=row.id,
            actor_id=principal.user.id,
            action="collection_created",
            before=None,
            after={**values(row), "code": row.code},
            created_at=now,
        )
    )
    db.flush()
    return row


def update_collection(db, principal, record_id, body):
    candidate = collection_record(db, principal, record_id)
    branch = lock_branch(db, principal, candidate.branch_id)
    row = collection_record(db, principal, record_id, lock=True)
    now = utc_now()  # After lock waits: the clock must still permit the write.
    if row.version != body.expected_version:
        raise HTTPException(
            409, "This collection changed. Reload the latest version before trying again."
        )
    if now >= row.locks_at:
        raise HTTPException(
            409, "This collection is locked: seven days have passed since creation."
        )
    require_active(branch)
    before = values(row)
    after = canonical(body)
    if before != after:
        row.amount = body.amount
        row.collected_on = body.collected_on
        row.collector_name = body.collector_name
        row.notes = body.notes
        row.version += 1
        row.updated_at = now
        db.add(
            CollectionEvent(
                collection_id=row.id,
                actor_id=principal.user.id,
                action="collection_updated",
                reason=body.reason,
                before=before,
                after=after,
                created_at=now,
            )
        )
    db.flush()
    return row
