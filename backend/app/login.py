from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import Principal, require_api_access
from app.models import SecurityEvent, User
from app.passwords import hash_password, needs_rehash, validate_new_password, verify_password
from app.sessions import clear_cookie, create_session, revoke_user_sessions, set_cookie, utc_now
from app.users import authenticate_user

router = APIRouter(
    prefix="/api", tags=["authentication"], dependencies=[Depends(require_api_access)]
)
DB = Annotated[Session, Depends(get_db)]
Auth = Annotated[Principal, Depends(require_api_access)]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class ChangePassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=15, max_length=72)
    confirm_password: str = Field(min_length=15, max_length=72)


def profile(user: User) -> dict:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "role": user.role.value,
        "must_change_password": user.must_change_password,
    }


@router.get("/csrf")
def csrf(response: Response, db: DB, principal: Auth):
    row = principal.session
    token = None
    if row is None:
        row, token = create_session(db, None, utc_now())
    db.commit()
    if token:
        set_cookie(response, token, row)
    return {"csrf_token": row.csrf_token}


@router.post("/login")
def login(credentials: LoginRequest, response: Response, db: DB, principal: Auth):
    # Verify before locking the user, then recheck the exact credential under lock.
    user = authenticate_user(db, credentials.email, credentials.password)
    if user is None:
        raise HTTPException(401, "Incorrect email or password.")
    verified_hash = user.password_hash
    user = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = utc_now()
    if (
        not user.is_active
        or user.password_hash != verified_hash
        or (
            user.must_change_password
            and user.temporary_password_expires_at
            and user.temporary_password_expires_at <= now
        )
    ):
        raise HTTPException(401, "Incorrect email or password.")
    # The anonymous/current session was locked and validated by the dependency.
    if (
        principal.session is None
        or principal.session.expires_at <= now
        or principal.session.idle_expires_at <= now
    ):
        raise HTTPException(401, "Session expired. Refresh and try again.")
    if (
        needs_rehash(user.password_hash)
        and len(credentials.password.encode("utf-8")) <= 72
        and "\x00" not in credentials.password
    ):
        user.password_hash = hash_password(credentials.password)
    db.delete(principal.session)
    row, token = create_session(db, user, now)
    db.add(SecurityEvent(actor_id=user.id, subject_id=user.id, action="login"))
    db.commit()
    set_cookie(response, token, row)
    return {**profile(user), "csrf_token": row.csrf_token}


@router.get("/me")
def me(db: DB, principal: Auth):
    result = profile(principal.user)
    db.commit()
    return result


@router.post("/logout", status_code=204)
def logout(response: Response, db: DB, principal: Auth):
    db.add(SecurityEvent(actor_id=principal.user.id, subject_id=principal.user.id, action="logout"))
    db.delete(principal.session)
    db.commit()
    clear_cookie(response)


@router.post("/change-password")
def change_password(data: ChangePassword, response: Response, db: DB, principal: Auth):
    user = principal.user
    if data.new_password != data.confirm_password:
        raise HTTPException(422, "New passwords do not match.")
    try:
        validate_new_password(data.new_password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(401, "Current password is incorrect.")
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(422, "Choose a different password.")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    user.temporary_password_expires_at = None
    user.credential_version += 1
    revoke_user_sessions(db, user)
    row, token = create_session(db, user, utc_now())
    db.add(SecurityEvent(actor_id=user.id, subject_id=user.id, action="password_changed"))
    db.commit()
    set_cookie(response, token, row)
    return {**profile(user), "csrf_token": row.csrf_token}
