import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, Numeric, String, DateTime, ForeignKey, Index, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.models.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(100), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    visitor_id = Column(UUID(as_uuid=True), ForeignKey("visitors.id"), nullable=True)
    order_time = Column(DateTime(timezone=True), nullable=False)
    customer_no = Column(String(100), nullable=True)
    qty = Column(Integer, nullable=False)
    gmv = Column(Numeric(12, 2), nullable=False)
    product_category = Column(String(100), nullable=True)
    product_name = Column(String(255), nullable=True)
    match_confidence = Column(String(10), nullable=True)  # "high", "medium", "low"
    is_visitor_matched = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("order_id", "store_id", name="uq_transaction_order_store"),
        Index("ix_transactions_store_id", "store_id"),
        Index("ix_transactions_order_time", "order_time"),
        Index("ix_transactions_store_time", "store_id", "order_time"),
        Index("ix_transactions_visitor_id", "visitor_id"),
        Index("ix_transactions_product_category", "product_category"),
    )


class TransactionIngestionError(Base):
    __tablename__ = "transaction_ingestion_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    row_number = Column(Integer, nullable=False)
    raw_payload = Column(String, nullable=False)
    error_message = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
