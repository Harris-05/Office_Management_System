"""Weekly reporting and immutable submission evidence."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Report(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (
        UniqueConstraint("branch_id", "week_start", name="uq_report_branch_week"),
        CheckConstraint(
            "status IN ('Draft','Submitted','Returned','Approved')", name="ck_report_status"
        ),
        CheckConstraint("extract(isodow from week_start) = 1", name="ck_report_monday"),
        CheckConstraint("version > 0 AND revision_number >= 0", name="ck_report_versions"),
        CheckConstraint(
            "(status = 'Approved') = (approved_at IS NOT NULL)", name="ck_report_approval"
        ),
        CheckConstraint(
            "status NOT IN ('Submitted','Approved') OR snapshot IS NOT NULL",
            name="ck_report_snapshot",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("public_branches.id"), index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(
        String(12), default="Draft", server_default="Draft", index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    revision_number: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    narrative: Mapped[str] = mapped_column(Text, default="", server_default="")
    snapshot: Mapped[dict | None] = mapped_column(JSONB)
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportRevision(Base):
    __tablename__ = "report_revisions"
    __table_args__ = (UniqueConstraint("report_id", "number", name="uq_report_revision"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("weekly_reports.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    narrative: Mapped[str] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReportEvent(Base):
    __tablename__ = "report_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("weekly_reports.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(500))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
