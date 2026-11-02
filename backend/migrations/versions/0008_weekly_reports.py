"""Weekly reports, immutable submissions, and actor/version audit."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "weekly_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("public_branches.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(12), server_default="Draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("revision_number", sa.Integer(), server_default="0", nullable=False),
        sa.Column("narrative", sa.Text(), server_default="", nullable=False),
        sa.Column("snapshot", postgresql.JSONB()),
        sa.Column("submitted_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("branch_id", "week_start", name="uq_report_branch_week"),
        sa.CheckConstraint(
            "status IN ('Draft','Submitted','Returned','Approved')", name="ck_report_status"
        ),
        sa.CheckConstraint("extract(isodow from week_start) = 1", name="ck_report_monday"),
        sa.CheckConstraint("version > 0 AND revision_number >= 0", name="ck_report_versions"),
        sa.CheckConstraint(
            "(status = 'Approved') = (approved_at IS NOT NULL)", name="ck_report_approval"
        ),
        sa.CheckConstraint(
            "status NOT IN ('Submitted','Approved') OR snapshot IS NOT NULL",
            name="ck_report_snapshot",
        ),
    )
    for column in ["branch_id", "week_start", "status"]:
        op.create_index(f"ix_weekly_reports_{column}", "weekly_reports", [column])
    op.create_table(
        "report_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), sa.ForeignKey("weekly_reports.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("report_id", "number", name="uq_report_revision"),
    )
    op.create_index("ix_report_revisions_report_id", "report_revisions", ["report_id"])
    op.create_table(
        "report_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), sa.ForeignKey("weekly_reports.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("before", postgresql.JSONB()),
        sa.Column("after", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_report_events_report_id", "report_events", ["report_id"])


def downgrade():
    op.drop_table("report_events")
    op.drop_table("report_revisions")
    op.drop_table("weekly_reports")
