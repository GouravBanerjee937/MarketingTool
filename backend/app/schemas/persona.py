import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class VariantIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)

    @field_validator("label")
    @classmethod
    def label_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("variant label cannot be blank")
        return v

    @field_validator("description")
    @classmethod
    def strip_desc(cls, v: str | None) -> str | None:
        return _clean(v)


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    description: str | None
    position: int


class PersonaBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    # Define the user
    user_type: str | None = Field(None, max_length=100)
    business_size: str | None = Field(None, max_length=50)
    region: str | None = Field(None, max_length=100)
    # Sub-parts
    pain_points: str | None = Field(None, max_length=2000)
    current_platforms: str | None = Field(None, max_length=2000)
    main_goal: str | None = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("persona name cannot be blank")
        return v

    @field_validator(
        "user_type", "business_size", "region",
        "pain_points", "current_platforms", "main_goal",
    )
    @classmethod
    def strip_optional(cls, v: str | None) -> str | None:
        return _clean(v)


class PersonaCreate(PersonaBase):
    variants: list[VariantIn] = Field(default_factory=list, max_length=20)


class PersonaUpdate(BaseModel):
    """Partial update. If `variants` is provided, it replaces the full list."""

    name: str | None = Field(None, min_length=1, max_length=200)
    user_type: str | None = Field(None, max_length=100)
    business_size: str | None = Field(None, max_length=50)
    region: str | None = Field(None, max_length=100)
    pain_points: str | None = Field(None, max_length=2000)
    current_platforms: str | None = Field(None, max_length=2000)
    main_goal: str | None = Field(None, max_length=2000)
    variants: list[VariantIn] | None = Field(None, max_length=20)

    @field_validator(
        "name", "user_type", "business_size", "region",
        "pain_points", "current_platforms", "main_goal",
    )
    @classmethod
    def strip_fields(cls, v: str | None) -> str | None:
        return _clean(v)


class PersonaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    user_type: str | None
    business_size: str | None
    region: str | None
    pain_points: str | None
    current_platforms: str | None
    main_goal: str | None
    position: int
    variants: list[VariantOut]
    created_at: datetime
    updated_at: datetime
