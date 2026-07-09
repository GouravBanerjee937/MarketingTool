import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.brand import Brand
from app.models.persona import MAX_PERSONAS_PER_BRAND, Persona, PersonaVariant
from app.schemas.persona import PersonaCreate, PersonaOut, PersonaUpdate, VariantIn

router = APIRouter(tags=["personas"])


def _build_variants(items: list[VariantIn]) -> list[PersonaVariant]:
    return [
        PersonaVariant(label=v.label, description=v.description, position=i)
        for i, v in enumerate(items)
    ]


async def _load_persona(persona_id: uuid.UUID, db: AsyncSession) -> Persona:
    result = await db.execute(
        select(Persona)
        .where(Persona.id == persona_id)
        .options(selectinload(Persona.variants))
    )
    persona = result.scalar_one_or_none()
    if persona is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Persona not found")
    return persona


async def _ensure_brand(brand_id: uuid.UUID, db: AsyncSession) -> None:
    if await db.get(Brand, brand_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")


@router.get("/brands/{brand_id}/personas", response_model=list[PersonaOut])
async def list_personas(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _ensure_brand(brand_id, db)
    result = await db.execute(
        select(Persona)
        .where(Persona.brand_id == brand_id)
        .options(selectinload(Persona.variants))
        .order_by(Persona.position, Persona.created_at)
    )
    return result.scalars().all()


@router.post(
    "/brands/{brand_id}/personas",
    response_model=PersonaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_persona(
    brand_id: uuid.UUID,
    payload: PersonaCreate,
    db: AsyncSession = Depends(get_db),
):
    await _ensure_brand(brand_id, db)

    count = await db.scalar(
        select(func.count()).select_from(Persona).where(Persona.brand_id == brand_id)
    )
    if count >= MAX_PERSONAS_PER_BRAND:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"A brand can have at most {MAX_PERSONAS_PER_BRAND} personas.",
        )

    fields = payload.model_dump(exclude={"variants"})
    persona = Persona(
        brand_id=brand_id,
        position=count,
        variants=_build_variants(payload.variants),
        **fields,
    )
    db.add(persona)
    await db.commit()
    return await _load_persona(persona.id, db)


@router.patch("/personas/{persona_id}", response_model=PersonaOut)
async def update_persona(
    persona_id: uuid.UUID,
    payload: PersonaUpdate,
    db: AsyncSession = Depends(get_db),
):
    persona = await _load_persona(persona_id, db)
    data = payload.model_dump(exclude_unset=True)

    if data.get("name") is not None:
        persona.name = data["name"]
    for field in ("user_type", "business_size", "region",
                  "pain_points", "current_platforms", "main_goal"):
        if field in data:
            setattr(persona, field, data[field])
    if data.get("variants") is not None:
        persona.variants = _build_variants(payload.variants)

    await db.commit()
    return await _load_persona(persona.id, db)


@router.delete("/personas/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(persona_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    persona = await _load_persona(persona_id, db)
    await db.delete(persona)
    await db.commit()
