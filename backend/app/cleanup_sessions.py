from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import AuthSession
from app.sessions import utc_now


def cleanup(db: Session) -> int:
    now = utc_now()
    return db.execute(
        delete(AuthSession).where(
            or_(AuthSession.expires_at <= now, AuthSession.idle_expires_at <= now)
        )
    ).rowcount


def main():
    with Session(get_engine()) as db, db.begin():
        count = cleanup(db)
    print(f"Removed {count} expired sessions.")


if __name__ == "__main__":
    main()
