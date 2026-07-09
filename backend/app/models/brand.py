import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.competitor import Competitor, CompetitorScope
    from app.models.persona import Persona
    from app.models.voice import BrandVoice


class Brand(Base):
    """Top-level brand entity.

    Phase 1 (Brand inputs) fields: vision, goal, moat. Later phases attach
    related tables (personas, competitors, pillars) via this brand id.
    """

    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Phase 1 — Brand inputs
    vision: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    moat: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 2 — ICP builder
    personas: Mapped[list["Persona"]] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Persona.position",
    )

    # Competitors (one-to-one scope)
    competitor_scope: Mapped["CompetitorScope"] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Competitor.position",
    )

    # Brand Voice (one-to-one: writing-style samples + banned words)
    brand_voice: Mapped["BrandVoice"] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
