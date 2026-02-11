"""
ConectaSEI v2.0 - FastAPI Application

REST API para gestao inteligente de processos SEI com suporte multi-tenant.

Usage:
    uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

Docs:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

from dotenv import load_dotenv
import os

load_dotenv()  # load .env from current working directory (project root)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    logger.info("ConectaSEI v2.0 API starting...")

    # Initialize Firebase Auth
    try:
        from app.core.auth import init_firebase
        init_firebase()
        logger.info("Firebase Auth initialized")
    except Exception as e:
        logger.warning(f"Firebase Auth not available: {e}")

    # Test database connection (async)
    try:
        from app.database.session import async_engine
        from sqlalchemy import text
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connection OK")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

    # Load scraper plugins (register in-memory; not from DB)
    try:
        import app.scrapers  # noqa: F401 - registers built-in scrapers (e.g. SEI 4.2.0)
        from app.scrapers.registry import get_registry
        versions = get_registry().list_versions()
        logger.info(f"Scraper registry: {len(versions)} version(s) — {versions}")
    except Exception as e:
        logger.warning(f"Scraper registry not loaded: {e}")

    # Start APScheduler
    try:
        from app.core.services.scheduler_service import start_scheduler
        start_scheduler()
        logger.info("APScheduler started")
    except Exception as e:
        logger.warning(f"APScheduler not started: {e}")

    logger.info("API ready")
    yield

    # Shutdown
    logger.info("ConectaSEI v2.0 API shutting down...")
    try:
        from app.core.services.scheduler_service import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass


app = FastAPI(
    title="ConectaSEI API",
    description=(
        "REST API para gestao inteligente de processos SEI. "
        "Multi-tenant, multi-version SEI support via plugin system."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS – allow frontend origins (configurable via .env CORS_ORIGINS, comma-separated)
_DEFAULT_CORS = "http://localhost:3000,http://localhost:5173,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:5173,http://127.0.0.1:8080"
_CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_CORS).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def _cors_headers(request: Request) -> dict:
    """Headers so error responses (e.g. 500) still satisfy CORS in the browser."""
    origin = request.headers.get("origin", "")
    if _CORS_ORIGINS and origin in _CORS_ORIGINS:
        return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true"}
    fallback = _CORS_ORIGINS[0] if _CORS_ORIGINS else "http://localhost:3000"
    return {"Access-Control-Allow-Origin": fallback, "Access-Control-Allow-Credentials": "true"}


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} [{response.status_code}] ({process_time:.3f}s)")
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handlers (include CORS headers so browser gets valid response)
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not Found", "message": f"'{request.url.path}' not found"},
        headers=_cors_headers(request),
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": "Check server logs."},
        headers=_cors_headers(request),
    )


@app.exception_handler(Exception)
async def any_exception_handler(request: Request, exc: Exception):
    """Catch-all so unhandled exceptions still return CORS headers."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": "Check server logs."},
        headers=_cors_headers(request),
    )


# Health endpoints
@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "ConectaSEI API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    health = {"status": "healthy", "components": {"api": "ok"}}
    try:
        from app.database.session import async_engine
        from sqlalchemy import text
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health["components"]["database"] = "ok"
    except Exception as e:
        health["status"] = "degraded"
        health["components"]["database"] = f"error: {str(e)}"
    return health


# Register routers
from app.api.routers import auth, institutions, processes, documents, extraction, schedules, pipelines, pipeline_stages, search, admin, orders, webhooks

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(orders.router, tags=["Orders"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(institutions.router, prefix="/institutions", tags=["Institutions"])
app.include_router(processes.router, prefix="/processes", tags=["Processes"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(extraction.router, prefix="", tags=["Extraction"])
app.include_router(schedules.router, prefix="", tags=["Schedules"])
app.include_router(pipelines.router, prefix="/pipelines", tags=["Pipelines"])
app.include_router(pipeline_stages.router, prefix="", tags=["Pipeline Stages"])
app.include_router(search.router, prefix="", tags=["Search"])

logger.info("Routers registered: auth, institutions, processes, documents, extraction, schedules, admin")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000, reload=True)
