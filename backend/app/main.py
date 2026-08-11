from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyses import router as analyses_router
from app.api.analyze import router as analyze_router
from app.api.health import router as health_router
from app.api.laws import router as laws_router
from app.api.law_updates import router as law_updates_router
from app.api.legal_references import router as legal_references_router
from app.api.legal_retrieval import router as legal_retrieval_router
from app.core.config import get_settings
from app.services.law_update_scheduler_runtime import start_law_update_scheduler, shutdown_law_update_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_law_update_scheduler()
    try:
        yield
    finally:
        shutdown_law_update_scheduler()


app = FastAPI(
    lifespan=lifespan,
    title="Urban Development Analysis API",
    version="0.3.0",
    description="Rule-based urban development project analysis API with migrations and DB persistence.",
)

settings = get_settings()
if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(analyze_router, prefix="/api")
app.include_router(analyses_router, prefix="/api")
app.include_router(laws_router, prefix="/api")
app.include_router(law_updates_router, prefix="/api")
app.include_router(legal_references_router, prefix="/api")
app.include_router(legal_retrieval_router, prefix="/api")