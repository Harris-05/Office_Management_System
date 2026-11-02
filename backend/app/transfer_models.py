"""Whole-collection transfers and immutable workflow evidence."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
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


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transfer_amount"),
        CheckConstraint(
            "status IN ('Submitted','Returned','Confirmed','Cancelled')", name="ck_transfer_status"
        ),
        CheckConstraint(
            "(status = 'Confirmed') = (confirmed_at IS NOT NULL)", name="ck_transfer_confirmation"
        ),
        UniqueConstraint("created_by_id", "request_id", name="uq_transfer_request"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    number_sequence = Sequence("transfer_number_seq", metadata=Base.metadata)
    number: Mapped[int] = mapped_column(
        Integer, number_sequence, server_default=number_sequence.next_value(), unique=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("public_branches.id"), index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    request_id: Mapped[uuid.UUID] = mapped_column()
    creation_fingerprint: Mapped[str] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    transferred_on: Mapped[date] = mapped_column(Date)
    reference: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    status: Mapped[str] = mapped_column(
        String(20), default="Submitted", server_default="Submitted", index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def code(self) -> str:
        return f"TRF-{self.number:06d}"


class TransferItem(Base):
    __tablename__ = "transfer_items"
    __table_args__ = (
        UniqueConstraint("transfer_id", "collection_id", name="uq_transfer_item"),
        Index(
            "uq_transfer_active_collection",
            "collection_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        CheckConstraint("amount > 0", name="ck_transfer_item_amount"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transfer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transfers.id"), index=True)
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    collection_version: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class TransferEvent(Base):
    __tablename__ = "transfer_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transfer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transfers.id"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(500))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
