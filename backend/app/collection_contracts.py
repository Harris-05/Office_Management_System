import re
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_serializer, field_validator

from app.membership_contracts import BranchOption, Person

PKT = timezone(timedelta(hours=5), "PKT")


def money(value: Decimal) -> str:
    return format(value, ".2f")


class CollectionFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    collected_on: date
    collector_name: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=1000)

    @field_validator("amount", mode="before")
    @classmethod
    def amount_string(cls, value):
        if not isinstance(value, str) or not re.fullmatch(
            r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?", value.strip()
        ):
            raise ValueError("Supply a positive decimal string with up to two decimal places.")
        return value.strip()

    @field_validator("collected_on")
    @classmethod
    def past_or_today(cls, value):
        if value > datetime.now(PKT).date():
            raise ValueError("Collection date cannot be in the future.")
        return value

    @field_validator("*")
    @classmethod
    def safe_text(cls, value, info: ValidationInfo):
        allowed = "\n\r\t" if info.field_name in {"notes", "reason"} else ""
        if isinstance(value, str) and any(
            unicodedata.category(c) in {"Cc", "Cs"} and c not in allowed for c in value
        ):
            raise ValueError("Control characters are not allowed.")
        return value


class CollectionCreate(CollectionFields):
    request_id: uuid.UUID
    expected_branch_id: uuid.UUID


class CollectionUpdate(CollectionFields):
    expected_version: int = Field(strict=True, ge=1)
    reason: str = Field(min_length=3, max_length=500)


class CollectionView(BaseModel):
    id: uuid.UUID
    code: str
    branch: BranchOption
    amount: str
    currency: Literal["PKR"]
    collected_on: date
    collector_name: str
    notes: str
    creator: Person | None
    created_at: datetime
    updated_at: datetime
    locks_at: datetime
    version: int
    is_locked: bool
    can_edit: bool
    server_time: datetime


class CollectionPage(BaseModel):
    items: list[CollectionView]
    total: int
    offset: int
    limit: int
    total_amount: Decimal
    currency: Literal["PKR"] = "PKR"
    server_time: datetime

    @field_serializer("total_amount")
    def total_string(self, value):
        return money(value)
