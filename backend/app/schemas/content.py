from pydantic import BaseModel, Field, field_validator


class _ContentReqBase(BaseModel):
    """Shared inputs for content theme suggestion and generation."""

    form: str  # 'long' | 'short'
    content_format: str = Field(min_length=1, max_length=80)
    platform: str = Field(min_length=1, max_length=80)

    @field_validator("form")
    @classmethod
    def valid_form(cls, v: str) -> str:
        if v not in ("long", "short"):
            raise ValueError("form must be 'long' or 'short'")
        return v

    @field_validator("content_format", "platform")
    @classmethod
    def strip_nonempty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class ContentThemesIn(_ContentReqBase):
    pass


class ContentTheme(BaseModel):
    title: str
    angle: str


class ContentThemesOut(BaseModel):
    themes: list[ContentTheme]


class ContentGenerateIn(_ContentReqBase):
    """Generation request — optionally for a chosen theme."""

    theme_title: str | None = Field(default=None, max_length=200)
    theme_angle: str | None = Field(default=None, max_length=600)


class ContentGenerateOut(BaseModel):
    script: str
