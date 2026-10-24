"""Published catalogue and private visitor correspondence."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Sequence,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PublishedRecord:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    description: Mapped[str] = mapped_column(Text)
    description_ur: Mapped[str] = mapped_column(Text)


class Branch(PublishedRecord, Base):
    __tablename__ = "public_branches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Forming','Active','Paused','Closed')", name="ck_branch_status"
        ),
        CheckConstraint("NOT is_published OR status = 'Active'", name="ck_branch_publication"),
        CheckConstraint("status <> 'Closed' OR lead_id IS NULL", name="ck_branch_closed_lead"),
    )
    number_sequence = Sequence("branch_number_seq", metadata=Base.metadata)
    number: Mapped[int] = mapped_column(
        Integer, number_sequence, server_default=number_sequence.next_value(), unique=True
    )
    status: Mapped[str] = mapped_column(
        String(10), default="Forming", server_default="Forming", index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def code(self) -> str:
        return f"BR-{self.number:06d}"

    name: Mapped[str] = mapped_column(String(160))
    name_ur: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(100))
    city_ur: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    address_ur: Mapped[str] = mapped_column(String(300))
    hours: Mapped[str] = mapped_column(String(160))
    hours_ur: Mapped[str] = mapped_column(String(160))


class BranchAudit(Base):
    __tablename__ = "branch_audits"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("public_branches.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(500))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Program(PublishedRecord, Base):
    __tablename__ = "public_programs"
    title: Mapped[str] = mapped_column(String(160))
    title_ur: Mapped[str] = mapped_column(String(160))
    audience: Mapped[str] = mapped_column(String(200))
    audience_ur: Mapped[str] = mapped_column(String(200))


class PublicEvent(PublishedRecord, Base):
    __tablename__ = "public_events"
    __table_args__ = (CheckConstraint("ends_at > starts_at", name="ck_event_date_order"),)
    title: Mapped[str] = mapped_column(String(160))
    title_ur: Mapped[str] = mapped_column(String(160))
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("public_branches.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PublicSubmission(Base):
    __tablename__ = "public_submissions"
    __table_args__ = (
        CheckConstraint("kind IN ('contact', 'volunteer')", name="ck_submission_kind"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    # Deliberately not a FK: receipts survive the short anonymous session lifetime.
    session_id: Mapped[uuid.UUID] = mapped_column()
    fingerprint: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), index=True)
    subject: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("public_branches.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
