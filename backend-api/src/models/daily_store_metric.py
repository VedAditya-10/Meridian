import uuid
from datetime import date

from sqlalchemy import Column, Integer, Numeric, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base


class DailyStoreMetric(Base):
    __tablename__ = "daily_store_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    metric_date = Column(Date, nullable=False)
    footfall = Column(Integer, default=0, nullable=False)
    unique_visitors = Column(Integer, default=0, nullable=False)
    transactions = Column(Integer, default=0, nullable=False)
    gmv = Column(Numeric(12, 2), default=0.0, nullable=False)
    conversion_rate = Column(Numeric(5, 2), default=0.0, nullable=False)
    average_basket_value = Column(Numeric(12, 2), default=0.0, nullable=False)
