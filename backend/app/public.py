import hashlib
import json
import unicodedata
import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import Principal, require_api_access, require_roles
from app.models import UserRole
from app.public_models import Branch, Program, PublicEvent, PublicSubmission
from app.rate_limits import consume
from app.sessions import utc_now

router = APIRouter(tags=["public website"])
DB = Annotated[Session, Depends(get_db)]
Auth = Annotated[Principal, Depends(require_api_access)]


class Published(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    is_demo: bool
    description: str
    description_ur: str


class BranchView(Published):
    name: str
    name_ur: str
    city: str
    city_ur: str
    address: str
    address_ur: str
    hours: str
    hours_ur: str


class ProgramView(Published):
    title: str
    title_ur: str
    audience: str
    audience_ur: str


class EventView(Published):
    title: str
    title_ur: str
    branch_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime


class Catalogue(BaseModel):
    branches: list[BranchView]
    programs: list[ProgramView]
    events: list[EventView]


@router.get("/api/public/catalog", response_model=Catalogue)
def catalogue(db: DB):
    return {
        "branches": db.scalars(
            select(Branch)
            .where(Branch.is_published, Branch.status == "Active")
            .order_by(Branch.city, Branch.id)
            .limit(100)
        ).all(),
        "programs": db.scalars(
            select(Program)
            .where(Program.is_published)
            .order_by(Program.title, Program.id)
            .limit(100)
        ).all(),
        "events": db.scalars(
            select(PublicEvent)
            .join(Branch)
            .where(PublicEvent.is_published, Branch.is_published, Branch.status == "Active")
            .order_by(PublicEvent.starts_at.desc(), PublicEvent.id)
            .limit(200)
        ).all(),
    }


class SubmissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=10, max_length=4000)
    consent: Literal[True]
    branch_id: uuid.UUID | None = None

    @field_validator("name", "email", "subject", "message")
    @classmethod
    def safe_text(cls, value: str, info: ValidationInfo) -> str:
        for char in value:
            if info.field_name == "message" and char in "\n\r\t":
                continue
            if unicodedata.category(char) in {"Cc", "Cs"}:
                raise ValueError("Control characters are not allowed.")
        return value


class Receipt(BaseModel):
    id: uuid.UUID


def save_submission(
    body: SubmissionInput, kind: str, request: Request, db: Session, principal: Principal
) -> Receipt:
    values = body.model_dump(exclude={"request_id", "consent"}, mode="json")
    values["email"] = body.email.lower()
    fingerprint = hashlib.sha256(
        json.dumps({**values, "kind": kind}, sort_keys=True).encode()
    ).hexdigest()

    def receipt(row):
        if row.session_id != principal.session.id or row.fingerprint != fingerprint:
            raise HTTPException(
                409, "This request reference has already been used. Reload to start again."
            )
        return Receipt(id=row.id)

    existing = db.scalar(
        select(PublicSubmission).where(PublicSubmission.request_id == body.request_id)
    )
    if existing:
        return receipt(existing)
    if kind == "volunteer" and body.branch_id is None:
        raise HTTPException(422, "Choose a published branch.")
    if body.branch_id is not None and not db.scalar(
        select(Branch.id).where(
            Branch.id == body.branch_id, Branch.is_published, Branch.status == "Active"
        )
    ):
        raise HTTPException(422, "Choose a published branch.")
    ip = request.client.host if request.client else "unknown"
    allowed, retry = consume(f"public-submission:{ip}", 5, 600)
    if not allowed:
        raise HTTPException(
            429, "Too many submissions. Please try later.", headers={"Retry-After": str(retry)}
        )
    values["branch_id"] = body.branch_id
    db.execute(
        insert(PublicSubmission)
        .values(
            **values,
            id=uuid.uuid4(),
            request_id=body.request_id,
            session_id=principal.session.id,
            fingerprint=fingerprint,
            kind=kind,
            expires_at=utc_now() + timedelta(days=90),
        )
        .on_conflict_do_nothing(index_elements=[PublicSubmission.request_id])
    )
    row = db.scalar(select(PublicSubmission).where(PublicSubmission.request_id == body.request_id))
    result = receipt(row)
    db.commit()
    return result


@router.post("/api/public/messages", status_code=201, response_model=Receipt)
def contact(body: SubmissionInput, request: Request, db: DB, principal: Auth):
    return save_submission(body, "contact", request, db, principal)


@router.post("/api/public/volunteers", status_code=201, response_model=Receipt)
def volunteer(body: SubmissionInput, request: Request, db: DB, principal: Auth):
    return save_submission(body, "volunteer", request, db, principal)


class InboxItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    name: str
    email: str
    subject: str
    message: str
    branch_id: uuid.UUID | None
    created_at: datetime


@router.get("/api/staff/public-submissions", response_model=list[InboxItem])
def inbox(
    db: DB,
    principal: Annotated[Principal, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_LEAD))],
    offset: Annotated[int, Query(ge=0)] = 0,
):
    query = select(PublicSubmission).where(PublicSubmission.expires_at > utc_now())
    if principal.user.role == UserRole.HR_LEAD:
        query = query.where(PublicSubmission.kind == "volunteer")
    rows = db.scalars(
        query.order_by(PublicSubmission.created_at.desc(), PublicSubmission.id)
        .offset(offset)
        .limit(50)
    ).all()
    db.commit()  # Persist the idle-session renewal performed by the access guard.
    return rows
