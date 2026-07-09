from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import brands, competitors, content, personas, voice
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="AIMark API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(brands.router, prefix="/api")
app.include_router(personas.router, prefix="/api")
app.include_router(competitors.router, prefix="/api")
app.include_router(content.router, prefix="/api")
app.include_router(voice.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
