"""
Purpose: ORM Models representing physical store infrastructure.
Responsibilities:
- Define the `Store` aggregate root.
- Define `Camera` entities belonging to a Store.
- Define `Zone` entities (polygons) used by the Event Engine for spatial reasoning.
- Dependencies: sqlalchemy, src.models.base
"""

from datetime import datetime
import uuid
from typing import Any, List

from sqlalchemy import ForeignKey, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class Store(Base, UUIDMixin, TimestampMixin):
    """
    Represents a physical retail location.
    Acts as the tenancy boundary for most queries (metrics are typically queried per Store).
    """
    __tablename__ = "stores"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Store specific timezone is critical for analytics (e.g., "Daily conversion rate" 
    # means midnight-to-midnight in the store's local timezone, not UTC).
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Kolkata")
    min_engaged_dwell_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    location: Mapped[str] = mapped_column(String(255), nullable=True)

    # Relationships - cascade="all, delete-orphan" ensures data integrity if a store is deleted
    cameras: Mapped[List["Camera"]] = relationship(
        "Camera", back_populates="store", cascade="all, delete-orphan"
    )
    zones: Mapped[List["Zone"]] = relationship(
        "Zone", back_populates="store", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Store(id={self.id}, name='{self.name}')>"


class Camera(Base, UUIDMixin, TimestampMixin):
    """
    Represents an RTSP CCTV camera feed within a store.
    """
    __tablename__ = "cameras"

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Internal RTSP URL used by the Edge node to pull the video feed
    rtsp_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    
    # Stores homography matrix or perspective transformation data for mapping
    # 2D camera coordinates into a global 2D floorplan coordinate space.
    calibration_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    store: Mapped["Store"] = relationship("Store", back_populates="cameras")

    def __repr__(self) -> str:
        return f"<Camera(id={self.id}, store_id={self.store_id}, name='{self.name}')>"


class Zone(Base, UUIDMixin, TimestampMixin):
    """
    Represents a physical area of interest within a store (e.g., QUEUE, DISPLAY, ENTRANCE).
    The Event Engine uses the `polygon` data to determine if a tracked visitor intersects this zone.
    """
    __tablename__ = "zones"

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Indexed for fast filtering when calculating specific metrics (e.g., "Get all QUEUE zones")
    zone_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="e.g., QUEUE, AISLE, DISPLAY, ENTRY_LINE"
    )
    
    # Stores polygon coordinates: e.g., [{"x": 100, "y": 200}, {"x": 300, "y": 400}, ...]
    # For a high-scale production system, we use JSONB rather than PostGIS for simplicity,
    # as spatial reasoning happens purely in-memory in the Python Event Engine, not in SQL.
    polygon: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    product_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    store: Mapped["Store"] = relationship("Store", back_populates="zones")

    def __repr__(self) -> str:
        return f"<Zone(id={self.id}, type='{self.zone_type}', name='{self.name}')>"
