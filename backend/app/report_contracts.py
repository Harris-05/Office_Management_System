import unicodedata
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator

from app.membership_contracts import Command

ReportStatus = Literal["Draft", "Submitted", "Returned", "Approved"]


class NarrativeCommand(Command):
    narrative: str = Field(max_length=10000)

    @field_validator("*")
    @classmethod
    def safe_text(cls, value, info: ValidationInfo):
        allowed = "\n\r\t" if info.field_name in {"reason", "narrative"} else ""
        if isinstance(value, str) and any(
            unicodedata.category(character) in {"Cc", "Cs"} and character not in allowed
            for character in value
        ):
            raise ValueError("Control characters are not allowed.")
        return value


class ReportReview(Command):
    acknowledge: Literal[True]
