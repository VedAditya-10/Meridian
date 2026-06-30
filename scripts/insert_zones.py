#!/usr/bin/env python3
"""
Insert corrected zones for the NYC Flagship store.
Run inside si_postgres container:
  docker exec si_postgres python /tmp/insert_zones.py
"""
import subprocess, json, sys

STORE_ID = "a1b2c3d4-0001-4000-8000-000000000001"

zones = [
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
            # cam-5: customer-facing side of the counter — opposite the operator's laptop.
            # Feet landing in the lower 55% of the frame (y >= 0.45) are "at the counter".
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

for z in zones:
    poly_json = json.dumps(z["polygon"]).replace("'", "''")
    sql = (
        "INSERT INTO zones (id, store_id, name, zone_type, polygon, created_at, updated_at) "
        f"VALUES (gen_random_uuid(), '{STORE_ID}', '{z['name']}', '{z['zone_type']}', "
        f"'{poly_json}'::jsonb, NOW(), NOW());"
    )
    result = subprocess.run(
        ["psql", "-U", "postgres", "-d", "store_intelligence", "-c", sql],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR inserting {z['name']}: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"  OK: {z['name']}")

print("All zones inserted successfully.")
