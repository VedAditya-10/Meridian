"""
Purpose: Core SQLAlchemy Base model and foundational mixins.
Responsibilities:
- Define the `DeclarativeBase` required by SQLAlchemy 2.0.
- Provide a `UUIDMixin` for secure, distributed primary keys.
- Provide a `TimestampMixin` for strict UTC timezone-aware auditing.
Dependencies: sqlalchemy
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 DeclarativeBase.
    All ORM models in the system must inherit from this class.
    """
    # Enables advanced SQLAlchemy 2.0 type checking
    pass


class UUIDMixin:
    """
    Provides a standardized UUIDv4 primary key for models.
    
    Why UUIDs over Auto-Incrementing Integers?
    1. Security: Prevents ID enumeration attacks (e.g., guessing /stores/2 after seeing /stores/1).
    2. Scalability: Allows edge nodes to generate IDs without coordinating with a central database.
    3. Migration: Makes cross-database migrations and data merging significantly easier.
    """
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )


def utcnow() -> datetime:
    """Helper to return an explicitly timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    """
    Mixin that adds strict UTC `created_at` and `updated_at` timestamps to any model.
    Timezones are notoriously buggy in distributed systems; explicitly enforcing 
    `DateTime(timezone=True)` with UTC ensures consistency globally.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        comment="UTC timestamp when the record was created"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
        comment="UTC timestamp when the record was last modified"
    )
