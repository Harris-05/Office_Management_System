"""Extend the shared public branch records into the operational register."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    sa.Sequence("branch_number_seq").create(op.get_bind())
    op.add_column("public_branches", sa.Column("number", sa.Integer(), nullable=True))
    op.execute("""UPDATE public_branches b SET number = ordered.n FROM
        (SELECT id, row_number() OVER (ORDER BY slug, id) AS n FROM public_branches) ordered
        WHERE b.id = ordered.id""")
    op.execute("""SELECT setval('branch_number_seq',
        GREATEST(COALESCE(MAX(number), 0), 1), COUNT(*) > 0) FROM public_branches""")
    op.alter_column(
        "public_branches",
        "number",
        nullable=False,
        server_default=sa.text("nextval('branch_number_seq')"),
    )
    op.create_unique_constraint("uq_public_branches_number", "public_branches", ["number"])
    op.add_column(
        "public_branches",
        sa.Column("status", sa.String(10), nullable=False, server_default="Forming"),
    )
    op.execute("UPDATE public_branches SET status = 'Active' WHERE is_published")
    op.add_column("public_branches", sa.Column("lead_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_branch_lead", "public_branches", "users", ["lead_id"], ["id"], ondelete="SET NULL"
    )
    op.create_unique_constraint("uq_public_branches_lead_id", "public_branches", ["lead_id"])
    op.add_column(
        "public_branches", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
    )
    for name in ("created_at", "updated_at"):
        op.add_column(
            "public_branches",
            sa.Column(
                name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
            ),
        )
    op.create_index("ix_public_branches_status", "public_branches", ["status"])
    op.create_check_constraint(
        "ck_branch_status", "public_branches", "status IN ('Forming','Active','Paused','Closed')"
    )
    op.create_check_constraint(
        "ck_branch_publication", "public_branches", "NOT is_published OR status = 'Active'"
    )
    op.create_check_constraint(
        "ck_branch_closed_lead", "public_branches", "status <> 'Closed' OR lead_id IS NULL"
    )
    op.create_table(
        "branch_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("public_branches.id"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("before", postgresql.JSONB()),
        sa.Column("after", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_branch_audits_branch_id", "branch_audits", ["branch_id"])


def downgrade():
    op.drop_table("branch_audits")
    for name in ("ck_branch_closed_lead", "ck_branch_publication", "ck_branch_status"):
        op.drop_constraint(name, "public_branches", type_="check")
    op.drop_index("ix_public_branches_status", "public_branches")
    op.drop_constraint("uq_public_branches_lead_id", "public_branches", type_="unique")
    op.drop_constraint("fk_branch_lead", "public_branches", type_="foreignkey")
    op.drop_constraint("uq_public_branches_number", "public_branches", type_="unique")
    for name in ("updated_at", "created_at", "version", "lead_id", "status", "number"):
        op.drop_column("public_branches", name)
    sa.Sequence("branch_number_seq").drop(op.get_bind())
