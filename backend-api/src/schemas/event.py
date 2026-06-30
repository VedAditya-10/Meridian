"""
Purpose: Pydantic schemas for Event validation and Analytics Dashboard responses.
Responsibilities:
- Validate core Event structures if injected via REST (fallback to Redis).
- Define the strict response contracts for the Dashboard Analytics.
Dependencies: pydantic, src.models.event
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.models.event import EventType


# --- Core Event Schemas ---

class EventBase(BaseModel):
    store_id: uuid.UUID
    visitor_id: uuid.UUID
    zone_id: Optional[uuid.UUID] = None
    event_type: EventType
    timestamp: datetime
    
    # We use `alias` to map the incoming/outgoing JSON key "metadata" 
    # to the Python model field "metadata_payload" (avoiding SQLAlchemy reserved words).
    metadata_payload: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class EventCreate(EventBase):
    """Payload for manual/webhook event ingestion."""
    pass


class EventResponse(EventBase):
    """Payload for retrieving raw event logs."""
    id: uuid.UUID

    # populate_by_name allows Pydantic to use the alias ("metadata") when serializing.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# --- Analytics Response Schemas (Dashboard Contracts) ---
# These schemas define the exact structure the React/Vite dashboard expects.

class FunnelStep(BaseModel):
    """Represents a single stage in the retail conversion funnel."""
    step_name: str = Field(..., description="e.g., 'Entered', 'Engaged/Dwell', 'Checkout'")
    visitor_count: int
    conversion_rate_from_previous: Optional[float] = Field(
        None, description="Percentage (0.0 to 100.0) drop-off from the previous step"
    )


class AnalyticsFunnelResponse(BaseModel):
    store_id: uuid.UUID
    time_window_start: datetime
    time_window_end: datetime
    steps: List[FunnelStep]


class AnalyticsMetricsResponse(BaseModel):
    """High-level Key Performance Indicators (KPIs) for the store."""
    store_id: uuid.UUID
    total_entries: int = Field(..., description="Total unique entries into the store")
    total_exits: int
    average_dwell_time_seconds: int
    
    # The ultimate business metric: How many entered vs how many joined the billing queue
    conversion_rate: float = Field(..., description="Checkout Queue Joins / Total Entries")
    
    # Real-time state query
    active_visitor_count: int = Field(..., description="Current live occupancy of the store")


class ZoneHeatmapData(BaseModel):
    """Data required to render the Heatmap overlay on the dashboard."""
    zone_id: uuid.UUID
    zone_name: str
    zone_type: str = Field(..., description="e.g., ENTRY_LINE, DISPLAY, AISLE, QUEUE")
    
    # Normalized value between 0.0 (Cold) and 1.0 (Hot) used to determine the overlay color
    dwell_time_density: float = Field(..., description="Normalized popularity density (0.0 to 1.0)")
    unique_visitors: int


class AnalyticsHeatmapResponse(BaseModel):
    store_id: uuid.UUID
    time_window_start: datetime
    time_window_end: datetime
    zones: List[ZoneHeatmapData]
