import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.competitor import COMPETITOR_STATUSES
from app.schemas.brand import BrandOut
from app.schemas.persona import PersonaOut


class CompetitorScopeIn(BaseModel):
    regions: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("regions")
    @classmethod
    def clean_regions(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            s = (item or "").strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
        return out


class CompetitorScopeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    regions: list[str]
    created_at: datetime
    updated_at: datetime


class BrandContextOut(BaseModel):
    """Aggregated context from the earlier stages, for the selected brand."""

    brand: BrandOut
    personas: list[PersonaOut]


class CompetitorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    website: str | None
    description: str | None
    source: str
    status: str
    is_primary: bool
    analysis: dict | None = None
    position: int


class CompetitorCreate(BaseModel):
    """A competitor added manually by the user."""

    name: str = Field(min_length=1, max_length=200)
    website: str | None = Field(default=None, max_length=255)
    source: str = "tailored"

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("website")
    @classmethod
    def clean_website(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("source")
    @classmethod
    def valid_source(cls, v: str) -> str:
        if v not in ("tailored", "general"):
            raise ValueError("source must be tailored or general")
        return v


class CompetitorStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in COMPETITOR_STATUSES:
            raise ValueError(f"status must be one of {COMPETITOR_STATUSES}")
        return v
