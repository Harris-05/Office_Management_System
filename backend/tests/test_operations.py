from datetime import timedelta

import pytest
from sqlalchemy import delete, func, or_, select

from app.bootstrap import bootstrap_admin
from app.cleanup_sessions import cleanup
from app.models import AuthSession, User, UserRole
from app.passwords import verify_password
from app.sessions import create_session, resolve_session, utc_now


def test_bootstrap_requires_absent_admin_and_forces_initial_change(db_session):
    with pytest.raises(ValueError):
        bootstrap_admin(db_session, "Admin", "first@example.test", "a temporary admin password")
    db_session.execute(delete(User).where(User.role == UserRole.SUPER_ADMIN))
    user = bootstrap_admin(
        db_session, "First Admin", "first@example.test", "a temporary admin password"
    )
    assert user.role == UserRole.SUPER_ADMIN
    assert user.must_change_password
    assert utc_now() + timedelta(hours=47) < user.temporary_password_expires_at
    assert verify_password("a temporary admin password", user.password_hash)


def test_cleanup_deletes_expired_sessions_without_resurrecting_them(db_session):
    now = utc_now()
    already_expired = db_session.scalar(
        select(func.count())
        .select_from(AuthSession)
        .where(or_(AuthSession.expires_at <= now, AuthSession.idle_expires_at <= now))
    )
    row, token = create_session(db_session, None, now - timedelta(hours=2))
    alive, _ = create_session(db_session, None, now)
    expired_id = row.id
    assert resolve_session(db_session, token, now) is None
    assert cleanup(db_session) == already_expired + 1
    assert db_session.get(AuthSession, expired_id) is None
    assert db_session.scalar(select(AuthSession).where(AuthSession.id == alive.id))
