"""Run daily to remove visitor correspondence after its 90-day retention window."""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database import get_engine
from app.public_models import PublicSubmission
from app.sessions import utc_now


def cleanup(session: Session) -> int:
    result = session.execute(
        delete(PublicSubmission).where(PublicSubmission.expires_at <= utc_now())
    )
    return result.rowcount


if __name__ == "__main__":
    with Session(get_engine()) as session, session.begin():
        count = cleanup(session)
    print(f"Removed {count} expired public submissions.")
