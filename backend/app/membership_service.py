"""Transactional mutations; caller commits the response and session renewal together."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.membership_models import ApplicationEvent, Member, MemberEvent
from app.public_models import Branch, PublicSubmission
from app.sessions import utc_now


def application_record(db, record_id, lock=False):
    query = select(PublicSubmission).where(
        PublicSubmission.id == record_id,
        PublicSubmission.kind == "volunteer",
        PublicSubmission.expires_at > utc_now(),
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None or row.expires_at <= utc_now():
        raise HTTPException(404, "Application not found or expired.")
    return row


def member_record(db, record_id, lock=False):
    query = select(Member).where(Member.id == record_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Member not found.")
    return row


def branch_lock(db, branch_id):
    return db.scalar(
        select(Branch)
        .where(Branch.id == branch_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def require_active(branch):
    if branch is None or branch.status != "Active":
        raise HTTPException(
            422, "The branch must be Active. Ask an administrator to resolve its status."
        )


def version_check(actual, expected):
    if actual != expected:
        raise HTTPException(
            409, "This record changed since you opened it. Reload the latest version."
        )


def member_values(row):
    return {"status": row.status, "team": row.team, "organisational_role": row.organisational_role}


def duplicate_message(existing):
    if existing:
        return (
            f"A member with this email already exists: {existing.code}. "
            "Search Members before reviewing this duplicate."
        )
    return "A member already exists for this email or application. Search Members and reload."


def review_application(db, principal, record_id, body):
    candidate = application_record(db, record_id)
    branch = branch_lock(db, candidate.branch_id)
    row = application_record(db, record_id, lock=True)
    version_check(row.review_version, body.expected_version)
    if row.review_status != "Pending":
        raise HTTPException(409, "This application has already been reviewed.")
    now = utc_now()
    if body.decision == "Accepted":
        require_active(branch)
        email = row.email.strip().lower()
        existing = db.scalar(select(Member).where(Member.email == email))
        if existing:
            raise HTTPException(409, duplicate_message(existing))
        member = Member(name=row.name, email=email, branch_id=row.branch_id, source_id=row.id)
        db.add(member)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = db.scalar(select(Member).where(Member.email == email))
            raise HTTPException(409, duplicate_message(existing)) from None
        db.add(
            MemberEvent(
                member_id=member.id,
                actor_id=principal.user.id,
                action="member_created",
                before=None,
                after={**member_values(member), "code": member.code, "source_id": str(row.id)},
                created_at=now,
            )
        )
    row.review_status = body.decision
    row.review_version += 1
    row.reviewer_id = principal.user.id
    row.reviewed_at = now
    row.review_reason = body.reason
    db.add(
        ApplicationEvent(
            application_id=row.id,
            actor_id=principal.user.id,
            action=body.decision.lower(),
            reason=body.reason,
            before={"status": "Pending"},
            after={"status": body.decision},
            created_at=now,
        )
    )
    db.flush()
    return row


def update_member(db, principal, record_id, body):
    candidate = member_record(db, record_id)
    branch = branch_lock(db, candidate.branch_id)
    row = member_record(db, record_id, lock=True)
    version_check(row.version, body.expected_version)
    before = member_values(row)
    if row.status != "Active" and body.status == "Active":
        require_active(branch)
    after = body.model_dump(include={"status", "team", "organisational_role"})
    if before != after:
        for key, value in after.items():
            setattr(row, key, value)
        row.version += 1
        row.updated_at = utc_now()
        db.add(
            MemberEvent(
                member_id=row.id,
                actor_id=principal.user.id,
                action="member_updated",
                reason=body.reason,
                before=before,
                after=after,
                created_at=row.updated_at,
            )
        )
    db.flush()
    return row
