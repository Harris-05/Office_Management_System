from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.passwords import dummy_hash, verify_password


def find_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = find_user_by_email(session, email)
    verified = verify_password(password, user.password_hash if user else dummy_hash())
    if user is None or not verified or not user.is_active:
        return None
    return user
