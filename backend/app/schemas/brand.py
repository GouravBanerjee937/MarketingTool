import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class BrandBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    vision: str | None = Field(None, max_length=2000)
    goal: str | None = Field(None, max_length=2000)
    moat: str | None = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be blank")
        return v

    @field_validator("vision", "goal", "moat")
    @classmethod
    def strip_optional(cls, v: str | None) -> str | None:
        return _clean(v)


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseModel):
    """All fields optional — partial update of brand inputs."""

    name: str | None = Field(None, min_length=1, max_length=200)
    vision: str | None = Field(None, max_length=2000)
    goal: str | None = Field(None, max_length=2000)
    moat: str | None = Field(None, max_length=2000)

    @field_validator("name", "vision", "goal", "moat")
    @classmethod
    def strip_fields(cls, v: str | None) -> str | None:
        return _clean(v)


class BrandOut(BrandBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
