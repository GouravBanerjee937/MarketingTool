import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.brand import Brand
from app.models.competitor import Competitor
from app.models.persona import Persona
from app.models.voice import BrandVoice
from app.schemas.content import (
    ContentGenerateIn,
    ContentGenerateOut,
    ContentThemesIn,
    ContentThemesOut,
)
from app.services import report, run_log, run_store
from app.services.llm import (
    LLMNotConfigured,
    generate_content,
    suggest_content_themes,
)

router = APIRouter(tags=["content"])


async def _load_brand_brain(brand_id: uuid.UUID, db: AsyncSession):
    """Load a brand plus its personas and considered competitors (stages 1-3)."""
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")

    personas_res = await db.execute(
        select(Persona)
        .where(Persona.brand_id == brand_id)
        .order_by(Persona.position, Persona.created_at)
    )
    personas = list(personas_res.scalars().all())

    comps_res = await db.execute(
        select(Competitor)
        .where(
            Competitor.brand_id == brand_id,
            Competitor.status == "considered",
        )
        .order_by(Competitor.is_primary.desc(), Competitor.position)
    )
    competitors = [
        {
            "name": c.name,
            "is_primary": c.is_primary,
            "moats": (c.analysis or {}).get("moats") if c.analysis else None,
        }
        for c in comps_res.scalars().all()
    ]

    voice_res = await db.execute(
        select(BrandVoice).where(BrandVoice.brand_id == brand_id)
    )
    voice = voice_res.scalar_one_or_none()
    voice_samples = (
        [s.get("text", "") for s in (voice.voice_samples or [])] if voice else []
    )
    banned_words = list(voice.banned_words or []) if voice else []
    return brand, personas, competitors, voice_samples, banned_words


@router.post("/brands/{brand_id}/content/themes", response_model=ContentThemesOut)
async def suggest_brand_content_themes(
    brand_id: uuid.UUID,
    payload: ContentThemesIn,
    db: AsyncSession = Depends(get_db),
):
    """Suggest 4-5 content themes grounded in the brand brain (stages 1-3) and the
    chosen platform's guidelines. The user picks one before generating."""
    brand, personas, competitors, voice_samples, banned_words = await _load_brand_brain(
        brand_id, db
    )
    try:
        with run_log.capture("content:themes") as runs:
            themes = await suggest_content_themes(
                brand_name=brand.name,
                vision=brand.vision,
                goal=brand.goal,
                moat=brand.moat,
                personas=personas,
                competitors=competitors,
                form=payload.form,
                content_format=payload.content_format,
                platform=payload.platform,
                voice_samples=voice_samples,
                banned_words=banned_words,
            )
        await run_store.persist(db, brand_id, "content:themes", runs)
    except LLMNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:  # noqa: BLE001 — surface provider errors cleanly
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Theme suggestion failed: {e}"
        )
    await report.refresh(db, brand_id)
    return ContentThemesOut(themes=themes)


@router.post(
    "/brands/{brand_id}/content/generate", response_model=ContentGenerateOut
)
async def generate_brand_content(
    brand_id: uuid.UUID,
    payload: ContentGenerateIn,
    db: AsyncSession = Depends(get_db),
):
    """Generate marketing content grounded in the brand brain (stages 1-3), the
    chosen platform's guidelines, and (optionally) a chosen theme."""
    brand, personas, competitors, voice_samples, banned_words = await _load_brand_brain(
        brand_id, db
    )
    stage = f"content:generate:{payload.platform}"
    try:
        with run_log.capture(stage) as runs:
            script = await generate_content(
                brand_name=brand.name,
                vision=brand.vision,
                goal=brand.goal,
                moat=brand.moat,
                personas=personas,
                competitors=competitors,
                form=payload.form,
                content_format=payload.content_format,
                platform=payload.platform,
                theme_title=payload.theme_title,
                theme_angle=payload.theme_angle,
                voice_samples=voice_samples,
                banned_words=banned_words,
            )
        await run_store.persist(db, brand_id, stage, runs)
    except LLMNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:  # noqa: BLE001 — surface provider errors cleanly
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Content generation failed: {e}"
        )
    await report.refresh(db, brand_id)
    return ContentGenerateOut(script=script)
