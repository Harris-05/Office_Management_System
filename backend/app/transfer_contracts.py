import unicodedata
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.collection_contracts import PKT
from app.membership_contracts import BranchOption, Person

TransferStatus = Literal["Submitted", "Returned", "Confirmed", "Cancelled"]


class TransferInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", check_fields=False)
    @classmethod
    def safe_text(cls, value, info: ValidationInfo):
        allowed = "\n\r\t" if info.field_name in {"notes", "reason"} else ""
        if isinstance(value, str) and any(
            unicodedata.category(c) in {"Cc", "Cs"} and c not in allowed for c in value
        ):
            raise ValueError("Control characters are not allowed.")
        return value


class TransferMetadata(TransferInput):
    transferred_on: date
    reference: str = Field(min_length=3, max_length=120)
    notes: str = Field(default="", max_length=1000)

    @field_validator("transferred_on")
    @classmethod
    def not_future(cls, value):
        if value > datetime.now(PKT).date():
            raise ValueError("Transfer date cannot be in the future.")
        return value


class TransferCreate(TransferMetadata):
    request_id: uuid.UUID
    expected_branch_id: uuid.UUID
    collection_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)

    @field_validator("collection_ids")
    @classmethod
    def unique_ids(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Choose each collection only once.")
        return value


class TransferCommand(TransferInput):
    expected_version: int = Field(strict=True, ge=1)
    reason: str = Field(min_length=3, max_length=500)


class TransferResubmit(TransferMetadata, TransferCommand):
    pass


class TransferItemView(BaseModel):
    collection_id: uuid.UUID
    code: str
    amount: str
    collected_on: date
    collection_version: int


class TransferView(BaseModel):
    id: uuid.UUID
    code: str
    branch: BranchOption
    amount: str
    currency: Literal["PKR"] = "PKR"
    transferred_on: date
    reference: str
    notes: str
    status: TransferStatus
    version: int
    creator: Person | None
    reviewer: Person | None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    items: list[TransferItemView]
    can_confirm: bool
    can_return: bool
    can_cancel: bool
    can_resubmit: bool


class TransferBalances(BaseModel):
    recorded: str
    not_submitted: str
    eligible: str
    awaiting_confirmation: str
    confirmed_received: str
    currency: Literal["PKR"] = "PKR"
