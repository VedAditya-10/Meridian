"""
Purpose: Single-store context for Meridian deployments.
Responsibilities:
- Expose the fixed MERIDIAN_STORE_ID used across API, edge-node, and workers.
- Provide helpers to load the one store record from the database.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.models.store import Store

MERIDIAN_STORE_ID: uuid.UUID = settings.MERIDIAN_STORE_ID


async def get_meridian_store(db: AsyncSession, *, with_cameras: bool = False) -> Store:
    """Load the single Meridian store or raise 404."""
    stmt = select(Store).where(Store.id == MERIDIAN_STORE_ID)
    if with_cameras:
        stmt = stmt.options(selectinload(Store.cameras))
    result = await db.execute(stmt)
    store = result.scalars().first()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meridian store is not configured. Run database bootstrap.",
        )
    return store
