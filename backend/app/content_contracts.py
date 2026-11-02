"""Allowlisted, plain-text bilingual content commands."""

import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class TextFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=160)
    title_ur: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=10000)
    description_ur: str = Field(min_length=1, max_length=10000)

    @field_validator(
        "slug",
        "title",
        "title_ur",
        "description",
        "description_ur",
        "audience",
        "audience_ur",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def plain_text(cls, value):
        if isinstance(value, str) and any(
            unicodedata.category(char) in {"Cc", "Cs"} and char not in "\n\r\t" for char in value
        ):
            raise ValueError("Control characters are not allowed.")
        return value


class ProgramContent(TextFields):
    kind: Literal["program"]
    audience: str = Field(min_length=1, max_length=200)
    audience_ur: str = Field(min_length=1, max_length=200)


class EventContent(TextFields):
    kind: Literal["event"]
    branch_id: uuid.UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("Event end must be after its start.")
        return self


class PageContent(TextFields):
    kind: Literal["page"]
    page_key: Literal["home", "about", "contact"]


ContentPayload = Annotated[ProgramContent | EventContent | PageContent, Field(discriminator="kind")]
ContentKind = Literal["program", "event", "page"]


class Reason(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def safe_reason(cls, value):
        return TextFields.plain_text(value)


class CreateContent(Reason):
    content: ContentPayload


class ContentCommand(Reason):
    expected_version: int = Field(ge=1)


class SaveDraft(ContentCommand):
    content: ContentPayload


class ContentView(BaseModel):
    id: uuid.UUID
    kind: ContentKind
    version: int
    draft: ContentPayload
    published: ContentPayload | None
    is_published: bool
    has_unpublished_changes: bool
    is_demo: bool
    updated_at: datetime


class ContentPage(BaseModel):
    items: list[ContentView]
    total: int
    offset: int
    limit: int


class Preview(BaseModel):
    content: ContentPayload
    version: int


class Actor(BaseModel):
    id: uuid.UUID
    name: str


class RevisionView(BaseModel):
    id: uuid.UUID
    version: int
    action: str
    reason: str
    actor: Actor | None
    created_at: datetime
    snapshot: dict


class RevisionPage(BaseModel):
    items: list[RevisionView]
    total: int
    offset: int
    limit: int


class BranchOption(BaseModel):
    id: uuid.UUID
    name: str
    name_ur: str
    code: str
