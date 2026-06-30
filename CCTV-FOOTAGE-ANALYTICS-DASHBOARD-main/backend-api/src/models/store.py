"""
Purpose: ORM Models representing physical store infrastructure.
Responsibilities:
- Define the `Store` aggregate root.
- Define `Camera` entities belonging to a Store.
- Define `Zone` entities (polygons) used by the Event Engine for spatial reasoning.
Dependencies: sqlalchemy, src.models.base
"""

import uuid
from datetime import datetime
from typing import Any, List

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class Store(Base, UUIDMixin, TimestampMixin):
    """
    Represents the single physical retail location in a Meridian deployment.
    """
    __tablename__ = "stores"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Kolkata")
    min_engaged_dwell_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_cameras: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    cameras: Mapped[List["Camera"]] = relationship(
        "Camera", back_populates="store", cascade="all, delete-orphan"
    )
    zones: Mapped[List["Zone"]] = relationship(
        "Zone", back_populates="store", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Store(id={self.id}, name='{self.name}')>"


class Camera(Base, UUIDMixin, TimestampMixin):
    """CCTV camera or video source within the store."""
    __tablename__ = "cameras"

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    camera_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="rtsp_stream"
    )
    rtsp_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    video_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="inactive")
    position_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calibration_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    store: Mapped["Store"] = relationship("Store", back_populates="cameras")

    def __repr__(self) -> str:
        return f"<Camera(id={self.id}, store_id={self.store_id}, name='{self.name}')>"


class Zone(Base, UUIDMixin, TimestampMixin):
    """
    Physical area of interest. Event engine uses `polygon` with normalized 0.0–1.0 points.
    """
    __tablename__ = "zones"

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, comment="e.g., QUEUE, AISLE, DISPLAY, ENTRY_LINE"
    )
    polygon: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    product_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    store: Mapped["Store"] = relationship("Store", back_populates="zones")

    def __repr__(self) -> str:
        return f"<Zone(id={self.id}, type='{self.zone_type}', name='{self.name}')>"
