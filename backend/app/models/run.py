import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LlmRun(Base):
    """One recorded LLM call: the exact system + user prompt and the response.

    Written by `run_log` at each `_chat()` call, grouped by the `stage` the API
    endpoint was serving (e.g. 'competitors:fetch:tailored', 'content:generate').
    Powers the Analysis Excel export.
    """

    __tablename__ = "llm_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
