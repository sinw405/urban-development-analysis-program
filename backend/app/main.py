from contextlib import asynccontextmanager
import logging
import os
import re
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyses import router as analyses_router
from app.api.analyze import router as analyze_router
from app.api.cases import router as cases_router
from app.api.health import router as health_router
from app.api.laws import router as laws_router
from app.api.law_updates import router as law_updates_router
from app.api.legal_references import router as legal_references_router
from app.api.legal_retrieval import router as legal_retrieval_router
from app.core.config import get_settings
from app.core.observability import bind_correlation_id, configure_logging, log_event, reset_correlation_id
from app.services.law_update_scheduler_runtime import start_law_update_scheduler, shutdown_law_update_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_law_update_scheduler()
    try:
        yield
    finally:
        shutdown_law_update_scheduler()


configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

app = FastAPI(
    lifespan=lifespan,
    title="Urban Development Analysis API",
    version="0.3.0",
    description="Rule-based urban development project analysis API with migrations and DB persistence.",
)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request_id = supplied if _SAFE_REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
    token = bind_correlation_id(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        category = "normal" if response.status_code < 400 else "client_error" if response.status_code < 500 else "server_error"
        log_event(logger, logging.INFO if response.status_code < 500 else logging.ERROR, "http.request.completed",
                  method=request.method, path=request.url.path, status_code=response.status_code,
                  duration_ms=duration_ms, error_category=category)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as exc:
        log_event(logger, logging.ERROR, "http.request.unhandled_exception", method=request.method,
                  path=request.url.path, duration_ms=round((time.perf_counter() - started) * 1000, 3),
                  error_category=exc.__class__.__name__, exc_info=True)
        raise
    finally:
        reset_correlation_id(token)


@app.exception_handler(RequestValidationError)
async def monitored_validation_error(request: Request, exc: RequestValidationError):
    log_event(logger, logging.WARNING, "http.request.validation_error", method=request.method,
              path=request.url.path, status_code=422, error_category="validation_error")
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(HTTPException)
async def monitored_http_error(request: Request, exc: HTTPException):
    log_event(logger, logging.WARNING if exc.status_code < 500 else logging.ERROR, "http.request.expected_error",
              method=request.method, path=request.url.path, status_code=exc.status_code,
              error_category="client_error" if exc.status_code < 500 else "server_error")
    return await http_exception_handler(request, exc)

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
app.include_router(cases_router, prefix="/api")
app.include_router(analyses_router, prefix="/api")
app.include_router(laws_router, prefix="/api")
app.include_router(law_updates_router, prefix="/api")
app.include_router(legal_references_router, prefix="/api")
app.include_router(legal_retrieval_router, prefix="/api")
