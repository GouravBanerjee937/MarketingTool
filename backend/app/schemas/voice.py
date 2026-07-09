import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VoiceSample(BaseModel):
    """One writing-style example — a pasted snippet or an uploaded doc's text."""

    label: str = Field(default="", max_length=200)
    text: str = Field(min_length=1, max_length=20000)

    @field_validator("label")
    @classmethod
    def clean_label(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("text")
    @classmethod
    def clean_text(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("sample text must not be empty")
        return v


class BrandVoiceIn(BaseModel):
    voice_samples: list[VoiceSample] = Field(default_factory=list, max_length=25)
    banned_words: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("banned_words")
    @classmethod
    def clean_words(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            s = (item or "").strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        return out


class BrandVoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    voice_samples: list[VoiceSample]
    banned_words: list[str]
    created_at: datetime
    updated_at: datetime
