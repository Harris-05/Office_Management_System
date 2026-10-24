"""Bounded private workflow contracts."""

import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

Search = Annotated[str, Query(max_length=160, pattern=r"^[^\x00-\x1f\x7f]*$")]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
ApplicationStatus = Literal["Pending", "Accepted", "Declined"]
MemberStatus = Literal["Active", "Inactive"]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_version: int = Field(strict=True, ge=1)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("*")
    @classmethod
    def safe_text(cls, value, info: ValidationInfo):
        allowed = "\n\r\t" if info.field_name == "reason" else ""
        if isinstance(value, str) and any(
            unicodedata.category(c) in {"Cc", "Cs"} and c not in allowed for c in value
        ):
            raise ValueError("Control characters are not allowed.")
        return value


class ReviewCommand(Command):
    decision: Literal["Accepted", "Declined"]


class MemberCommand(Command):
    team: str = Field(max_length=80)
    organisational_role: str = Field(min_length=1, max_length=100)
    status: MemberStatus


class Person(BaseModel):
    id: uuid.UUID
    name: str


class BranchOption(Person):
    code: str
    status: str


class MemberSummary(Person):
    code: str


class ApplicationView(Person):
    email: str
    subject: str
    message: str
    branch: BranchOption | None
    status: ApplicationStatus
    version: int
    created_at: datetime
    expires_at: datetime
    reviewed_at: datetime | None
    reviewer: Person | None
    reason: str | None
    member: MemberSummary | None


class MemberView(MemberSummary):
    email: str
    branch: BranchOption
    source_id: uuid.UUID | None
    status: MemberStatus
    team: str
    organisational_role: str
    version: int
    created_at: datetime
    updated_at: datetime


class EventView(BaseModel):
    id: uuid.UUID
    actor: Person | None
    action: str
    reason: str | None
    before: dict | None
    after: dict
    created_at: datetime


class Page[T](BaseModel):
    items: list[T]
    total: int
    offset: int
    limit: int
