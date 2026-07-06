from fastapi import FastAPI

from app.api.analyze import router as analyze_router
from app.api.health import router as health_router


app = FastAPI(
    title="Urban Development Analysis API",
    version="0.1.0",
    description="Phase 0 MVP API for rule-based urban development project analysis.",
)

app.include_router(health_router)
app.include_router(analyze_router, prefix="/api")
