"""
Purpose: Single-store Meridian API (GET/PUT store, clear analytics data).
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.store_context import MERIDIAN_STORE_ID, get_meridian_store
from src.models.daily_store_metric import DailyStoreMetric
from src.models.event import Event
from src.models.store import Camera, Store
from src.models.transaction import Transaction
from src.models.visitor import Visitor, VisitorEmbedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/store", tags=["Meridian Store"])


class CameraSummary(BaseModel):
    id: uuid.UUID
    name: str
    camera_type: str
    status: str
    rtsp_url: Optional[str] = None
    video_file_path: Optional[str] = None
    position_index: Optional[int] = None

    model_config = {"from_attributes": True}


class MeridianStoreResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    timezone: str
    min_engaged_dwell_seconds: int
    max_cameras: int
    cameras: int
    camera_list: List[CameraSummary] = []
    created_at: datetime
    updated_at: datetime


class StoreSettingsUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = Field(None, max_length=1024)
    phone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=255)
    timezone: Optional[str] = Field(None, max_length=50)


class ClearDataRequest(BaseModel):
    confirm: str = Field(..., description='Must be exactly "DELETE"')


def _active_cameras(cameras: List[Camera]) -> List[Camera]:
    return [c for c in cameras if c.deleted_at is None]


def _to_response(store: Store) -> MeridianStoreResponse:
    active = _active_cameras(store.cameras)
    return MeridianStoreResponse(
        id=store.id,
        name=store.name,
        address=store.address,
        phone=store.phone,
        location=store.location,
        timezone=store.timezone,
        min_engaged_dwell_seconds=store.min_engaged_dwell_seconds,
        max_cameras=store.max_cameras,
        cameras=len(active),
        camera_list=[
            CameraSummary(
                id=c.id,
                name=c.name,
                camera_type=c.camera_type,
                status=c.status,
                rtsp_url=c.rtsp_url,
                video_file_path=c.video_file_path,
                position_index=c.position_index,
            )
            for c in active
        ],
        created_at=store.created_at,
        updated_at=store.updated_at,
    )


@router.get("", response_model=MeridianStoreResponse, summary="Get Meridian store")
async def get_store(db: AsyncSession = Depends(get_db)) -> MeridianStoreResponse:
    stmt = (
        select(Store)
        .where(Store.id == MERIDIAN_STORE_ID)
        .options(selectinload(Store.cameras))
    )
    result = await db.execute(stmt)
    store = result.scalars().first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return _to_response(store)


@router.put("", response_model=MeridianStoreResponse, summary="Update store settings")
async def update_store(
    payload: StoreSettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> MeridianStoreResponse:
    store = await get_meridian_store(db, with_cameras=True)
    if payload.name is not None:
        store.name = payload.name
    if payload.address is not None:
        store.address = payload.address
    if payload.phone is not None:
        store.phone = payload.phone
    if payload.location is not None:
        store.location = payload.location
    if payload.timezone is not None:
        store.timezone = payload.timezone
    await db.commit()
    await db.refresh(store)
    return _to_response(store)


@router.delete("/data", summary="Clear all analytics data")
async def clear_store_data(
    payload: ClearDataRequest,
    db: AsyncSession = Depends(get_db),
):
    if payload.confirm != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Confirmation required: set confirm to "DELETE"',
        )

    store_id = MERIDIAN_STORE_ID
    visitor_ids = select(Visitor.id).where(Visitor.store_id == store_id)

    await db.execute(
        delete(VisitorEmbedding).where(VisitorEmbedding.visitor_id.in_(visitor_ids))
    )
    await db.execute(delete(Visitor).where(Visitor.store_id == store_id))
    await db.execute(delete(Event).where(Event.store_id == store_id))
    await db.execute(delete(Transaction).where(Transaction.store_id == store_id))
    await db.execute(delete(DailyStoreMetric).where(DailyStoreMetric.store_id == store_id))
    await db.commit()

    logger.info("Cleared analytics data for Meridian store %s", store_id)
    return {"status": "success", "message": "Analytics data cleared"}


@router.get("/anomalies", summary="Get store anomalies (resolved)")
async def get_store_anomalies_resolved(
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    try:
        from src.services.analytics_service import AnalyticsService
        service = AnalyticsService(db)
        return await service.detect_anomalies(MERIDIAN_STORE_ID)
    except Exception as e:
        logger.error(f"Failed to detect anomalies for store {MERIDIAN_STORE_ID}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during anomaly detection."
        )
