import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.brand import Brand

COMPETITOR_STATUSES = ("pending", "considered", "rejected")


class CompetitorScope(Base):
    """Competitors stage — where the brand wants to operate.

    One row per brand. `regions` is the list of markets/regions we want to
    compete in; it seeds later competitor discovery. Built on top of the brand
    context from earlier stages (brand inputs, personas).
    """

    __tablename__ = "competitor_scopes"

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
    regions: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    brand: Mapped["Brand"] = relationship(back_populates="competitor_scope")


class Competitor(Base):
    """A competitor fetched for a brand, awaiting the user's tick/cross gate.

    `status`: pending (just fetched) -> considered (ticked) / rejected (crossed).
    """

    __tablename__ = "competitors"

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
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'tailored' = derived from brand context + personas; 'general' = broad market
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="tailored", server_default="tailored"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    brand: Mapped["Brand"] = relationship(back_populates="competitors")
