import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.brand import Brand

MAX_PERSONAS_PER_BRAND = 5


class Persona(Base):
    """Phase 2 — ICP builder. A core buyer type for a brand (up to 5 per brand)."""

    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Who is this user? (structured definition)
    user_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Qualitative sub-parts
    pain_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_platforms: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_goal: Mapped[str | None] = mapped_column(Text, nullable=True)

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    brand: Mapped["Brand"] = relationship(back_populates="personas")
    variants: Mapped[list["PersonaVariant"]] = relationship(
        back_populates="persona",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PersonaVariant.position",
    )


class PersonaVariant(Base):
    """A sub-group within a persona — one buyer type flexed for a situation."""

    __tablename__ = "persona_variants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    persona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    persona: Mapped["Persona"] = relationship(back_populates="variants")
