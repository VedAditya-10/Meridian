"""
Purpose: FastAPI endpoints for Camera Zone configuration.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.store_context import MERIDIAN_STORE_ID
from src.models.store import Zone, Camera

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Camera Zones"])


class PointSchema(BaseModel):
    x: float
    y: float


class ZonePolygonSchema(BaseModel):
    camera_ids: List[str]
    points: List[PointSchema]


class ZoneResponse(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    zone_type: str
    polygon: ZonePolygonSchema
    product_category: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ZoneCreate(BaseModel):
    name: str = Field(..., max_length=255)
    zone_type: str = Field(..., description="ENTRY_LINE | DISPLAY | AISLE | QUEUE")
    points: List[PointSchema]
    product_category: Optional[str] = Field(None, max_length=100)


class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    points: Optional[List[PointSchema]] = None
    product_category: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


@router.get("/cameras/{camera_id}/zones", response_model=List[ZoneResponse], summary="Get active zones for a camera")
async def get_camera_zones(
    camera_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> List[Zone]:
    # Ensure camera exists and is active
    camera_stmt = select(Camera).where(
        and_(
            Camera.id == camera_id,
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.deleted_at.is_(None)
        )
    )
    camera_result = await db.execute(camera_stmt)
    if not camera_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found or is inactive."
        )

    # Get all active zones
    stmt = select(Zone).where(
        and_(
            Zone.store_id == MERIDIAN_STORE_ID,
            Zone.is_active == True,
            Zone.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    zones = result.scalars().all()

    # Filter in Python to match camera_id strings
    camera_zones = []
    cam_str = str(camera_id)
    for z in zones:
        cids = z.polygon.get("camera_ids", []) if isinstance(z.polygon, dict) else []
        if cam_str in [str(cid) for cid in cids]:
            camera_zones.append(z)

    return camera_zones


@router.post("/cameras/{camera_id}/zones", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED, summary="Create a zone for a camera")
async def create_camera_zone(
    camera_id: uuid.UUID,
    payload: ZoneCreate,
    db: AsyncSession = Depends(get_db)
) -> Zone:
    # 1. Verify camera exists
    camera_stmt = select(Camera).where(
        and_(
            Camera.id == camera_id,
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.deleted_at.is_(None)
        )
    )
    camera_result = await db.execute(camera_stmt)
    if not camera_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found."
        )

    # 2. Validate geometry
    if len(payload.points) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Polygon requires at least 3 points."
        )

    # 3. Check name uniqueness on this camera
    active_stmt = select(Zone).where(
        and_(
            Zone.store_id == MERIDIAN_STORE_ID,
            Zone.name == payload.name,
            Zone.is_active == True,
            Zone.deleted_at.is_(None)
        )
    )
    active_res = await db.execute(active_stmt)
    active_zones = active_res.scalars().all()
    
    cam_str = str(camera_id)
    for z in active_zones:
        cids = z.polygon.get("camera_ids", []) if isinstance(z.polygon, dict) else []
        if cam_str in [str(cid) for cid in cids]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A zone with the name '{payload.name}' already exists on this camera feed."
            )

    polygon_data = {
        "camera_ids": [cam_str],
        "points": [{"x": pt.x, "y": pt.y} for pt in payload.points]
    }

    zone = Zone(
        id=uuid.uuid4(),
        store_id=MERIDIAN_STORE_ID,
        name=payload.name,
        zone_type=payload.zone_type,
        polygon=polygon_data,
        product_category=payload.product_category,
        is_active=True,
    )
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return zone


@router.put("/zones/{id}", response_model=ZoneResponse, summary="Update a zone")
async def update_zone(
    id: uuid.UUID,
    payload: ZoneUpdate,
    db: AsyncSession = Depends(get_db)
) -> Zone:
    stmt = select(Zone).where(
        and_(
            Zone.id == id,
            Zone.store_id == MERIDIAN_STORE_ID,
            Zone.is_active == True,
            Zone.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found."
        )

    # Validate name uniqueness if changed
    if payload.name is not None and payload.name != zone.name:
        active_stmt = select(Zone).where(
            and_(
                Zone.store_id == MERIDIAN_STORE_ID,
                Zone.name == payload.name,
                Zone.is_active == True,
                Zone.deleted_at.is_(None)
            )
        )
        active_res = await db.execute(active_stmt)
        active_zones = active_res.scalars().all()
        
        # Check if they share any camera_ids
        zone_cids = zone.polygon.get("camera_ids", []) if isinstance(zone.polygon, dict) else []
        for az in active_zones:
            az_cids = az.polygon.get("camera_ids", []) if isinstance(az.polygon, dict) else []
            intersection = set(zone_cids).intersection(set(az_cids))
            if intersection:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A zone with the name '{payload.name}' already exists on camera feeds: {list(intersection)}"
                )
        zone.name = payload.name

    if payload.points is not None:
        if len(payload.points) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Polygon requires at least 3 points."
            )
        camera_ids = zone.polygon.get("camera_ids", []) if isinstance(zone.polygon, dict) else []
        zone.polygon = {
            "camera_ids": camera_ids,
            "points": [{"x": pt.x, "y": pt.y} for pt in payload.points]
        }

    if payload.product_category is not None:
        zone.product_category = payload.product_category

    if payload.is_active is not None:
        zone.is_active = payload.is_active

    zone.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(zone)
    return zone


@router.delete("/zones/{id}", summary="Soft delete a zone")
async def delete_zone(id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Zone).where(
        and_(
            Zone.id == id,
            Zone.store_id == MERIDIAN_STORE_ID,
            Zone.is_active == True,
            Zone.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    zone = result.scalars().first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found."
        )

    zone.is_active = False
    zone.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info(f"Soft deleted zone {id}")
    return {"status": "success", "message": "Zone soft deleted successfully"}
