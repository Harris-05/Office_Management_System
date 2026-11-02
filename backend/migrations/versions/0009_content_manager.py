"""Private bilingual content drafts and append-only revision history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "content_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("program_id", sa.Uuid(), sa.ForeignKey("public_programs.id"), unique=True),
        sa.Column("event_id", sa.Uuid(), sa.ForeignKey("public_events.id"), unique=True),
        sa.Column("page_key", sa.String(10), unique=True),
        sa.Column("draft", postgresql.JSONB(), nullable=False),
        sa.Column("published", postgresql.JSONB()),
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("kind IN ('program','event','page')", name="ck_content_kind"),
        sa.CheckConstraint("version > 0", name="ck_content_version"),
        sa.CheckConstraint(
            "(kind = 'program' AND program_id IS NOT NULL AND event_id IS NULL AND page_key IS NULL) OR "
            "(kind = 'event' AND event_id IS NOT NULL AND program_id IS NULL AND page_key IS NULL) OR "
            "(kind = 'page' AND program_id IS NULL AND event_id IS NULL AND page_key IS NOT NULL "
            "AND page_key IN ('home','about','contact'))",
            name="ck_content_target",
        ),
        sa.CheckConstraint(
            "NOT is_published OR published IS NOT NULL", name="ck_content_published"
        ),
    )
    op.create_index("ix_content_documents_kind", "content_documents", ["kind"])
    op.create_table(
        "content_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("content_documents.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("document_id", "version", name="uq_content_revision_version"),
        sa.CheckConstraint("version > 0", name="ck_content_revision_version"),
    )
    op.create_index("ix_content_revisions_document_id", "content_revisions", ["document_id"])
    # Adopt existing catalogue records, retaining their IDs, publication and demo labels.
    # A deterministic document ID equals its existing target ID (UUIDs are globally random).
    for kind, table, target, extra in (
        (
            "program",
            "public_programs",
            "program_id",
            "'audience', audience, 'audience_ur', audience_ur",
        ),
        (
            "event",
            "public_events",
            "event_id",
            "'branch_id', branch_id::text, 'starts_at', starts_at, 'ends_at', ends_at",
        ),
    ):
        fields = (
            "jsonb_build_object('kind', '" + kind + "', 'slug', slug, 'title', title, "
            "'title_ur', title_ur, 'description', description, 'description_ur', description_ur, "
            + extra
            + ")"
        )
        op.execute(
            sa.text(
                f"INSERT INTO content_documents (id,kind,{target},draft,published,is_published,version) "
                f"SELECT id,'{kind}',id,{fields},CASE WHEN is_published THEN {fields} ELSE NULL END,"
                f"is_published,1 FROM {table}"
            )
        )
    op.execute(
        sa.text(
            "INSERT INTO content_revisions (id,document_id,version,action,reason,snapshot) "
            "SELECT id,id,1,'imported','Existing catalogue adopted without changing public content',"
            "jsonb_build_object('draft',draft,'published',published,'is_published',is_published) FROM content_documents"
        )
    )


def downgrade():
    op.drop_table("content_revisions")
    op.drop_table("content_documents")
