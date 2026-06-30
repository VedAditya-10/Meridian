"""
Purpose: Database Seeder for the single Meridian store (cameras + zones).
Usage: docker exec -it si_backend_api python -m scripts.seed
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from src.core.config import settings
from src.core.database import AsyncSessionLocal, engine
from src.models import Base
from src.models.store import Camera, Store, Zone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seeder")

MERIDIAN_STORE = {
    "id": settings.MERIDIAN_STORE_ID,
    "name": "My Store",
    "timezone": "Asia/Kolkata",
    "address": "",
    "phone": "",
    "location": "",
    "cameras": [
        {"name": "Entrance Left", "rtsp_url": "rtsp://192.168.1.10:554/stream1"},
        {"name": "Entrance Right", "rtsp_url": "rtsp://192.168.1.11:554/stream1"},
        {"name": "Outside Area", "rtsp_url": "rtsp://192.168.1.12:554/stream1"},
        {"name": "Storage Room", "rtsp_url": "rtsp://192.168.1.13:554/stream1"},
        {"name": "Billing Counter", "rtsp_url": "rtsp://192.168.1.14:554/stream1"},
    ],
    "zones": [
        {
            "name": "Store Entrance",
            "zone_type": "ENTRY_LINE",
            "polygon": {
                "camera_ids": ["cam-1", "cam-2"],
                "points": [
                    {"x": 0.0, "y": 0.60},
                    {"x": 1.0, "y": 0.60},
                    {"x": 1.0, "y": 1.0},
                    {"x": 0.0, "y": 1.0},
                ],
            },
        },
        {
            "name": "Products Display",
            "zone_type": "DISPLAY",
            "polygon": {
                "camera_ids": ["cam-1", "cam-2"],
                "points": [
                    {"x": 0.10, "y": 0.15},
                    {"x": 0.90, "y": 0.15},
                    {"x": 0.90, "y": 0.62},
                    {"x": 0.10, "y": 0.62},
                ],
            },
        },
        {
            "name": "Outside Approach",
            "zone_type": "AISLE",
            "polygon": {
                "camera_ids": ["cam-3"],
                "points": [
                    {"x": 0.0, "y": 0.0},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                    {"x": 0.0, "y": 1.0},
                ],
            },
        },
        {
            "name": "Storage Room",
            "zone_type": "AISLE",
            "polygon": {
                "camera_ids": ["cam-4"],
                "points": [
                    {"x": 0.0, "y": 0.0},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                    {"x": 0.0, "y": 1.0},
                ],
            },
        },
        {
            "name": "Billing Counter",
            "zone_type": "QUEUE",
            "polygon": {
                "camera_ids": ["cam-5"],
                "points": [
                    {"x": 0.10, "y": 0.45},
                    {"x": 0.90, "y": 0.45},
                    {"x": 0.90, "y": 1.0},
                    {"x": 0.10, "y": 1.0},
                ],
            },
        },
    ],
}


async def seed_database():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE stores ADD COLUMN IF NOT EXISTS location VARCHAR(255)"))
        await conn.execute(text("ALTER TABLE stores ADD COLUMN IF NOT EXISTS address TEXT"))
        await conn.execute(text("ALTER TABLE stores ADD COLUMN IF NOT EXISTS phone VARCHAR(50)"))
        await conn.execute(text("ALTER TABLE stores ADD COLUMN IF NOT EXISTS max_cameras INTEGER NOT NULL DEFAULT 6"))
        logger.info("Database tables ready.")

    store_def = MERIDIAN_STORE
    store_id = store_def["id"]

    async with AsyncSessionLocal() as session:
        async with session.begin():
            store = Store(
                id=store_id,
                name=store_def["name"],
                timezone=store_def["timezone"],
                address=store_def.get("address"),
                phone=store_def.get("phone"),
                location=store_def.get("location"),
                max_cameras=settings.MAX_CAMERAS,
            )
            session.add(store)
            logger.info("Seeding Meridian store: %s", store_def["name"])

            for idx, cam_def in enumerate(store_def["cameras"], start=1):
                session.add(
                    Camera(
                        store_id=store_id,
                        name=cam_def["name"],
                        camera_type="rtsp_stream",
                        rtsp_url=cam_def["rtsp_url"],
                        status="inactive",
                        position_index=idx,
                    )
                )

            for zone_def in store_def["zones"]:
                session.add(
                    Zone(
                        id=uuid.uuid4(),
                        store_id=store_id,
                        name=zone_def["name"],
                        zone_type=zone_def["zone_type"],
                        polygon=zone_def["polygon"],
                        is_active=True,
                    )
                )

    logger.info("Meridian seed complete. Store ID: %s", store_id)


if __name__ == "__main__":
    asyncio.run(seed_database())
