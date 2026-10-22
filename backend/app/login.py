from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.users import authenticate_user

router = APIRouter(prefix="/api", tags=["login"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserProfile(BaseModel):
    name: str
    email: str
    role: str


@router.post("/login", response_model=UserProfile)
def login(credentials: LoginRequest, session: Annotated[Session, Depends(get_db)]) -> UserProfile:
    user = authenticate_user(session, credentials.email, credentials.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return UserProfile(name=user.name, email=user.email, role=user.role.value)
