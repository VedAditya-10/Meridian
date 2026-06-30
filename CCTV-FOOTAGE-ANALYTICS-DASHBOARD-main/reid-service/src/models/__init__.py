"""
Purpose: Export all ORM models for Alembic auto-generation and application use.
Responsibilities:
- Provide a single centralized import point for all database entities.
- Guarantee that all models are attached to the `Base.metadata` registry before Alembic generates migrations.
Dependencies: src.models.*
"""

from src.models.base import Base
from src.models.event import Event, EventType
from src.models.store import Camera, Store, Zone
from src.models.visitor import Visitor, VisitorEmbedding

# Exposing exactly what is intended.
# Alembic's env.py will import `Base` from here, and because the other models
# are imported into this file, SQLAlchemy's registry will successfully map them
# all to the metadata. Without this, Alembic will fail to detect table changes.
__all__ = [
    "Base",
    "Store",
    "Camera",
    "Zone",
    "Visitor",
    "VisitorEmbedding",
    "Event",
    "EventType",
]
