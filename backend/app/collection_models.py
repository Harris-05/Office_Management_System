"""Exact offline receipts with immutable creation-based editing deadlines."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Sequence,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Collection(Base):
    __tablename__ = "collections"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_collection_amount"),
        CheckConstraint("currency = 'PKR'", name="ck_collection_currency"),
        CheckConstraint(
            "locks_at - created_at = interval '168 hours'", name="ck_collection_deadline"
        ),
        UniqueConstraint("created_by_id", "request_id", name="uq_collection_request"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    number_sequence = Sequence("collection_number_seq", metadata=Base.metadata)
    number: Mapped[int] = mapped_column(
        Integer, number_sequence, server_default=number_sequence.next_value(), unique=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("public_branches.id"), index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    request_id: Mapped[uuid.UUID] = mapped_column()
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PKR", server_default="PKR")
    collected_on: Mapped[date] = mapped_column(Date, index=True)
    collector_name: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locks_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now() + interval '168 hours'"), index=True
    )

    @property
    def code(self) -> str:
        return f"COL-{self.number:06d}"


class CollectionEvent(Base):
    __tablename__ = "collection_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(500))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
