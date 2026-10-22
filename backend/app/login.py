"""Temporary demo login; no sessions or authorisation are implemented."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["demo login"])

DEMO_USERS = {
    "admin@example.test": ("Demo Admin", "Super Admin"),
    "finance@example.test": ("Demo Finance Reviewer", "Finance Reviewer"),
    "editor@example.test": ("Demo Content Editor", "Content Editor"),
    "branch@example.test": ("Demo Branch Lead", "Branch Lead"),
    "hr@example.test": ("Demo HR Lead", "HR Lead"),
}
DEMO_PASSWORD = "Demo123!"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class DemoUser(BaseModel):
    name: str
    email: str
    role: str


@router.post("/login", response_model=DemoUser)
def login(credentials: LoginRequest) -> DemoUser:
    email = credentials.email.strip().lower()
    user = DEMO_USERS.get(email)
    if user is None or credentials.password != DEMO_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    return DemoUser(name=user[0], email=email, role=user[1])
