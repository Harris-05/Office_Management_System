from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.passwords import verify_password


def find_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = find_user_by_email(session, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user
