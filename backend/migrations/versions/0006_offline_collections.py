"""offline_collections

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    sa.Sequence("collection_number_seq").create(op.get_bind())
    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "number",
            sa.Integer(),
            server_default=sa.text("nextval('collection_number_seq')"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("creation_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="PKR", nullable=False),
        sa.Column("collected_on", sa.Date(), nullable=False),
        sa.Column("collector_name", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.String(length=1000), server_default="", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
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
        sa.Column(
            "locks_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now() + interval '168 hours'"),
            nullable=False,
        ),
        sa.CheckConstraint("currency = 'PKR'", name="ck_collection_currency"),
        sa.CheckConstraint(
            "locks_at - created_at = interval '168 hours'", name="ck_collection_deadline"
        ),
        sa.CheckConstraint("amount > 0", name="ck_collection_amount"),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["public_branches.id"],
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("created_by_id", "request_id", name="uq_collection_request"),
        sa.UniqueConstraint("number"),
    )
    op.create_index(op.f("ix_collections_branch_id"), "collections", ["branch_id"], unique=False)
    op.create_index(
        op.f("ix_collections_collected_on"), "collections", ["collected_on"], unique=False
    )
    op.create_index(op.f("ix_collections_locks_at"), "collections", ["locks_at"], unique=False)
    op.create_table(
        "collection_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
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
            ["collection_id"],
            ["collections.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_collection_events_collection_id"),
        "collection_events",
        ["collection_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_collection_events_collection_id"), table_name="collection_events")
    op.drop_table("collection_events")
    op.drop_index(op.f("ix_collections_locks_at"), table_name="collections")
    op.drop_index(op.f("ix_collections_collected_on"), table_name="collections")
    op.drop_index(op.f("ix_collections_branch_id"), table_name="collections")
    op.drop_table("collections")
    sa.Sequence("collection_number_seq").drop(op.get_bind())
