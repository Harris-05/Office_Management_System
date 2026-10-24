"""Private member records and retention-scoped workflow history."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Sequence, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        CheckConstraint("email = lower(trim(email))", name="ck_member_email"),
        CheckConstraint("status IN ('Active','Inactive')", name="ck_member_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    number_sequence = Sequence("member_number_seq", metadata=Base.metadata)
    number: Mapped[int] = mapped_column(
        Integer, number_sequence, server_default=number_sequence.next_value(), unique=True
    )
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("public_branches.id"), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("public_submissions.id", ondelete="SET NULL"), unique=True
    )
    status: Mapped[str] = mapped_column(
        String(8), default="Active", server_default="Active", index=True
    )
    team: Mapped[str] = mapped_column(String(80), default="", server_default="")
    organisational_role: Mapped[str] = mapped_column(
        String(100), default="Volunteer", server_default="Volunteer"
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def code(self) -> str:
        return f"MEM-{self.number:06d}"


class EventFields:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(500))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApplicationEvent(EventFields, Base):
    __tablename__ = "application_events"
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public_submissions.id", ondelete="CASCADE"), index=True
    )


class MemberEvent(EventFields, Base):
    __tablename__ = "member_events"
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("members.id"), index=True)
