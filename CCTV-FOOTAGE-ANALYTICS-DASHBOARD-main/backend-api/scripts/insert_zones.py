"""
Zone insertion script — run inside the si_backend_api container.
Usage: docker exec si_backend_api python -m scripts.insert_zones
"""
import asyncio, json, uuid
from sqlalchemy import text
from src.core.database import AsyncSessionLocal


STORE_ID = uuid.UUID("a1b2c3d4-0001-4000-8000-000000000001")

ZONES = [
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
            # cam-5: customer-facing side of counter — lower portion of frame (y >= 0.45)
            # The operator's laptop sits in the upper half; customers approach from below.
            "camera_ids": ["cam-5"],
            "points": [
                {"x": 0.10, "y": 0.45},
                {"x": 0.90, "y": 0.45},
                {"x": 0.90, "y": 1.0},
                {"x": 0.10, "y": 1.0},
            ],
        },
    },
]


async def main():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for z in ZONES:
                await session.execute(
                    text(
                        "INSERT INTO zones (id, store_id, name, zone_type, polygon, created_at, updated_at) "
                        "VALUES (gen_random_uuid(), :store_id, :name, :zone_type, CAST(:polygon AS jsonb), NOW(), NOW())"
                    ),
                    {
                        "store_id": str(STORE_ID),
                        "name": z["name"],
                        "zone_type": z["zone_type"],
                        "polygon": json.dumps(z["polygon"]),
                    },
                )
                print(f"  Inserted: {z['name']}")
    print("Done — all zones inserted.")


if __name__ == "__main__":
    asyncio.run(main())
