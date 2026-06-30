import logging
import uuid
from typing import List, Optional
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.store_context import MERIDIAN_STORE_ID
from src.models.event import Event, EventType
from src.models.visitor import Visitor
from src.models.transaction import Transaction
from src.models.daily_store_metric import DailyStoreMetric
from src.schemas.event import AnalyticsFunnelResponse
from fastapi.responses import StreamingResponse
import redis.asyncio as redis
import os
import asyncio
import json
from datetime import timedelta, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

from src.models.store import Store
from src.services.analytics_service import AnalyticsService

class DashboardMetricsResponse(BaseModel):
    footfall: int
    uniqueVisitors: int
    transactions: int
    gmv: float
    conversionRate: float
    averageBasketValue: float
    total_exits: int = 0
    active_visitor_count: int = 0
    
    # New metrics
    totalFootfall: int
    engagedVisitors: int
    verifiedConversionRate: float
    estimatedConversionRate: float
    queueAbandonmentRate: float
    avgDwellMinutes: float


class DailyTrendResponse(BaseModel):
    metric_date: date
    footfall: int
    unique_visitors: int
    transactions: int
    gmv: float
    conversion_rate: float
    average_basket_value: float


@router.get("/store/{store_id}", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    store_id: uuid.UUID,
    date: Optional[date] = Query(None, description="Query date (defaults to local store today)"),
    db: AsyncSession = Depends(get_db)
):
    try:
        # Fetch store configuration
        store = await db.get(Store, store_id)
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")

        import zoneinfo
        from datetime import timezone as dt_timezone
        from sqlalchemy import cast, Integer, Float

        try:
            tz = zoneinfo.ZoneInfo(store.timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        # Resolve date filter (default to local store today)
        if not date:
            date = datetime.now(dt_timezone.utc).astimezone(tz).date()

        tz_name = store.timezone or "Asia/Kolkata"

        # 1. Total footfall on date (distinct entries)
        stmt_footfall = select(func.count(distinct(Event.visitor_id))).where(
            Event.store_id == store_id,
            Event.event_type == EventType.ENTRY,
            Event.cancelled == False,
            func.date(func.timezone(tz_name, Event.timestamp)) == date
        )
        footfall_res = await db.execute(stmt_footfall)
        footfall = footfall_res.scalar() or 0

        # 2. Engaged visitors (dwell duration >= store threshold, completed sessions only)
        stmt_engaged = select(func.count(Event.id)).where(
            Event.store_id == store_id,
            Event.event_type == EventType.EXIT,
            Event.cancelled == False,
            func.date(func.timezone(tz_name, Event.timestamp)) == date,
            cast(Event.metadata_payload["dwell_duration_seconds"].astext, Float) >= store.min_engaged_dwell_seconds
        )
        engaged_res = await db.execute(stmt_engaged)
        engaged_visitors = engaged_res.scalar() or 0

        # 3. Verified conversions (high confidence matched transactions on date)
        stmt_verified = select(func.count(distinct(Transaction.visitor_id))).where(
            Transaction.store_id == store_id,
            func.date(func.timezone(tz_name, Transaction.order_time)) == date,
            Transaction.is_visitor_matched == True,
            Transaction.match_confidence == "high"
        )
        verified_res = await db.execute(stmt_verified)
        verified_conversions = verified_res.scalar() or 0

        # 4. Estimated conversions (high + medium confidence matched transactions on date)
        stmt_estimated = select(func.count(distinct(Transaction.visitor_id))).where(
            Transaction.store_id == store_id,
            func.date(func.timezone(tz_name, Transaction.order_time)) == date,
            Transaction.is_visitor_matched == True,
            Transaction.match_confidence.in_(["high", "medium"])
        )
        estimated_res = await db.execute(stmt_estimated)
        estimated_conversions = estimated_res.scalar() or 0

        # 5. Total POS transactions & GMV on date
        stmt_tx = select(
            func.count(Transaction.id).label("tx_count"),
            func.sum(Transaction.gmv).label("total_gmv")
        ).where(
            Transaction.store_id == store_id,
            func.date(func.timezone(tz_name, Transaction.order_time)) == date
        )
        tx_res = await db.execute(stmt_tx)
        tx_row = tx_res.first()
        transactions = tx_row.tx_count if tx_row and tx_row.tx_count else 0
        gmv = float(tx_row.total_gmv) if tx_row and tx_row.total_gmv else 0.0

        # 6. Queue abandonment rate
        stmt_queue_joins = select(func.count(Event.id)).where(
            Event.store_id == store_id,
            Event.event_type == EventType.BILLING_QUEUE_JOIN,
            Event.cancelled == False,
            func.date(func.timezone(tz_name, Event.timestamp)) == date
        )
        joins_res = await db.execute(stmt_queue_joins)
        total_queue_joins = joins_res.scalar() or 0

        abandonment_rate = 0.0
        if total_queue_joins > 0:
            abandonment_rate = ((total_queue_joins - verified_conversions) / total_queue_joins) * 100.0

        # 7. Average Dwell (completed exits on date)
        stmt_dwell = select(func.avg(cast(Event.metadata_payload["dwell_duration_seconds"].astext, Float))).where(
            Event.store_id == store_id,
            Event.event_type == EventType.EXIT,
            Event.cancelled == False,
            func.date(func.timezone(tz_name, Event.timestamp)) == date
        )
        dwell_res = await db.execute(stmt_dwell)
        avg_dwell = dwell_res.scalar()
        avg_dwell_minutes = (avg_dwell / 60.0) if avg_dwell is not None else 0.0

        # 8. Conversion rates (using engaged visitors as denominator)
        verified_conversion_rate = 0.0
        if engaged_visitors > 0:
            verified_conversion_rate = (verified_conversions / engaged_visitors) * 100.0

        estimated_conversion_rate = 0.0
        if engaged_visitors > 0:
            estimated_conversion_rate = (estimated_conversions / engaged_visitors) * 100.0

        # 9. Active visitor count (All-time Entries - All-time Exits)
        entries_all = await db.scalar(
            select(func.count(distinct(Event.visitor_id)))
            .where(Event.store_id == store_id, Event.event_type == EventType.ENTRY, Event.cancelled == False)
        ) or 0
        exits_all = await db.scalar(
            select(func.count(Event.id))
            .where(Event.store_id == store_id, Event.event_type == EventType.EXIT, Event.cancelled == False)
        ) or 0
        active_visitors = max(0, entries_all - exits_all)

        # Legacy calculations for backward compatibility with standard metrics
        legacy_conversion_rate = (transactions / footfall * 100.0) if footfall > 0 else 0.0
        legacy_abv = (gmv / transactions) if transactions > 0 else 0.0

        return DashboardMetricsResponse(
            footfall=footfall,
            uniqueVisitors=footfall,
            transactions=transactions,
            gmv=gmv,
            conversionRate=round(legacy_conversion_rate, 1),
            averageBasketValue=round(legacy_abv, 2),
            total_exits=exits_all,
            active_visitor_count=active_visitors,
            totalFootfall=footfall,
            engagedVisitors=engaged_visitors,
            verifiedConversionRate=round(verified_conversion_rate, 1),
            estimatedConversionRate=round(estimated_conversion_rate, 1),
            queueAbandonmentRate=round(abandonment_rate, 1),
            avgDwellMinutes=round(avg_dwell_minutes, 1)
        )

    except Exception as e:
        logger.error(f"Failed to fetch dashboard metrics for store {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error fetching dashboard metrics"
        )


@router.get("/store/{store_id}/trend", response_model=List[DailyTrendResponse])
async def get_dashboard_trend(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    from src.models.store import Store
    from datetime import timedelta, timezone
    import zoneinfo
    
    try:
        # 1. Fetch store timezone
        store_stmt = select(Store).where(Store.id == store_id)
        store_res = await db.execute(store_stmt)
        store = store_res.scalar()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
            
        try:
            tz = zoneinfo.ZoneInfo(store.timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")
            
        now_local = datetime.now(timezone.utc).astimezone(tz)
        
        # Generate the last 30 calendar days
        days = []
        day_map = {}
        for i in range(29, -1, -1):
            d = (now_local - timedelta(days=i)).date()
            days.append({
                "metric_date": d,
                "footfall": 0,
                "unique_visitors": 0,
                "transactions": 0,
                "gmv": 0.0,
                "conversion_rate": 0.0,
                "average_basket_value": 0.0
            })
            day_map[d] = len(days) - 1
            
        start_date_local = now_local - timedelta(days=30)
        start_time_utc = start_date_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        
        # Query footfall events
        stmt_events = select(Event.visitor_id, Event.timestamp).where(
            Event.store_id == store_id,
            Event.event_type == EventType.ENTRY,
            Event.timestamp >= start_time_utc
        )
        events_res = await db.execute(stmt_events)
        events = events_res.all()
        
        # Group footfall & unique visitors in python
        daily_visitor_ids = {}
        for event in events:
            evt_date = event.timestamp.replace(tzinfo=timezone.utc).astimezone(tz).date()
            if evt_date in day_map:
                idx = day_map[evt_date]
                days[idx]["footfall"] += 1
                if evt_date not in daily_visitor_ids:
                    daily_visitor_ids[evt_date] = set()
                daily_visitor_ids[evt_date].add(event.visitor_id)
                
        for evt_date, v_ids in daily_visitor_ids.items():
            if evt_date in day_map:
                idx = day_map[evt_date]
                days[idx]["unique_visitors"] = len(v_ids)
                
        # Query transactions
        stmt_txs = select(Transaction.gmv, Transaction.order_time).where(
            Transaction.store_id == store_id,
            Transaction.order_time >= start_time_utc
        )
        txs_res = await db.execute(stmt_txs)
        txs = txs_res.all()
        
        for tx in txs:
            tx_date = tx.order_time.replace(tzinfo=timezone.utc).astimezone(tz).date()
            if tx_date in day_map:
                idx = day_map[tx_date]
                days[idx]["transactions"] += 1
                days[idx]["gmv"] += float(tx.gmv)
                
        # Calculate conversion rates and basket values
        result_trend = []
        for d_info in days:
            u_visitors = d_info["unique_visitors"]
            txs_count = d_info["transactions"]
            total_gmv = d_info["gmv"]
            
            conversion_rate = 0.0
            if u_visitors > 0:
                conversion_rate = round((txs_count / u_visitors) * 100.0, 1)
                
            average_basket_value = 0.0
            if txs_count > 0:
                average_basket_value = round(total_gmv / txs_count, 2)
                
            result_trend.append(
                DailyTrendResponse(
                    metric_date=d_info["metric_date"],
                    footfall=d_info["footfall"],
                    unique_visitors=d_info["unique_visitors"],
                    transactions=txs_count,
                    gmv=total_gmv,
                    conversion_rate=conversion_rate,
                    average_basket_value=average_basket_value
                )
            )
            
        return result_trend

    except Exception as e:
        logger.error(f"Failed to fetch trend for store {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error fetching trend metrics: {str(e)}"
        )


@router.get("/store/{store_id}/hourly-traffic", response_model=List[dict])
async def get_hourly_traffic(
    store_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    from src.models.store import Store
    from datetime import timedelta, timezone
    import zoneinfo
    
    try:
        # 1. Fetch store timezone
        store_stmt = select(Store).where(Store.id == store_id)
        store_res = await db.execute(store_stmt)
        store = store_res.scalar()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
            
        try:
            tz = zoneinfo.ZoneInfo(store.timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")
            
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(tz)
        
        # We want 12 hourly intervals ending at now
        start_local = now_local - timedelta(hours=12)
        start_local_aligned = start_local.replace(minute=0, second=0, microsecond=0)
        start_time_utc = start_local_aligned.astimezone(timezone.utc)
        
        # 2. Get initial occupancy before start_time_utc
        stmt_prev = select(
            func.count(Event.id).filter(Event.event_type == EventType.ENTRY).label("entries"),
            func.count(Event.id).filter(Event.event_type == EventType.EXIT).label("exits")
        ).where(
            Event.store_id == store_id,
            Event.timestamp < start_time_utc
        )
        prev_res = await db.execute(stmt_prev)
        prev_row = prev_res.first()
        prev_entries = prev_row.entries if prev_row and prev_row.entries else 0
        prev_exits = prev_row.exits if prev_row and prev_row.exits else 0
        running_occupancy = max(0, prev_entries - prev_exits)
        
        # 3. Fetch all entry/exit events in the window
        stmt_events = select(Event.event_type, Event.timestamp).where(
            Event.store_id == store_id,
            Event.event_type.in_([EventType.ENTRY, EventType.EXIT]),
            Event.timestamp >= start_time_utc,
            Event.timestamp <= now_utc
        ).order_by(Event.timestamp.asc())
        
        events_res = await db.execute(stmt_events)
        events = events_res.all()
        
        # 4. Group events by hour bucket in local time
        buckets = []
        bucket_map = {}
        
        for i in range(13): # 12 hours ago to current hour inclusive (13 points)
            dt = start_local_aligned + timedelta(hours=i)
            hour_num = dt.hour
            ampm = "AM" if hour_num < 12 else "PM"
            display_hour = hour_num if hour_num <= 12 else hour_num - 12
            if display_hour == 0:
                display_hour = 12
            time_label = f"{display_hour}:00 {ampm}"
            
            buckets.append({
                "time": time_label,
                "Entries": 0,
                "Exits": 0,
                "InStore": 0
            })
            bucket_map[(dt.year, dt.month, dt.day, dt.hour)] = i
            
        for event in events:
            event_local = event.timestamp.replace(tzinfo=timezone.utc).astimezone(tz)
            key = (event_local.year, event_local.month, event_local.day, event_local.hour)
            if key in bucket_map:
                idx = bucket_map[key]
                if event.event_type == EventType.ENTRY:
                    buckets[idx]["Entries"] += 1
                elif event.event_type == EventType.EXIT:
                    buckets[idx]["Exits"] += 1
                    
        # 5. Calculate cumulative occupancy (InStore)
        for bucket in buckets:
            running_occupancy += (bucket["Entries"] - bucket["Exits"])
            if running_occupancy < 0:
                running_occupancy = 0
            bucket["InStore"] = running_occupancy
            
        return buckets

    except Exception as e:
        logger.error(f"Failed to fetch hourly traffic for store {store_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error fetching hourly traffic: {str(e)}"
        )



@router.get("/store/{store_id}/stream")
async def stream_live_dashboard(store_id: uuid.UUID):
    """
    SSE Endpoint for real-time bounding boxes and physical events.
    """
    redis_uri = os.getenv("REDIS_URI", "redis://redis:6379/0")
    r = redis.from_url(redis_uri)

    async def event_generator():
        pubsub = r.pubsub()
        await pubsub.subscribe("live_events", "live_telemetry", "pipeline_status")
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    channel = message["channel"].decode("utf-8")
                    data = message["data"].decode("utf-8")
                    
                    parsed_data = json.loads(data)
                    # Filter by store_id
                    if str(parsed_data.get("store_id")) != str(store_id):
                        continue
                    
                    if channel == "live_telemetry":
                        event_type = "telemetry"
                    elif channel == "pipeline_status":
                        event_type = "pipeline_status"
                    else:
                        event_type = "domain_event"
                    
                    yield f"event: {event_type}\ndata: {data}\n\n"
                else:
                    # Keep-alive
                    yield ": keep-alive\n\n"
                    await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.info("Client disconnected from SSE stream")
        finally:
            await pubsub.unsubscribe()
            await r.aclose()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/store", response_model=DashboardMetricsResponse, summary="Get Meridian store KPIs (resolved)")
async def get_dashboard_metrics_resolved(
    date: Optional[date] = Query(None, description="Query date (defaults to local store today)"),
    db: AsyncSession = Depends(get_db)
) -> DashboardMetricsResponse:
    return await get_dashboard_metrics(store_id=MERIDIAN_STORE_ID, date=date, db=db)


@router.get("/trend", response_model=List[DailyTrendResponse], summary="Get Meridian daily trend metrics (resolved)")
async def get_dashboard_trend_resolved(
    db: AsyncSession = Depends(get_db)
) -> List[DailyTrendResponse]:
    return await get_dashboard_trend(store_id=MERIDIAN_STORE_ID, db=db)


@router.get("/traffic", response_model=List[dict], summary="Get Meridian hourly traffic (resolved)")
async def get_hourly_traffic_resolved(
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    return await get_hourly_traffic(store_id=MERIDIAN_STORE_ID, db=db)


@router.get("/funnel", response_model=AnalyticsFunnelResponse, summary="Get Conversion Funnel (resolved)")
async def get_dashboard_funnel_resolved(
    start_time: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=1),
        description="Defaults to the last 24 hours"
    ),
    end_time: datetime = Query(
        default_factory=lambda: datetime.now(timezone.utc)
    ),
    db: AsyncSession = Depends(get_db)
) -> AnalyticsFunnelResponse:
    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="start_time must be strictly before end_time."
        )

    try:
        service = AnalyticsService(db)
        return await service.calculate_funnel(MERIDIAN_STORE_ID, start_time, end_time)
    except Exception as e:
        logger.error(f"Failed to calculate funnel for store {MERIDIAN_STORE_ID}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during funnel aggregation."
        )


@router.get("/store/stream", summary="SSE Endpoint for real-time live events (resolved)")
async def stream_live_dashboard_resolved():
    return await stream_live_dashboard(store_id=MERIDIAN_STORE_ID)
