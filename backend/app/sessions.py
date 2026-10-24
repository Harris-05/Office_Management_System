import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthSession, User


def utc_now() -> datetime:
    return datetime.now(UTC)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User | None, now: datetime) -> tuple[AuthSession, str]:
    settings = get_settings()
    lifetime = settings.session_absolute_seconds if user else settings.anonymous_seconds
    token = secrets.token_urlsafe(32)
    row = AuthSession(
        token_digest=digest(token),
        user_id=user.id if user else None,
        csrf_token=secrets.token_urlsafe(32),
        credential_version=user.credential_version if user else None,
        created_at=now,
        expires_at=now + timedelta(seconds=lifetime),
        idle_expires_at=now + timedelta(seconds=min(lifetime, settings.session_idle_seconds)),
    )
    db.add(row)
    db.flush()
    return row, token


def resolve_session(db: Session, token: str | None, now: datetime) -> AuthSession | None:
    if not token or len(token) > 128:
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_digest == digest(token)))
    if row is None:
        return None
    # User-first lock order matches password reset and authenticated session changes.
    if row.user_id:
        user = db.scalar(
            select(User)
            .where(User.id == row.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            not user
            or not user.is_active
            or user.credential_version != row.credential_version
            or (
                user.must_change_password
                and user.temporary_password_expires_at
                and user.temporary_password_expires_at <= now
            )
        ):
            return None
    row = db.scalar(
        select(AuthSession)
        .where(AuthSession.id == row.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or row.expires_at <= now or row.idle_expires_at <= now:
        return None
    if row.user_id:
        row.idle_expires_at = min(
            row.expires_at, now + timedelta(seconds=get_settings().session_idle_seconds)
        )
    return row


def revoke_user_sessions(db: Session, user: User) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))


def set_cookie(response: Response, token: str, row: AuthSession) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=max(0, int((row.expires_at - utc_now()).total_seconds())),
    )


def clear_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.cookie_name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
