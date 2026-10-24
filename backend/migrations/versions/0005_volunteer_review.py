"""Volunteer decisions and independent member records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    for name, datatype in [
        ("review_status", sa.String(10)),
        ("review_version", sa.Integer()),
        ("reviewed_at", sa.DateTime(timezone=True)),
        ("reviewer_id", sa.Uuid()),
        ("review_reason", sa.String(500)),
    ]:
        op.add_column("public_submissions", sa.Column(name, datatype, nullable=True))
    op.create_foreign_key(
        "fk_submission_reviewer",
        "public_submissions",
        "users",
        ["reviewer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(
        "UPDATE public_submissions SET review_status='Pending', review_version=1 "
        "WHERE kind='volunteer'"
    )
    op.create_index("ix_public_submissions_review_status", "public_submissions", ["review_status"])
    op.create_check_constraint(
        "ck_submission_review",
        "public_submissions",
        "(kind = 'contact' AND review_status IS NULL AND review_version IS NULL "
        "AND reviewed_at IS NULL AND reviewer_id IS NULL AND review_reason IS NULL) OR "
        "(kind = 'volunteer' AND review_status IS NOT NULL AND review_version IS NOT NULL "
        "AND review_version > 0 AND ((review_status = 'Pending' AND reviewed_at IS NULL "
        "AND reviewer_id IS NULL AND review_reason IS NULL) OR "
        "(review_status IN ('Accepted','Declined') AND reviewed_at IS NOT NULL "
        "AND review_reason IS NOT NULL)))",
    )
    sa.Sequence("member_number_seq").create(op.get_bind())
    op.create_table(
        "members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "number",
            sa.Integer(),
            server_default=sa.text("nextval('member_number_seq')"),
            nullable=False,
            unique=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("public_branches.id"), nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("public_submissions.id", ondelete="SET NULL"),
            unique=True,
        ),
        sa.Column("status", sa.String(8), nullable=False, server_default="Active"),
        sa.Column("team", sa.String(80), nullable=False, server_default=""),
        sa.Column(
            "organisational_role", sa.String(100), nullable=False, server_default="Volunteer"
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("email = lower(trim(email))", name="ck_member_email"),
        sa.CheckConstraint("status IN ('Active','Inactive')", name="ck_member_status"),
    )
    op.create_index("ix_members_branch_id", "members", ["branch_id"])
    op.create_index("ix_members_status", "members", ["status"])
    for table, field, parent in [
        ("application_events", "application_id", "public_submissions"),
        ("member_events", "member_id", "members"),
    ]:
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                field,
                sa.Uuid(),
                sa.ForeignKey(
                    f"{parent}.id", ondelete="CASCADE" if table == "application_events" else None
                ),
                nullable=False,
            ),
            sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("action", sa.String(30), nullable=False),
            sa.Column("reason", sa.String(500)),
            sa.Column("before", postgresql.JSONB()),
            sa.Column("after", postgresql.JSONB(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(f"ix_{table}_{field}", table, [field])


def downgrade():
    op.drop_table("member_events")
    op.drop_table("application_events")
    op.drop_table("members")
    sa.Sequence("member_number_seq").drop(op.get_bind())
    op.drop_constraint("ck_submission_review", "public_submissions", type_="check")
    op.drop_index("ix_public_submissions_review_status", "public_submissions")
    op.drop_constraint("fk_submission_reviewer", "public_submissions", type_="foreignkey")
    for name in ["review_reason", "reviewer_id", "reviewed_at", "review_version", "review_status"]:
        op.drop_column("public_submissions", name)
