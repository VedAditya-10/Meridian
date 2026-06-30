"""
Purpose: Main entry point for the FastAPI Backend.
Responsibilities:
- Initialize the FastAPI application and OpenAPI specifications.
- Configure Cross-Origin Resource Sharing (CORS) for the frontend dashboard.
- Register application lifespan hooks (startup/shutdown).
- Self-bootstrap the database on first startup (creates tables + seeds data).
- Mount the API routers.
Dependencies: fastapi
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from src.api.endpoints import dashboard, pipeline, store, stores, cameras, zones
from src.core.config import settings
from src.core.database import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)

SCHEMA_MIGRATIONS = [
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS location VARCHAR(255)",
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS address TEXT",
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS phone VARCHAR(50)",
    "ALTER TABLE stores ADD COLUMN IF NOT EXISTS max_cameras INTEGER NOT NULL DEFAULT 6",
    "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS camera_type VARCHAR(50) DEFAULT 'rtsp_stream'",
    "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS video_file_path TEXT",
    "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'inactive'",
    "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS position_index INTEGER",
    "ALTER TABLE cameras ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    "ALTER TABLE zones ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE zones ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
    # Allow nullable RTSP for video_file / webcam cameras (idempotent).
    "ALTER TABLE cameras ALTER COLUMN rtsp_url DROP NOT NULL",
]


async def _run_schema_migrations(conn) -> None:
    for stmt in SCHEMA_MIGRATIONS:
        await conn.execute(text(stmt))


async def _ensure_meridian_store(session) -> None:
    from src.models.store import Store

    result = await session.execute(
        select(Store).where(Store.id == settings.MERIDIAN_STORE_ID).limit(1)
    )
    if result.scalars().first():
        return

    session.add(
        Store(
            id=settings.MERIDIAN_STORE_ID,
            name="My Store",
            timezone="Asia/Kolkata",
            max_cameras=settings.MAX_CAMERAS,
        )
    )
    await session.commit()
    logger.info("Created default Meridian store (%s)", settings.MERIDIAN_STORE_ID)


async def _verify_dependencies() -> dict:
    """Startup checks for Postgres/pgvector and Redis."""
    checks: dict = {"postgres": "unknown", "pgvector": "unknown", "redis": "unknown"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            checks["postgres"] = "ok"
            row = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            checks["pgvector"] = "ok" if row.first() else "missing"
    except Exception as exc:
        checks["postgres"] = f"error: {exc}"
        logger.error("Postgres startup check failed: %s", exc)

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(str(settings.REDIS_URI), decode_responses=True)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        logger.warning("Redis startup check failed (SSE/live pipeline may be degraded): %s", exc)

    return checks


async def _bootstrap_database():
    """
    Self-bootstraps the database on first startup.
    Steps:
      1. Enable the pgvector extension (idempotent).
      2. Create all tables from SQLAlchemy metadata (idempotent via checkfirst=True).
      3. Run additive column migrations.
      4. Ensure the Meridian store row exists.
      5. Seed demo data only if stores table was empty before bootstrap.
    """
    from src.models import Base
    from src.models.store import Store

    logger.info("Running database bootstrap check...")

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension: OK")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _run_schema_migrations(conn)
        logger.info("Database schema: OK")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Store).limit(1))
        was_empty = result.scalars().first() is None

    if was_empty:
        logger.info("Database is empty — running seeder...")
        try:
            from scripts.seed import seed_database

            await seed_database()
            logger.info("Database seeding: COMPLETE")
        except Exception as e:
            logger.error(f"Seeding failed (non-fatal, API will still start): {e}")
    else:
        async with AsyncSessionLocal() as session:
            await _ensure_meridian_store(session)
        logger.info("Database already has data — skipping full seed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.ENVIRONMENT} mode...")
    await _bootstrap_database()
    app.state.startup_checks = await _verify_dependencies()
    yield
    logger.info("Gracefully shutting down backend services...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Meridian — single-store CCTV analytics API.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(store.router, prefix=settings.API_V1_STR)
app.include_router(stores.router, prefix=settings.API_V1_STR)
app.include_router(stores.heatmaps_router, prefix=settings.API_V1_STR)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(pipeline.router, prefix=settings.API_V1_STR)
app.include_router(cameras.router, prefix=settings.API_V1_STR)
app.include_router(zones.router, prefix=settings.API_V1_STR)



@app.get("/health", tags=["System"], status_code=status.HTTP_200_OK)
async def health_check():
    checks = getattr(app.state, "startup_checks", {})
    healthy = checks.get("postgres") == "ok"
    return {
        "status": "healthy" if healthy else "degraded",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0",
        "app": settings.PROJECT_NAME,
        "checks": checks,
    }
