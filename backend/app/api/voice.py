import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.brand import Brand
from app.models.voice import BrandVoice
from app.schemas.voice import BrandVoiceIn, BrandVoiceOut

router = APIRouter(tags=["brand-voice"])


async def _get_brand_or_404(brand_id: uuid.UUID, db: AsyncSession) -> Brand:
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


async def _get_voice(brand_id: uuid.UUID, db: AsyncSession) -> BrandVoice | None:
    res = await db.execute(select(BrandVoice).where(BrandVoice.brand_id == brand_id))
    return res.scalar_one_or_none()


@router.get("/brands/{brand_id}/brand-voice", response_model=BrandVoiceOut)
async def get_brand_voice(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Fetch the brand's voice samples + banned words (auto-creates an empty row)."""
    await _get_brand_or_404(brand_id, db)
    voice = await _get_voice(brand_id, db)
    if voice is None:
        voice = BrandVoice(brand_id=brand_id)
        db.add(voice)
        await db.commit()
        await db.refresh(voice)
    return voice


@router.put("/brands/{brand_id}/brand-voice", response_model=BrandVoiceOut)
async def put_brand_voice(
    brand_id: uuid.UUID,
    payload: BrandVoiceIn,
    db: AsyncSession = Depends(get_db),
):
    """Replace the brand's voice samples + banned words."""
    await _get_brand_or_404(brand_id, db)
    voice = await _get_voice(brand_id, db)
    if voice is None:
        voice = BrandVoice(brand_id=brand_id)
        db.add(voice)
    voice.voice_samples = [s.model_dump() for s in payload.voice_samples]
    voice.banned_words = payload.banned_words
    await db.commit()
    await db.refresh(voice)
    return voice
