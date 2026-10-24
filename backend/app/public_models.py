"""Published catalogue and private visitor correspondence."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, false, func
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
    name: Mapped[str] = mapped_column(String(160))
    name_ur: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(100))
    city_ur: Mapped[str] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    address_ur: Mapped[str] = mapped_column(String(300))
    hours: Mapped[str] = mapped_column(String(160))
    hours_ur: Mapped[str] = mapped_column(String(160))


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
