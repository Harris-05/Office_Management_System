"""Adopt explicit development catalogue samples without overwriting authored drafts."""

import uuid

from sqlalchemy import select

from app.content_models import ContentDocument, ContentRevision
from app.public_models import Program, PublicEvent


def adopt_catalogue_record(db, target):
    """Used by the opt-in demo seeder after migrations, inside its transaction."""
    if not isinstance(target, (Program, PublicEvent)):
        return
    program = isinstance(target, Program)
    column = ContentDocument.program_id if program else ContentDocument.event_id
    if db.scalar(select(ContentDocument.id).where(column == target.id)):
        return
    fields = {
        key: getattr(target, key)
        for key in ("slug", "title", "title_ur", "description", "description_ur")
    }
    fields["kind"] = "program" if program else "event"
    if program:
        fields.update(audience=target.audience, audience_ur=target.audience_ur)
    else:
        fields.update(
            branch_id=str(target.branch_id),
            starts_at=target.starts_at.isoformat(),
            ends_at=target.ends_at.isoformat(),
        )
    row = ContentDocument(
        id=uuid.uuid4(),
        kind=fields["kind"],
        program_id=target.id if program else None,
        event_id=None if program else target.id,
        draft=fields,
        published=fields if target.is_published else None,
        is_published=target.is_published,
        version=1,
    )
    db.add(row)
    db.flush()
    db.add(
        ContentRevision(
            document_id=row.id,
            version=1,
            action="imported",
            reason="Existing development example adopted without changing public content",
            snapshot={
                "draft": row.draft,
                "published": row.published,
                "is_published": row.is_published,
            },
        )
    )
