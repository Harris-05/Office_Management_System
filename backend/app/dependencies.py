import secrets
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuthSession, User, UserRole
from app.sessions import resolve_session, utc_now

PUBLIC = {("GET", "/api/csrf"), ("POST", "/api/login")}
CHANGE_ALLOWED = {"/api/me", "/api/change-password", "/api/logout", "/api/csrf"}


@dataclass
class Principal:
    user: User | None
    session: AuthSession | None


def require_api_access(request: Request, db: Annotated[Session, Depends(get_db)]) -> Principal:
    if not (request.url.path == "/api" or request.url.path.startswith("/api/")):
        return Principal(None, None)
    settings = get_settings()
    row = resolve_session(db, request.cookies.get(settings.cookie_name), utc_now())
    user = db.get(User, row.user_id) if row and row.user_id else None
    public = (request.method, request.url.path) in PUBLIC
    if not public and not user:
        raise HTTPException(401, "Authentication required.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        csrf = request.headers.get("x-csrf-token", "")
        if (
            origin not in settings.allowed_origins
            or not row
            or not secrets.compare_digest(csrf.encode("utf-8"), row.csrf_token.encode("utf-8"))
        ):
            raise HTTPException(403, "Request verification failed. Refresh and try again.")
    if user and user.must_change_password:
        if user.temporary_password_expires_at and user.temporary_password_expires_at <= utc_now():
            raise HTTPException(401, "Temporary password expired. Contact your administrator.")
        if request.url.path not in CHANGE_ALLOWED:
            raise HTTPException(403, "Change your temporary password first.")
    return Principal(user, row)


def require_roles(*roles: UserRole):
    def guard(principal: Annotated[Principal, Depends(require_api_access)]) -> Principal:
        if not principal.user or principal.user.role not in roles:
            raise HTTPException(403, "You do not have permission for this action.")
        return principal

    return guard
