"""Private drafts and immutable command snapshots for the public catalogue."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ContentDocument(Base):
    __tablename__ = "content_documents"
    __table_args__ = (
        CheckConstraint("kind IN ('program','event','page')", name="ck_content_kind"),
        CheckConstraint("version > 0", name="ck_content_version"),
        CheckConstraint(
            "(kind = 'program' AND program_id IS NOT NULL "
            "AND event_id IS NULL AND page_key IS NULL) OR "
            "(kind = 'event' AND event_id IS NOT NULL "
            "AND program_id IS NULL AND page_key IS NULL) OR "
            "(kind = 'page' AND program_id IS NULL AND event_id IS NULL AND page_key IS NOT NULL "
            "AND page_key IN ('home','about','contact'))",
            name="ck_content_target",
        ),
        CheckConstraint("NOT is_published OR published IS NOT NULL", name="ck_content_published"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(10), index=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("public_programs.id"), unique=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("public_events.id"), unique=True)
    page_key: Mapped[str | None] = mapped_column(String(10), unique=True)
    draft: Mapped[dict] = mapped_column(JSONB)
    published: Mapped[dict | None] = mapped_column(JSONB)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentRevision(Base):
    __tablename__ = "content_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_content_revision_version"),
        CheckConstraint("version > 0", name="ck_content_revision_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_documents.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(500))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
