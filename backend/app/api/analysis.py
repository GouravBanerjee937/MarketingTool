import io
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.brand import Brand
from app.services import report

router = APIRouter(tags=["analysis"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/brands/{brand_id}/analysis.xlsx")
async def export_analysis(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Serve the brand's Analysis workbook. A brand-new table is built from the
    current DB on EVERY request (fresh Workbook, no reuse of the old file), then
    persisted. No-cache headers ensure the browser never serves a stale copy."""
    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")

    # Always rebuild from scratch, then overwrite the on-disk copy with it.
    data = await report.build_bytes(db, brand_id) or b""
    report.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report.path_for(brand_id).write_bytes(data)

    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", brand.name).strip("_") or "brand"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=_XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="analysis-{safe}.xlsx"',
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )
