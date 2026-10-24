import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.dependencies import Principal, require_api_access, require_roles
from app.login import DB, profile
from app.models import SecurityEvent, User, UserRole
from app.passwords import hash_password, validate_new_password
from app.sessions import revoke_user_sessions, utc_now

router = APIRouter(prefix="/api/staff", tags=["staff"], dependencies=[Depends(require_api_access)])
Admin = Annotated[Principal, Depends(require_roles(UserRole.SUPER_ADMIN))]


class ResetPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temporary_password: str = Field(min_length=15, max_length=72)

    @field_validator("temporary_password")
    @classmethod
    def password_policy(cls, value):
        return validate_new_password(value)


class CreateStaff(ResetPassword):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    role: UserRole

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Name is required.")
        return value.strip()

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        value = value.strip().lower()
        if value.count("@") != 1 or any(c.isspace() for c in value) or not all(value.split("@")):
            raise ValueError("Enter a valid email address.")
        return value


@router.get("")
def list_staff(
    db: DB, admin: Admin, offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)
):
    rows = db.scalars(select(User).order_by(User.email).offset(offset).limit(limit)).all()
    result = [profile(row) for row in rows]
    db.commit()
    return result


@router.post("", status_code=201)
def create_staff(data: CreateStaff, db: DB, admin: Admin):
    user = User(
        name=data.name,
        email=data.email,
        role=data.role,
        password_hash=hash_password(data.temporary_password),
        must_change_password=True,
        temporary_password_expires_at=utc_now()
        + timedelta(seconds=get_settings().temporary_password_seconds),
    )
    db.add(user)
    try:
        db.flush()
        db.add(SecurityEvent(actor_id=admin.user.id, subject_id=user.id, action="staff_created"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from None
    return profile(user)


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(user_id: uuid.UUID, data: ResetPassword, db: DB, admin: Admin):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(404, "Account not found.")
    if user.id == admin.user.id:
        raise HTTPException(422, "Use Change password for your own account.")
    user.password_hash = hash_password(data.temporary_password)
    user.must_change_password = True
    user.temporary_password_expires_at = utc_now() + timedelta(
        seconds=get_settings().temporary_password_seconds
    )
    user.credential_version += 1
    revoke_user_sessions(db, user)
    db.add(SecurityEvent(actor_id=admin.user.id, subject_id=user.id, action="staff_password_reset"))
    db.commit()
