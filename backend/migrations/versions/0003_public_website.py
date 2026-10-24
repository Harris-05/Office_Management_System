"""Published public catalogue and private submissions."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def common():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("description_ur", sa.Text(), nullable=False),
    ]


def translated(name, length):
    return [
        sa.Column(name, sa.String(length), nullable=False),
        sa.Column(name + "_ur", sa.String(length), nullable=False),
    ]


def upgrade():
    op.create_table(
        "public_branches",
        *common(),
        *translated("name", 160),
        *translated("city", 100),
        *translated("address", 300),
        *translated("hours", 160),
    )
    op.create_table(
        "public_programs", *common(), *translated("title", 160), *translated("audience", 200)
    )
    op.create_table(
        "public_events",
        *common(),
        *translated("title", 160),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("public_branches.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_event_date_order"),
    )
    for column in ("branch_id", "starts_at"):
        op.create_index(f"ix_public_events_{column}", "public_events", [column])
    op.create_table(
        "public_submissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("public_branches.id")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('contact', 'volunteer')", name="ck_submission_kind"),
    )
    for column in ("email", "expires_at"):
        op.create_index(f"ix_public_submissions_{column}", "public_submissions", [column])


def downgrade():
    for table in ("public_submissions", "public_events", "public_programs", "public_branches"):
        op.drop_table(table)
