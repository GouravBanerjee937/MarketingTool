import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.brand import Brand


class BrandVoice(Base):
    """Brand Voice — how the brand writes, plus words it must never use.

    One row per brand. `voice_samples` holds example external posts (pasted text
    or the extracted text of an uploaded document) used to teach the LLM the
    brand's writing style; each item is ``{"label": str, "text": str}``.
    `banned_words` is a list of words that must not appear in any generated theme
    or content.
    """

    __tablename__ = "brand_voices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    voice_samples: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    banned_words: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    brand: Mapped["Brand"] = relationship(back_populates="brand_voice")
