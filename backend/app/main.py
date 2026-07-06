from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.analyses import router as analyses_router
from app.api.analyze import router as analyze_router
from app.api.health import router as health_router
from app.core.database import create_db_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_tables()
    yield


app = FastAPI(
    title="Urban Development Analysis API",
    version="0.2.0",
    description="Rule-based urban development project analysis API with DB persistence.",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(analyze_router, prefix="/api")
app.include_router(analyses_router, prefix="/api")
