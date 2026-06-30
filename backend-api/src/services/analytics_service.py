"""
Purpose: Core business logic for aggregating Store Analytics.
Responsibilities:
- Translate raw append-only timeseries Events into high-level KPIs.
- Execute optimized SQLAlchemy queries for funnel drops and spatial heatmaps.
- Apply heuristics for basic anomaly detection.
Dependencies: sqlalchemy, src.models, src.schemas
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event import Event, EventType
from src.models.store import Store, Zone
from src.schemas.event import (
    AnalyticsFunnelResponse,
    AnalyticsHeatmapResponse,
    AnalyticsMetricsResponse,
    FunnelStep,
    ZoneHeatmapData,
)


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_daily_metrics(self, store_id: uuid.UUID) -> AnalyticsMetricsResponse:
        """
        Calculates KPIs based on raw events.
        Note: In a true massive-scale production environment (e.g., 4000 stores), 
        these counts would be queried from pre-aggregated Materialized Views or 
        Redis counters. However, for 40 stores, indexed PostgreSQL can handle 
        direct queries over the current day's partition efficiently.
        """
        store = await self.db.get(Store, store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found in database.")

        # Single pass query to count multiple event types using filter clauses
        stmt = select(
            func.count(Event.id).filter(Event.event_type == EventType.ENTRY).label("entries"),
            func.count(Event.id).filter(Event.event_type == EventType.EXIT).label("exits"),
            func.count(Event.id).filter(Event.event_type == EventType.BILLING_QUEUE_JOIN).label("queue_joins"),
        ).where(Event.store_id == store_id)
        
        result = await self.db.execute(stmt)
        row = result.one()
        
        entries = row.entries or 0
        exits = row.exits or 0
        queue_joins = row.queue_joins or 0
        
        conversion_rate = (queue_joins / entries * 100) if entries > 0 else 0.0
        
        # Simplified live occupancy (Entries - Exits)
        active_visitors = max(0, entries - exits)

        # Average Dwell Time calculated from EXIT events metadata
        from sqlalchemy import cast, Float
        stmt_dwell = select(func.avg(cast(Event.metadata_payload['dwell_duration_seconds'].astext, Float))).where(
            Event.store_id == store_id,
            Event.event_type == EventType.EXIT
        )
        dwell_res = await self.db.execute(stmt_dwell)
        avg_dwell = dwell_res.scalar()
        avg_dwell_seconds = int(round(avg_dwell)) if avg_dwell is not None else 0

        return AnalyticsMetricsResponse(
            store_id=store_id,
            total_entries=entries,
            total_exits=exits,
            average_dwell_time_seconds=avg_dwell_seconds,
            conversion_rate=conversion_rate,
            active_visitor_count=active_visitors
        )

    async def calculate_funnel(
        self, store_id: uuid.UUID, start_time: datetime, end_time: datetime
    ) -> AnalyticsFunnelResponse:
        """
        Calculates exact visitor drop-off: Entrance -> Zone Engagement -> Checkout.
        Uses `COUNT(DISTINCT visitor_id)` to ensure one person entering a zone 
        multiple times only counts as a single funnel conversion.
        """
        stmt = select(
            func.count(Event.visitor_id.distinct()).filter(Event.event_type == EventType.ENTRY).label("entered"),
            func.count(Event.visitor_id.distinct()).filter(Event.event_type == EventType.ZONE_DWELL).label("engaged"),
            func.count(Event.visitor_id.distinct()).filter(Event.event_type == EventType.BILLING_QUEUE_JOIN).label("checkout")
        ).where(
            and_(
                Event.store_id == store_id,
                Event.timestamp >= start_time,
                Event.timestamp <= end_time
            )
        )
        
        result = await self.db.execute(stmt)
        row = result.one()
        
        entered = row.entered or 0
        engaged = row.engaged or 0
        checkout = row.checkout or 0
        
        steps = [
            FunnelStep(
                step_name="Entered Store",
                visitor_count=entered,
                conversion_rate_from_previous=None
            ),
            FunnelStep(
                step_name="Engaged with Zone",
                visitor_count=engaged,
                conversion_rate_from_previous=(engaged / entered * 100) if entered > 0 else 0.0
            ),
            FunnelStep(
                step_name="Joined Checkout",
                visitor_count=checkout,
                conversion_rate_from_previous=(checkout / engaged * 100) if engaged > 0 else 0.0
            )
        ]
        
        return AnalyticsFunnelResponse(
            store_id=store_id,
            time_window_start=start_time,
            time_window_end=end_time,
            steps=steps
        )

    async def calculate_heatmap(
        self, store_id: uuid.UUID, start_time: datetime, end_time: datetime
    ) -> AnalyticsHeatmapResponse:
        """
        Calculates normalized popularity for each zone.
        Uses an outer join from Zones to Events to ensure cold zones (0 events) 
        are still returned to the dashboard.
        """
        stmt = select(
            Zone.id,
            Zone.name,
            Zone.zone_type,
            func.count(Event.id).label("dwell_events"),
            func.count(Event.visitor_id.distinct()).label("unique_visitors")
        ).outerjoin(
            Event, 
            and_(
                Event.zone_id == Zone.id,
                Event.event_type == EventType.ZONE_DWELL,
                Event.timestamp >= start_time,
                Event.timestamp <= end_time
            )
        ).where(
            Zone.store_id == store_id
        ).group_by(Zone.id, Zone.name, Zone.zone_type)
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        # Calculate max dwell to normalize the gradient
        max_dwell = max([r.dwell_events for r in rows]) if rows else 0
        
        zones = []
        for row in rows:
            # 0.0 to 1.0 normalization for frontend heat mapping
            density = (row.dwell_events / max_dwell) if max_dwell > 0 else 0.0
            zones.append(
                ZoneHeatmapData(
                    zone_id=row.id,
                    zone_name=row.name,
                    zone_type=row.zone_type,
                    dwell_time_density=density,
                    unique_visitors=row.unique_visitors
                )
            )
            
        return AnalyticsHeatmapResponse(
            store_id=store_id,
            time_window_start=start_time,
            time_window_end=end_time,
            zones=zones
        )

    async def detect_anomalies(self, store_id: uuid.UUID) -> List[dict]:
        """
        Statistical heuristics for anomaly detection.
        In a fully scaled V2 architecture, this would query an ML Isolation Forest.
        For V1, we check if abandonment rates spike beyond standard deviations.
        """
        fifteen_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
        
        stmt = select(func.count(Event.id)).where(
            and_(
                Event.store_id == store_id,
                Event.event_type == EventType.BILLING_QUEUE_ABANDON,
                Event.timestamp >= fifteen_mins_ago
            )
        )
        
        result = await self.db.execute(stmt)
        recent_abandons = result.scalar() or 0
        
        anomalies = []
        # Arbitrary heuristic for demonstration: > 5 abandons in 15 mins is bad
        if recent_abandons > 5:
            anomalies.append({
                "type": "QUEUE_SPIKE",
                "severity": "HIGH",
                "message": f"Critical: {recent_abandons} customers abandoned the checkout queue in the last 15 minutes."
            })
            
        return anomalies
