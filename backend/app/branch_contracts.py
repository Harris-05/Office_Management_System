import unicodedata
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BranchStatus = Literal["Forming", "Active", "Paused", "Closed"]


class BranchFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    name_ur: str = Field(min_length=1, max_length=160)
    city: str = Field(min_length=1, max_length=100)
    city_ur: str = Field(min_length=1, max_length=100)
    address: str = Field(min_length=1, max_length=300)
    address_ur: str = Field(min_length=1, max_length=300)
    hours: str = Field(min_length=1, max_length=160)
    hours_ur: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=4000)
    description_ur: str = Field(min_length=1, max_length=4000)

    @field_validator("*")
    @classmethod
    def safe_text(cls, value):
        if isinstance(value, str) and any(
            unicodedata.category(c) == "Cc" and c not in "\n\t" for c in value
        ):
            raise ValueError("Control characters are not allowed.")
        return value


class ExpectedVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)


class BranchUpdate(BranchFields, ExpectedVersion):
    pass


class StatusChange(ExpectedVersion):
    status: BranchStatus
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        value = value.strip()
        if len(value) < 3 or any(unicodedata.category(c) == "Cc" for c in value):
            raise ValueError("A readable reason is required.")
        return value


class LeadChange(ExpectedVersion):
    lead_id: uuid.UUID | None


class PublicationChange(ExpectedVersion):
    is_published: bool = Field(strict=True)


class LeadSummary(BaseModel):
    id: uuid.UUID
    name: str


class BranchView(BranchFields):
    id: uuid.UUID
    code: str
    slug: str
    status: BranchStatus
    is_published: bool
    is_demo: bool
    version: int
    lead: LeadSummary | None
    created_at: datetime
    updated_at: datetime


class BranchPage(BaseModel):
    items: list[BranchView]
    total: int
    offset: int
    limit: int


class LeadOption(LeadSummary):
    email: str
    branch_id: uuid.UUID | None
    branch_code: str | None


class LeadPage(BaseModel):
    items: list[LeadOption]
    total: int
    offset: int
    limit: int


class AuditView(BaseModel):
    id: uuid.UUID
    actor: LeadSummary | None
    action: str
    reason: str | None
    before: dict | None
    after: dict
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditView]
    total: int
    offset: int
    limit: int
