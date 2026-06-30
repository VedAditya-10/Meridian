"""
Purpose: ORM Models representing visitors and their biometric embeddings.
Responsibilities:
- Define the `Visitor` entity, grouping all observations of a single person across cameras.
- Define the `VisitorEmbedding` entity using `pgvector` for fast cosine-similarity search.
- Dependencies: sqlalchemy, pgvector, src.models.base
"""

import uuid
from datetime import datetime
from typing import Any, List

# WARNING: Requires 'pgvector' extension to be installed in PostgreSQL 
# CREATE EXTENSION IF NOT EXISTS vector;
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin


class Visitor(Base, UUIDMixin, TimestampMixin):
    """
    Represents a unique tracked individual within a Store.
    Through the ReID (Re-Identification) process, multiple transient track IDs from different 
    cameras are mathematically resolved into a single global Visitor ID.
    """
    __tablename__ = "visitors"

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Tracking the exact bounding timeframe the visitor was physically in the store.
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Staff Exclusion: If a visitor's dwell time exceeds a shift threshold (e.g. 4 hours),
    # or they match a known staff uniform embedding, they are flagged and excluded from 
    # the primary conversion rate analytics.
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    staff_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationships
    embeddings: Mapped[List["VisitorEmbedding"]] = relationship(
        "VisitorEmbedding", back_populates="visitor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Visitor(id={self.id}, store_id={self.store_id}, is_staff={self.is_staff})>"


class VisitorEmbedding(Base, UUIDMixin, TimestampMixin):
    """
    Stores the high-dimensional feature vector extracted by ResNet50 ReID model.
    Uses PostgreSQL's `pgvector` extension for ultra-fast similarity search (cosine distance).
    """
    __tablename__ = "visitor_embeddings"

    visitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # 2048 dimensions matches the output of a FastReID ResNet50 feature extractor.
    embedding: Mapped[Any] = mapped_column(Vector(2048), nullable=False)
    
    # Garbage In, Garbage Out: We only persist high-quality embeddings. 
    # If a person is highly occluded or severely blurred, the Edge Node assigns 
    # a low quality_score and the embedding is discarded to prevent ReID pollution.
    quality_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Visual quality/confidence of the person crop"
    )

    # Relationships
    visitor: Mapped["Visitor"] = relationship("Visitor", back_populates="embeddings")

    def __repr__(self) -> str:
        return f"<VisitorEmbedding(id={self.id}, visitor_id={self.visitor_id}, quality={self.quality_score:.2f})>"
