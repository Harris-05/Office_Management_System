"""transfers_to_head_office

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sa.Sequence("transfer_number_seq").create(op.get_bind())
    op.create_table(
        "transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "number",
            sa.Integer(),
            server_default=sa.text("nextval('transfer_number_seq')"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("creation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("transferred_on", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="Submitted", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'Confirmed') = (confirmed_at IS NOT NULL)", name="ck_transfer_confirmation"
        ),
        sa.CheckConstraint(
            "status IN ('Submitted','Returned','Confirmed','Cancelled')", name="ck_transfer_status"
        ),
        sa.CheckConstraint("amount > 0", name="ck_transfer_amount"),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public_branches.id"],
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("created_by_id", "request_id", name="uq_transfer_request"),
        sa.UniqueConstraint("number"),
    )
    op.create_index(op.f("ix_transfers_branch_id"), "transfers", ["branch_id"], unique=False)
    op.create_index(op.f("ix_transfers_status"), "transfers", ["status"], unique=False)
    op.create_table(
        "transfer_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transfer_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["transfer_id"],
            ["transfers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transfer_events_transfer_id"), "transfer_events", ["transfer_id"], unique=False
    )
    op.create_table(
        "transfer_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transfer_id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("collection_version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_transfer_item_amount"),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["collections.id"],
        ),
        sa.ForeignKeyConstraint(
            ["transfer_id"],
            ["transfers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transfer_id", "collection_id", name="uq_transfer_item"),
    )
    op.create_index(
        op.f("ix_transfer_items_transfer_id"), "transfer_items", ["transfer_id"], unique=False
    )
    op.create_index(
        "uq_transfer_active_collection",
        "transfer_items",
        ["collection_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_transfer_active_collection",
        table_name="transfer_items",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_index(op.f("ix_transfer_items_transfer_id"), table_name="transfer_items")
    op.drop_table("transfer_items")
    op.drop_index(op.f("ix_transfer_events_transfer_id"), table_name="transfer_events")
    op.drop_table("transfer_events")
    op.drop_index(op.f("ix_transfers_status"), table_name="transfers")
    op.drop_index(op.f("ix_transfers_branch_id"), table_name="transfers")
    op.drop_table("transfers")
    sa.Sequence("transfer_number_seq").drop(op.get_bind())
