"""
Purpose: FastAPI REST endpoints for Store Analytics.
Responsibilities:
- Define the HTTP routing schema for `/stores/{id}/*`.
- Inject the asynchronous database session securely.
- Handle HTTP exceptions, error logging, and input validation.
- Delegate complex database aggregations to the `AnalyticsService`.
Dependencies: fastapi, sqlalchemy
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from src.core.database import get_db
from src.core.store_context import MERIDIAN_STORE_ID
from src.models.store import Store, Camera, Zone
from src.schemas.event import (
    AnalyticsFunnelResponse,
    AnalyticsHeatmapResponse,
    AnalyticsMetricsResponse,
)
from src.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stores", tags=["Store Analytics"])


@router.get(
    "/{store_id}/metrics",
    response_model=AnalyticsMetricsResponse,
    summary="Get Store KPIs",
    description="Returns high-level conversion, total entries, and live occupancy."
)
async def get_store_metrics(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> AnalyticsMetricsResponse:
    """
    Fetches the primary Key Performance Indicators for the dashboard.
    """
    store_id = MERIDIAN_STORE_ID
    try:
        service = AnalyticsService(db)
        return await service.get_daily_metrics(store_id)
    except ValueError as ve:
        # Handle specific domain errors (e.g., Store ID not found)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to fetch metrics for store {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during metric aggregation."
        )


@router.get(
    "/{store_id}/funnel",
    response_model=AnalyticsFunnelResponse,
    summary="Get Conversion Funnel",
    description="Returns the step-by-step visitor drop-off rate (Entry -> Dwell -> Checkout)."
)
async def get_store_funnel(
    store_id: uuid.UUID,
    start_time: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=1),
        description="Defaults to the last 24 hours"
    ),
    end_time: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc)
    ),
    db: AsyncSession = Depends(get_db)
) -> AnalyticsFunnelResponse:
    """
    Calculates the conversion funnel. Time windows are required via Query params 
    because funnels are highly sensitive to the temporal context (morning vs evening).
    """
    store_id = MERIDIAN_STORE_ID
    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="start_time must be strictly before end_time."
        )

    try:
        service = AnalyticsService(db)
        return await service.calculate_funnel(store_id, start_time, end_time)
    except Exception as e:
        logger.error(f"Failed to calculate funnel for store {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during funnel aggregation."
        )


@router.get(
    "/{store_id}/heatmap",
    response_model=AnalyticsHeatmapResponse,
    summary="Get Zone Popularity Heatmap",
    description="Returns normalized dwell time density across all store zones."
)
async def get_store_heatmap(
    store_id: uuid.UUID,
    start_time: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(hours=1),
        description="Defaults to the last 1 hour for immediate heat trends"
    ),
    end_time: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc)
    ),
    db: AsyncSession = Depends(get_db)
) -> AnalyticsHeatmapResponse:
    """
    Aggregates ZONE_DWELL events per zone and normalizes them into a 0.0-1.0 density score
    used by the frontend canvas overlay to render the heatmap.
    """
    store_id = MERIDIAN_STORE_ID
    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="start_time must be strictly before end_time."
        )

    try:
        service = AnalyticsService(db)
        return await service.calculate_heatmap(store_id, start_time, end_time)
    except Exception as e:
        logger.error(f"Failed to calculate heatmap for store {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during heatmap aggregation."
        )


@router.get(
    "/{store_id}/anomalies",
    summary="Get Store Anomalies",
    description="Detects dead camera feeds, queue spikes, or sudden conversion drops."
)
async def get_store_anomalies(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """
    Queries the anomaly detection engine heuristics.
    """
    store_id = MERIDIAN_STORE_ID
    try:
        service = AnalyticsService(db)
        return await service.detect_anomalies(store_id)
    except Exception as e:
        logger.error(f"Failed to detect anomalies for store {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during anomaly detection."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Store Onboarding / Management API schemas & endpoints
# ─────────────────────────────────────────────────────────────────────────────

class PointSchema(BaseModel):
    x: float
    y: float

class ZonePolygonSchema(BaseModel):
    camera_ids: Optional[List[str]] = None
    points: List[PointSchema]

class ZoneCreateSchema(BaseModel):
    name: str
    zone_type: str  # e.g., ENTRY_LINE, DISPLAY, AISLE, QUEUE
    polygon: ZonePolygonSchema
    product_category: Optional[str] = None

class CameraCreateSchema(BaseModel):
    name: str
    rtsp_url: str

class StoreCreateSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    name: str
    timezone: str
    location: str
    cameras: List[CameraCreateSchema]
    zones: List[ZoneCreateSchema]

class StoreListResponse(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    location: Optional[str] = None
    cameras: int


class CameraDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    rtsp_url: str


class ZoneDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    zone_type: str
    polygon: dict
    product_category: Optional[str] = None


class StoreDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    location: Optional[str] = None
    min_engaged_dwell_seconds: int
    cameras: List[CameraDetailResponse]
    zones: List[ZoneDetailResponse]


class ZoneUpdateSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    name: str
    zone_type: str
    polygon: ZonePolygonSchema
    product_category: Optional[str] = None


class StoreZonesUpdatePayload(BaseModel):
    zones: List[ZoneUpdateSchema]


@router.get(
    "",
    response_model=List[StoreListResponse],
    summary="List all stores",
    description="Returns all registered stores with camera counts."
)
async def list_stores(
    db: AsyncSession = Depends(get_db)
):
    try:
        stmt = (
            select(Store)
            .where(Store.id == MERIDIAN_STORE_ID)
            .options(selectinload(Store.cameras))
        )
        result = await db.execute(stmt)
        stores = result.scalars().all()
        
        return [
            StoreListResponse(
                id=s.id,
                name=s.name,
                timezone=s.timezone,
                location=s.location,
                cameras=len([c for c in s.cameras if c.deleted_at is None])
            )
            for s in stores
        ]
    except Exception as e:
        logger.error(f"Failed to list stores: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list stores"
        )


@router.post(
    "",
    status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
    summary="Create store (disabled)",
    description="Meridian is single-store. Use PUT /api/v1/store to update settings.",
)
async def create_store(
    payload: StoreCreateSchema,
    db: AsyncSession = Depends(get_db),
):
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Meridian supports a single store. Use PUT /api/v1/store to update settings.",
    )


@router.get(
    "/{store_id}",
    response_model=StoreDetailResponse,
    summary="Get detailed store configuration",
    description="Returns full metadata, camera list, and zone coordinates for a store."
)
async def get_store(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> StoreDetailResponse:
    store_id = MERIDIAN_STORE_ID
    try:
        stmt = (
            select(Store)
            .options(selectinload(Store.cameras), selectinload(Store.zones))
            .where(Store.id == store_id)
        )
        result = await db.execute(stmt)
        store = result.scalars().first()
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found"
            )
        return StoreDetailResponse(
            id=store.id,
            name=store.name,
            timezone=store.timezone,
            location=store.location,
            min_engaged_dwell_seconds=store.min_engaged_dwell_seconds,
            cameras=[
                CameraDetailResponse(id=c.id, name=c.name, rtsp_url=c.rtsp_url)
                for c in store.cameras
            ],
            zones=[
                ZoneDetailResponse(
                    id=z.id,
                    name=z.name,
                    zone_type=z.zone_type,
                    polygon=z.polygon,
                    product_category=z.product_category
                )
                for z in store.zones
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch store details for {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.put(
    "/{store_id}/zones",
    summary="Batch update zones for a store",
    description="Updates existing zones, creates new ones, and removes deleted ones."
)
async def update_store_zones(
    store_id: uuid.UUID,
    payload: StoreZonesUpdatePayload,
    db: AsyncSession = Depends(get_db)
):
    store_id = MERIDIAN_STORE_ID
    try:
        store = await db.get(Store, store_id)
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found"
            )

        stmt = select(Zone).where(Zone.store_id == store_id)
        result = await db.execute(stmt)
        existing_zones = {z.id: z for z in result.scalars().all()}
        
        updated_ids = set()
        
        for zone_input in payload.zones:
            if zone_input.id and zone_input.id in existing_zones:
                db_zone = existing_zones[zone_input.id]
                db_zone.name = zone_input.name
                db_zone.zone_type = zone_input.zone_type
                db_zone.polygon = zone_input.polygon.model_dump()
                db_zone.product_category = zone_input.product_category
                updated_ids.add(db_zone.id)
            else:
                new_id = zone_input.id or uuid.uuid4()
                db_zone = Zone(
                    id=new_id,
                    store_id=store_id,
                    name=zone_input.name,
                    zone_type=zone_input.zone_type,
                    polygon=zone_input.polygon.model_dump(),
                    product_category=zone_input.product_category
                )
                db.add(db_zone)
                updated_ids.add(new_id)
                
        for zid, db_zone in existing_zones.items():
            if zid not in updated_ids:
                await db.delete(db_zone)
                
        await db.commit()
        return {"status": "success", "updated_count": len(updated_ids)}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to batch update zones for store {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update zones: {str(e)}"
        )

# ─────────────────────────────────────────────────────────────────────────────
# New Schemas for Webhook, Zone Update, and Section Performance
# ─────────────────────────────────────────────────────────────────────────────
from datetime import date
from src.models.event import Event
from src.models.transaction import Transaction

class TransactionWebhookPayload(BaseModel):
    order_time: datetime
    gmv: float
    qty: int
    product_category: Optional[str] = None
    product_name: Optional[str] = None

class ZoneUpdatePayload(BaseModel):
    coordinates: List[List[float]]
    product_category: Optional[str] = None

class SectionPerformanceItem(BaseModel):
    productCategory: str
    totalGmv: float
    dwellDensityPercent: float
    dwellCount: int


# ─────────────────────────────────────────────────────────────────────────────
# Webhook and Zone Update Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{store_id}/transactions/webhook")
async def ingest_transaction(
    store_id: uuid.UUID,
    payload: TransactionWebhookPayload,
    db: AsyncSession = Depends(get_db)
):
    store_id = MERIDIAN_STORE_ID
    # Step 1: Create transaction record
    transaction = Transaction(
        id=uuid.uuid4(),
        order_id=f"TXN-{uuid.uuid4().hex[:8].upper()}",
        store_id=store_id,
        order_time=payload.order_time,
        gmv=payload.gmv,
        qty=payload.qty,
        product_category=payload.product_category,
        product_name=payload.product_name,
        is_visitor_matched=False,
        match_confidence=None
    )
    db.add(transaction)
    await db.flush()

    window_start = payload.order_time - timedelta(minutes=5)

    # Step 2: Find BILLING_QUEUE_JOIN candidates
    candidates_result = await db.execute(
        select(Event)
        .where(
            Event.store_id == store_id,
            Event.event_type == "BILLING_QUEUE_JOIN",
            Event.cancelled == False,
            Event.timestamp.between(window_start, payload.order_time)
        )
        .order_by(Event.timestamp.desc())
    )
    candidates = candidates_result.scalars().all()

    if not candidates:
        await db.commit()
        return {"matched": False, "confidence": None}

    # Step 3: Exclude already-matched visitors in this window WITH a row lock
    already_matched_result = await db.execute(
        select(Transaction.visitor_id)
        .where(
            Transaction.store_id == store_id,
            Transaction.order_time.between(window_start, payload.order_time),
            Transaction.is_visitor_matched == True,
            Transaction.id != transaction.id
        )
        .with_for_update(skip_locked=True)
    )
    already_matched_ids = {row[0] for row in already_matched_result if row[0] is not None}

    unmatched = [c for c in candidates if c.visitor_id not in already_matched_ids]

    if not unmatched:
        await db.commit()
        return {"matched": False, "confidence": None}

    # Step 4: Check billing zone presence via most recent zone event (active in queue)
    active_in_billing = []
    for candidate in unmatched:
        latest_event = await db.scalar(
            select(Event)
            .where(
                Event.visitor_id == candidate.visitor_id,
                Event.event_type.in_(["ZONE_ENTER", "ZONE_EXIT", "EXIT"]),
                Event.cancelled == False,
                Event.timestamp <= payload.order_time
            )
            .order_by(Event.timestamp.desc())
        )
        if (latest_event
                and latest_event.event_type == "ZONE_ENTER"
                and latest_event.metadata_payload.get("zone_name") == "billing"):
            active_in_billing.append(candidate)

    # Step 5: Assign confidence and pick winner
    if len(active_in_billing) == 1:
        winner, confidence = active_in_billing[0], "high"
    elif len(active_in_billing) > 1:
        winner, confidence = active_in_billing[0], "medium"  # most recent first
    elif len(unmatched) == 1:
        winner, confidence = unmatched[0], "medium"
    else:
        winner, confidence = unmatched[0], "low"

    # Step 6: Commit match
    transaction.visitor_id = winner.visitor_id
    transaction.is_visitor_matched = True
    transaction.match_confidence = confidence
    await db.commit()

    return {
        "matched": True,
        "confidence": confidence,
        "visitor_id": str(winner.visitor_id)
    }


@router.put("/{store_id}/zones/{zone_id}")
async def update_zone(
    store_id: uuid.UUID,
    zone_id: uuid.UUID,
    payload: ZoneUpdatePayload,
    db: AsyncSession = Depends(get_db)
):
    store_id = MERIDIAN_STORE_ID
    from shapely.geometry import Polygon as ShapelyPolygon

    # Validate geometry
    if len(payload.coordinates) < 3:
        raise HTTPException(400, "Polygon requires at least 3 points")

    poly = ShapelyPolygon(payload.coordinates)

    if not poly.is_valid:
        raise HTTPException(400, "Invalid polygon geometry (self-intersecting or degenerate)")

    if poly.area == 0:
        raise HTTPException(400, "Polygon has zero area")

    zone = await db.scalar(
        select(Zone)
        .where(Zone.id == zone_id, Zone.store_id == store_id)
    )

    if not zone:
        raise HTTPException(404, "Zone not found")

    # Maintain structured dictionary points format expected by Event Engine State Machine
    db_polygon = {
        "points": [{"x": float(pt[0]), "y": float(pt[1])} for pt in payload.coordinates]
    }
    # Preserve existing camera_ids filter if present
    if isinstance(zone.polygon, dict) and "camera_ids" in zone.polygon:
        db_polygon["camera_ids"] = zone.polygon["camera_ids"]

    zone.polygon = db_polygon
    if payload.product_category is not None:
        zone.product_category = payload.product_category

    await db.commit()
    return {"updated": True, "zone_id": str(zone_id)}


@router.get(
    "/{store_id}/section-performance",
    response_model=List[SectionPerformanceItem],
    summary="Get Section Performance Metrics",
    description="Returns total GMV, dwell density percent, and dwell counts by product category."
)
async def get_section_performance(
    store_id: uuid.UUID,
    date: date = Query(..., description="Query date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db)
):
    store_id = MERIDIAN_STORE_ID
    # Fetch store to get local timezone
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(404, "Store not found")
        
    tz_name = store.timezone or "Asia/Kolkata"
    
    # 1. Total store ZONE_DWELL count on this date in store timezone
    total_dwells_stmt = select(func.count(Event.id)).where(
        Event.store_id == store_id,
        Event.event_type == "ZONE_DWELL",
        Event.cancelled == False,
        func.date(func.timezone(tz_name, Event.timestamp)) == date
    )
    total_dwells = await db.scalar(total_dwells_stmt) or 0
    
    # 2. Query ZONE_DWELL count grouped by product_category (using Zone model category join)
    dwells_by_cat_stmt = (
        select(Zone.product_category, func.count(Event.id))
        .join(Event, Event.zone_id == Zone.id)
        .where(
            Zone.store_id == store_id,
            Event.event_type == "ZONE_DWELL",
            Event.cancelled == False,
            func.date(func.timezone(tz_name, Event.timestamp)) == date,
            Zone.product_category.isnot(None)
        )
        .group_by(Zone.product_category)
    )
    dwells_res = await db.execute(dwells_by_cat_stmt)
    dwell_counts = {row[0]: row[1] for row in dwells_res.all()}
    
    # 3. Query GMV grouped by product_category from transactions on this date in store timezone
    gmv_by_cat_stmt = (
        select(Transaction.product_category, func.sum(Transaction.gmv))
        .where(
            Transaction.store_id == store_id,
            func.date(func.timezone(tz_name, Transaction.order_time)) == date,
            Transaction.product_category.isnot(None)
        )
        .group_by(Transaction.product_category)
    )
    gmv_res = await db.execute(gmv_by_cat_stmt)
    gmv_sums = {row[0]: float(row[1]) for row in gmv_res.all()}
    
    # Combine results
    all_categories = set(dwell_counts.keys()).union(gmv_sums.keys())
    
    results = []
    for cat in all_categories:
        d_count = dwell_counts.get(cat, 0)
        gmv_val = gmv_sums.get(cat, 0.0)
        density = (d_count / total_dwells * 100.0) if total_dwells > 0 else 0.0
        
        results.append(
            SectionPerformanceItem(
                productCategory=cat,
                totalGmv=round(gmv_val, 2),
                dwellDensityPercent=round(density, 1),
                dwellCount=d_count
            )
        )
        
    return results


heatmaps_router = APIRouter(prefix="/heatmaps", tags=["Heatmaps"])

@heatmaps_router.get(
    "/zones",
    response_model=AnalyticsHeatmapResponse,
    summary="Get Zone Popularity Heatmap (resolved)",
    description="Returns normalized dwell time density across all store zones."
)
async def get_store_heatmap_resolved(
    start_time: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(hours=1),
        description="Defaults to the last 1 hour for immediate heat trends"
    ),
    end_time: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc)
    ),
    db: AsyncSession = Depends(get_db)
) -> AnalyticsHeatmapResponse:
    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="start_time must be strictly before end_time."
        )

    try:
        service = AnalyticsService(db)
        return await service.calculate_heatmap(MERIDIAN_STORE_ID, start_time, end_time)
    except Exception as e:
        logger.error(f"Failed to calculate heatmap for store {MERIDIAN_STORE_ID}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during heatmap aggregation."
        )
