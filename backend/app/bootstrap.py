"""Interactive one-time first administrator setup; passwords never enter CLI arguments."""

from datetime import timedelta
from getpass import getpass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_engine
from app.models import SecurityEvent, User, UserRole
from app.passwords import hash_password, validate_new_password
from app.sessions import utc_now
from app.staff import CreateStaff


def bootstrap_admin(db: Session, name: str, email: str, password: str) -> User:
    db.execute(text("SELECT pg_advisory_xact_lock(87361421)"))
    if db.scalar(select(User.id).where(User.role == UserRole.SUPER_ADMIN).limit(1)):
        raise ValueError("A Super Admin already exists. Use staff management instead.")
    data = CreateStaff(
        name=name, email=email, role=UserRole.SUPER_ADMIN, temporary_password=password
    )
    user = User(
        name=data.name,
        email=data.email,
        role=data.role,
        password_hash=hash_password(password),
        must_change_password=True,
        temporary_password_expires_at=utc_now()
        + timedelta(seconds=get_settings().temporary_password_seconds),
    )
    db.add(user)
    db.flush()
    db.add(SecurityEvent(subject_id=user.id, action="admin_bootstrapped"))
    return user


def main():
    name = input("Administrator name: ").strip()
    email = input("Existing email address: ").strip()
    password = getpass("Temporary password (15+ characters, max 72 UTF-8 bytes): ")
    if password != getpass("Confirm temporary password: "):
        raise SystemExit("Passwords do not match.")
    try:
        validate_new_password(password)
        with Session(get_engine()) as db, db.begin():
            bootstrap_admin(db, name, email, password)
    except ValueError:
        raise SystemExit(
            "Setup rejected. Check the input and whether an administrator exists."
        ) from None
    print("Administrator created. Change the temporary password at first login.")


if __name__ == "__main__":
    main()
