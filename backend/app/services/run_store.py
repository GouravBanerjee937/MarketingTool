"""Persist captured LLM calls (from run_log) into the llm_runs table."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run import LlmRun


async def persist(
    db: AsyncSession,
    brand_id: uuid.UUID | None,
    stage: str,
    entries: list[dict],
) -> None:
    if not entries:
        return
    for i, e in enumerate(entries):
        db.add(
            LlmRun(
                brand_id=brand_id,
                stage=stage,
                seq=i,
                system_prompt=e["system"],
                user_prompt=e["user"],
                response=e["response"],
            )
        )
    await db.commit()
