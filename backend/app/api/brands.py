import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.brand import Brand
from app.schemas.brand import BrandCreate, BrandOut, BrandUpdate
from app.services import report

router = APIRouter(prefix="/brands", tags=["brands"])


async def _get_or_404(brand_id: uuid.UUID, db: AsyncSession) -> Brand:
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.get("", response_model=list[BrandOut])
async def list_brands(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Brand).order_by(Brand.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
async def create_brand(payload: BrandCreate, db: AsyncSession = Depends(get_db)):
    brand = Brand(**payload.model_dump())
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    await report.refresh(db, brand.id)  # start the report from stage 1
    return brand


@router.get("/{brand_id}", response_model=BrandOut)
async def get_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_or_404(brand_id, db)


@router.patch("/{brand_id}", response_model=BrandOut)
async def update_brand(
    brand_id: uuid.UUID, payload: BrandUpdate, db: AsyncSession = Depends(get_db)
):
    brand = await _get_or_404(brand_id, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(brand, field, value)
    await db.commit()
    await db.refresh(brand)
    await report.refresh(db, brand.id)
    return brand


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    brand = await _get_or_404(brand_id, db)
    await db.delete(brand)
    await db.commit()
