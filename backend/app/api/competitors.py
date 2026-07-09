import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.brand import Brand
from app.models.competitor import Competitor, CompetitorScope
from app.models.persona import Persona
from app.schemas.competitor import (
    BrandContextOut,
    CompetitorCreate,
    CompetitorOut,
    CompetitorScopeIn,
    CompetitorScopeOut,
    CompetitorStatusUpdate,
)
from app.services.llm import (
    LLMNotConfigured,
    analyze_competitor,
    fetch_competitors,
)

router = APIRouter(tags=["competitors"])


async def _get_brand_or_404(brand_id: uuid.UUID, db: AsyncSession) -> Brand:
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("/brands/{brand_id}/context", response_model=BrandContextOut)
async def brand_context(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Pull together everything captured in the earlier stages for this brand."""
    brand = await _get_brand_or_404(brand_id, db)

    personas_res = await db.execute(
        select(Persona)
        .where(Persona.brand_id == brand_id)
        .options(selectinload(Persona.variants))
        .order_by(Persona.position, Persona.created_at)
    )
    return BrandContextOut(
        brand=brand,
        personas=list(personas_res.scalars().all()),
    )


async def _get_scope(brand_id: uuid.UUID, db: AsyncSession) -> CompetitorScope | None:
    res = await db.execute(
        select(CompetitorScope).where(CompetitorScope.brand_id == brand_id)
    )
    return res.scalar_one_or_none()


@router.get("/brands/{brand_id}/competitor-scope", response_model=CompetitorScopeOut)
async def get_scope(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _get_brand_or_404(brand_id, db)
    scope = await _get_scope(brand_id, db)
    if scope is None:
        scope = CompetitorScope(brand_id=brand_id)
        db.add(scope)
        await db.commit()
        await db.refresh(scope)
    return scope


@router.put("/brands/{brand_id}/competitor-scope", response_model=CompetitorScopeOut)
async def put_scope(
    brand_id: uuid.UUID,
    payload: CompetitorScopeIn,
    db: AsyncSession = Depends(get_db),
):
    await _get_brand_or_404(brand_id, db)
    scope = await _get_scope(brand_id, db)
    if scope is None:
        scope = CompetitorScope(brand_id=brand_id)
        db.add(scope)
    scope.regions = payload.regions
    await db.commit()
    await db.refresh(scope)
    return scope


# --- Competitors (fetch + tick/cross gate) ------------------------------

@router.get("/brands/{brand_id}/competitors", response_model=list[CompetitorOut])
async def list_competitors(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _get_brand_or_404(brand_id, db)
    result = await db.execute(
        select(Competitor)
        .where(Competitor.brand_id == brand_id)
        .order_by(Competitor.position, Competitor.name)
    )
    return result.scalars().all()


@router.post(
    "/brands/{brand_id}/competitors/fetch",
    response_model=list[CompetitorOut],
    status_code=status.HTTP_201_CREATED,
)
async def fetch_brand_competitors(
    brand_id: uuid.UUID,
    kind: str = "tailored",
    db: AsyncSession = Depends(get_db),
):
    """Use the LLM + this brand's context (stages 1-2) and regions to suggest
    competitors, saved as `pending` for the user to tick/cross.

    kind='tailored' → competitors specific to the brand's positioning/personas;
    kind='general'  → the broad set of major competitors in the category.
    """
    if kind not in ("tailored", "general"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "kind must be tailored or general")
    brand = await _get_brand_or_404(brand_id, db)

    personas_res = await db.execute(
        select(Persona)
        .where(Persona.brand_id == brand_id)
        .order_by(Persona.position, Persona.created_at)
    )
    personas = list(personas_res.scalars().all())
    scope = await _get_scope(brand_id, db)
    regions = scope.regions if scope else []

    existing_res = await db.execute(
        select(Competitor.name).where(Competitor.brand_id == brand_id)
    )
    existing = {n for (n,) in existing_res.all()}

    try:
        suggestions = await fetch_competitors(
            brand_name=brand.name,
            vision=brand.vision,
            goal=brand.goal,
            moat=brand.moat,
            personas=personas,
            regions=regions,
            exclude_names=existing,
            general=(kind == "general"),
        )
    except LLMNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:  # noqa: BLE001 — surface provider errors cleanly
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Competitor fetch failed: {e}"
        )

    start = await db.scalar(
        select(func.count()).select_from(Competitor).where(Competitor.brand_id == brand_id)
    )
    for i, s in enumerate(suggestions):
        db.add(
            Competitor(
                brand_id=brand_id, position=start + i, status="pending",
                source=kind, **s,
            )
        )
    await db.commit()

    result = await db.execute(
        select(Competitor)
        .where(Competitor.brand_id == brand_id)
        .order_by(Competitor.position, Competitor.name)
    )
    return result.scalars().all()


@router.post(
    "/brands/{brand_id}/competitors",
    response_model=CompetitorOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_competitor(
    brand_id: uuid.UUID,
    payload: CompetitorCreate,
    db: AsyncSession = Depends(get_db),
):
    """Manually add a competitor (name + optional website) to a brand's list,
    saved as `pending` under the given source so it lands in the tick/cross gate."""
    await _get_brand_or_404(brand_id, db)

    dup = await db.scalar(
        select(Competitor).where(
            Competitor.brand_id == brand_id,
            func.lower(Competitor.name) == payload.name.lower(),
        )
    )
    if dup is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"“{payload.name}” is already in the list."
        )

    count = await db.scalar(
        select(func.count()).select_from(Competitor).where(Competitor.brand_id == brand_id)
    )
    comp = Competitor(
        brand_id=brand_id,
        name=payload.name,
        website=payload.website,
        source=payload.source,
        status="pending",
        position=count or 0,
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return comp


async def _load_competitor(competitor_id: uuid.UUID, db: AsyncSession) -> Competitor:
    comp = await db.get(Competitor, competitor_id)
    if comp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Competitor not found")
    return comp


@router.patch("/competitors/{competitor_id}", response_model=CompetitorOut)
async def set_competitor_status(
    competitor_id: uuid.UUID,
    payload: CompetitorStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    comp = await _load_competitor(competitor_id, db)
    comp.status = payload.status
    if payload.status != "considered":
        comp.is_primary = False
    await db.commit()
    await db.refresh(comp)
    return comp


@router.post("/competitors/{competitor_id}/pick", response_model=list[CompetitorOut])
async def pick_primary_competitor(
    competitor_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Pick one considered competitor as the primary — clears any prior pick for
    the same brand. Returns the full competitor list so the client reflects it."""
    comp = await _load_competitor(competitor_id, db)
    # Clear any existing primary for this brand, then set this one.
    await db.execute(
        update(Competitor)
        .where(Competitor.brand_id == comp.brand_id)
        .values(is_primary=False)
    )
    comp.is_primary = True
    if comp.status != "considered":
        comp.status = "considered"
    await db.commit()

    result = await db.execute(
        select(Competitor)
        .where(Competitor.brand_id == comp.brand_id)
        .order_by(Competitor.position, Competitor.name)
    )
    return result.scalars().all()


@router.post("/competitors/{competitor_id}/analyze", response_model=CompetitorOut)
async def analyze_one_competitor(
    competitor_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Analyze a competitor with the LLM (name, revenue, users, moats, social,
    features + sample marketing) and store the result. NA where unknown."""
    comp = await _load_competitor(competitor_id, db)
    try:
        analysis = await analyze_competitor(
            name=comp.name, website=comp.website, description=comp.description
        )
    except LLMNotConfigured as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Competitor analysis failed: {e}"
        )
    comp.analysis = analysis
    await db.commit()
    await db.refresh(comp)
    return comp


@router.delete("/competitors/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(competitor_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    comp = await _load_competitor(competitor_id, db)
    await db.delete(comp)
    await db.commit()
