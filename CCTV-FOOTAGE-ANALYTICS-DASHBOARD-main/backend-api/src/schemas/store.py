"""
Purpose: Pydantic schemas for Store, Camera, and Zone API validation.
Responsibilities:
- Strictly validate incoming JSON payloads for creation/updates.
- Serialize SQLAlchemy ORM models into clean, typed outgoing JSON responses.
- Define explicit API contracts (Swagger/OpenAPI).
Dependencies: pydantic
"""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# --- Zone Schemas ---

class ZoneBase(BaseModel):
    name: str = Field(..., max_length=255, examples=["Checkout Queue 1", "Nike Display"])
    zone_type: str = Field(
        ..., max_length=50, examples=["QUEUE", "DISPLAY", "ENTRY_LINE"]
    )
    product_category: Optional[str] = Field(None, max_length=100)
    # The frontend allows drawing polygons over a camera frame. 
    # We validate this as a list of dictionaries with x,y coords.
    polygon: List[dict[str, float]] = Field(
        ..., 
        description="List of coordinates forming the polygon: [{'x': 0.0, 'y': 0.0}, ...]",
        examples=[[{"x": 10.5, "y": 20.0}, {"x": 30.0, "y": 20.0}, {"x": 30.0, "y": 50.0}]]
    )


class ZoneCreate(ZoneBase):
    pass


class ZoneResponse(ZoneBase):
    id: uuid.UUID
    store_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Instructs Pydantic V2 to read data even if it's an ORM model rather than a dict.
    model_config = ConfigDict(from_attributes=True)


# --- Camera Schemas ---

class CameraBase(BaseModel):
    name: str = Field(..., max_length=255, examples=["Entrance Cam Left"])
    # Pydantic's HttpUrl ensures the RTSP string is syntactically a valid URI.
    # Note: We may need AnyUrl if we specifically want to enforce `rtsp://` scheme easily.
    rtsp_url: str = Field(..., description="Internal RTSP stream URL for the Edge Node")
    
    # Opaque calibration matrix for mapping 2D pixels to global floorplan
    calibration_data: Optional[dict[str, Any]] = None


class CameraCreate(CameraBase):
    pass


class CameraResponse(CameraBase):
    id: uuid.UUID
    store_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Store Schemas ---

class StoreBase(BaseModel):
    name: str = Field(..., max_length=255, examples=["NYC Flagship"])
    # Critical for analytics: IANA Timezone string
    timezone: str = Field(default="Asia/Kolkata", max_length=50, examples=["America/New_York", "Asia/Tokyo"])
    min_engaged_dwell_seconds: int = Field(default=60, description="Dwell threshold to count as an engaged visitor")


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    # All fields are optional in an update (PATCH) payload
    name: Optional[str] = Field(None, max_length=255)
    timezone: Optional[str] = Field(None, max_length=50)


class StoreResponse(StoreBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    # We include nested relationships as optional. 
    # This allows specific API endpoints to eager-load and return the full store graph,
    # or just return the store summary to save bandwidth.
    cameras: Optional[List[CameraResponse]] = None
    zones: Optional[List[ZoneResponse]] = None

    model_config = ConfigDict(from_attributes=True)
