"""Content Editor/Super Admin commands; public reads use published copies only."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.content_contracts import (
    Actor,
    BranchOption,
    ContentCommand,
    ContentKind,
    ContentPage,
    ContentPayload,
    ContentView,
    CreateContent,
    Preview,
    RevisionPage,
    RevisionView,
    SaveDraft,
)
from app.content_models import ContentDocument, ContentRevision
from app.dependencies import Principal, require_roles
from app.login import DB
from app.models import User, UserRole
from app.public_models import Branch, Program, PublicEvent
from app.sessions import utc_now

router = APIRouter(prefix="/api/content", tags=["content manager"])
Editor = Annotated[Principal, Depends(require_roles(UserRole.CONTENT_EDITOR, UserRole.SUPER_ADMIN))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
payload_adapter = TypeAdapter(ContentPayload)


def document(db, document_id, *, lock=False):
    query = select(ContentDocument).where(ContentDocument.id == document_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if not row:
        raise HTTPException(404, "Content not found.")
    return row


def source(db, row):
    if row.kind == "program":
        return db.get(Program, row.program_id)
    if row.kind == "event":
        return db.get(PublicEvent, row.event_id)
    return None


def view(db, row):
    target = source(db, row)
    return ContentView(
        id=row.id,
        kind=row.kind,
        version=row.version,
        draft=row.draft,
        published=row.published,
        is_published=target.is_published if target else row.is_published,
        has_unpublished_changes=row.draft != row.published,
        is_demo=bool(target and target.is_demo),
        updated_at=row.updated_at,
    )


def version(row, expected):
    if row.version != expected:
        raise HTTPException(409, "Content changed since you opened it. Reload before trying again.")


def event_branch(db, content, *, publish=False, lock=False):
    if content.kind != "event":
        return
    query = select(Branch).where(Branch.id == content.branch_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    branch = db.scalar(query)
    if branch is None:
        raise HTTPException(422, "Choose an existing branch.")
    if publish and (branch.status != "Active" or not branch.is_published):
        raise HTTPException(422, "Events can only be published for an Active, published branch.")


def record_revision(db, row, principal, action, reason):
    row.updated_at = utc_now()
    db.add(
        ContentRevision(
            document_id=row.id,
            version=row.version,
            actor_id=principal.user.id,
            action=action,
            reason=reason,
            snapshot={
                "draft": row.draft,
                "published": row.published,
                "is_published": row.is_published,
            },
        )
    )


def finish(db, row):
    try:
        db.flush()
        result = view(db, row)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This slug or page is already in use. Choose a unique value and reload."
        ) from None
    return result


@router.get("", response_model=ContentPage)
def list_content(
    db: DB,
    principal: Editor,
    kind: ContentKind | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = select(ContentDocument)
    if kind:
        query = query.where(ContentDocument.kind == kind)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(ContentDocument.updated_at.desc(), ContentDocument.id)
        .offset(offset)
        .limit(limit)
    ).all()
    result = ContentPage(
        items=[view(db, row) for row in rows], total=total, offset=offset, limit=limit
    )
    db.commit()
    return result


@router.get("/branches", response_model=list[BranchOption])
def branches(db: DB, principal: Editor):
    rows = db.scalars(
        select(Branch).where(Branch.status == "Active", Branch.is_published).order_by(Branch.number)
    ).all()
    result = [
        BranchOption(id=row.id, name=row.name, name_ur=row.name_ur, code=row.code) for row in rows
    ]
    db.commit()
    return result


@router.post("", response_model=ContentView, status_code=201)
def create_content(data: CreateContent, db: DB, principal: Editor):
    content = data.content
    event_branch(db, content)
    values = content.model_dump(exclude={"kind", "page_key"})
    row = ContentDocument(
        id=uuid.uuid4(),
        kind=content.kind,
        draft=content.model_dump(mode="json"),
        published=None,
        is_published=False,
        version=1,
    )
    try:
        if content.kind in {"program", "event"}:
            target = (Program if content.kind == "program" else PublicEvent)(
                id=uuid.uuid4(), **values, is_published=False, is_demo=False
            )
            db.add(target)
            db.flush()
            if content.kind == "program":
                row.program_id = target.id
            else:
                row.event_id = target.id
        else:
            row.page_key = content.page_key
        db.add(row)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "This slug or page is already in use. Choose a unique value."
        ) from None
    record_revision(db, row, principal, "created", data.reason)
    return finish(db, row)


@router.get("/{document_id}", response_model=ContentView)
def get_content(document_id: uuid.UUID, db: DB, principal: Editor):
    result = view(db, document(db, document_id))
    db.commit()
    return result


@router.get("/{document_id}/preview", response_model=Preview)
def preview(document_id: uuid.UUID, db: DB, principal: Editor):
    row = document(db, document_id)
    result = Preview(content=row.draft, version=row.version)
    db.commit()
    return result


@router.post("/{document_id}/draft", response_model=ContentView)
def save_draft(document_id: uuid.UUID, data: SaveDraft, db: DB, principal: Editor):
    row = document(db, document_id, lock=True)
    version(row, data.expected_version)
    content = data.content
    if row.kind != content.kind or (row.kind == "page" and row.page_key != content.page_key):
        raise HTTPException(422, "Content kind and page cannot be changed.")
    event_branch(db, content)
    row.draft = content.model_dump(mode="json")
    row.version += 1
    record_revision(db, row, principal, "draft_saved", data.reason)
    return finish(db, row)


@router.post("/{document_id}/publish", response_model=ContentView)
def publish(document_id: uuid.UUID, data: ContentCommand, db: DB, principal: Editor):
    # Branch-first locking agrees with branch lifecycle commands. Recheck the document
    # version after acquiring its lock, so a racing branch change/draft save cannot publish.
    initial = document(db, document_id)
    content = payload_adapter.validate_python(initial.draft)
    event_branch(db, content, publish=True, lock=True)
    row = document(db, document_id, lock=True)
    version(row, data.expected_version)
    content = payload_adapter.validate_python(row.draft)
    target = source(db, row)
    if target:
        for key, value in content.model_dump(exclude={"kind"}).items():
            setattr(target, key, value)
        target.is_published = True
    row.published = content.model_dump(mode="json")
    row.is_published = True
    row.version += 1
    record_revision(db, row, principal, "published", data.reason)
    return finish(db, row)


@router.post("/{document_id}/unpublish", response_model=ContentView)
def unpublish(document_id: uuid.UUID, data: ContentCommand, db: DB, principal: Editor):
    row = document(db, document_id, lock=True)
    version(row, data.expected_version)
    target = source(db, row)
    if target:
        target.is_published = False
    row.is_published = False
    row.version += 1
    record_revision(db, row, principal, "unpublished", data.reason)
    return finish(db, row)


@router.get("/{document_id}/history", response_model=RevisionPage)
def history(
    document_id: uuid.UUID, db: DB, principal: Editor, offset: Offset = 0, limit: Limit = 25
):
    document(db, document_id)
    query = select(ContentRevision, User).outerjoin(User, User.id == ContentRevision.actor_id)
    query = query.where(ContentRevision.document_id == document_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = [
        RevisionView(
            id=row.id,
            version=row.version,
            action=row.action,
            reason=row.reason,
            actor=Actor(id=actor.id, name=actor.name) if actor else None,
            created_at=row.created_at,
            snapshot=row.snapshot,
        )
        for row, actor in db.execute(
            query.order_by(ContentRevision.version.desc()).offset(offset).limit(limit)
        )
    ]
    result = RevisionPage(items=items, total=total, offset=offset, limit=limit)
    db.commit()
    return result
