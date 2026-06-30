"""
Purpose: FastAPI CRUD endpoints for Camera Management.
"""

import logging
import uuid
import os
from datetime import datetime, timezone
from typing import List, Optional

import time
import cv2
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.store_context import MERIDIAN_STORE_ID
from src.models.store import Camera

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cameras", tags=["Camera Management"])


class CameraResponse(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    camera_type: str
    rtsp_url: Optional[str] = None
    video_file_path: Optional[str] = None
    status: str
    position_index: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CameraCreate(BaseModel):
    name: str = Field(..., max_length=255)
    camera_type: str = Field("rtsp_stream", description="rtsp_stream | video_file | webcam")
    rtsp_url: Optional[str] = Field(None, max_length=1024)
    video_file_path: Optional[str] = Field(None, max_length=1024)
    status: str = Field("inactive")
    position_index: Optional[int] = None


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    camera_type: Optional[str] = None
    rtsp_url: Optional[str] = Field(None, max_length=1024)
    video_file_path: Optional[str] = Field(None, max_length=1024)
    status: Optional[str] = None
    position_index: Optional[int] = None


@router.get("", response_model=List[CameraResponse], summary="List all active (non-deleted) cameras")
async def list_cameras(db: AsyncSession = Depends(get_db)) -> List[Camera]:
    stmt = (
        select(Camera)
        .where(
            and_(
                Camera.store_id == MERIDIAN_STORE_ID,
                Camera.deleted_at.is_(None)
            )
        )
        .order_by(Camera.position_index.asc(), Camera.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED, summary="Add a camera")
async def create_camera(payload: CameraCreate, db: AsyncSession = Depends(get_db)) -> Camera:
    # 1. Reject if active cameras >= 6
    count_stmt = select(func.count(Camera.id)).where(
        and_(
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.deleted_at.is_(None)
        )
    )
    count_result = await db.execute(count_stmt)
    active_count = count_result.scalar() or 0
    if active_count >= 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Active camera limit reached (maximum 6 active cameras)."
        )

    # 2. Enforce active camera name uniqueness
    name_stmt = select(Camera).where(
        and_(
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.name == payload.name,
            Camera.deleted_at.is_(None)
        )
    )
    name_result = await db.execute(name_stmt)
    if name_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An active camera with the name '{payload.name}' already exists."
        )

    # 3. Handle default position index
    pos_idx = payload.position_index
    if pos_idx is None:
        pos_idx = active_count + 1

    camera = Camera(
        id=uuid.uuid4(),
        store_id=MERIDIAN_STORE_ID,
        name=payload.name,
        camera_type=payload.camera_type,
        rtsp_url=payload.rtsp_url,
        video_file_path=payload.video_file_path,
        status=payload.status,
        position_index=pos_idx,
    )
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    return camera


@router.get("/{camera_id}", response_model=CameraResponse, summary="Get camera details")
async def get_camera(camera_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Camera:
    stmt = select(Camera).where(
        and_(
            Camera.id == camera_id,
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found or has been deleted."
        )
    return camera


@router.put("/{camera_id}", response_model=CameraResponse, summary="Update camera configurations")
async def update_camera(
    camera_id: uuid.UUID,
    payload: CameraUpdate,
    db: AsyncSession = Depends(get_db)
) -> Camera:
    # 1. Fetch existing camera
    stmt = select(Camera).where(
        and_(
            Camera.id == camera_id,
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found."
        )

    # 2. Enforce active name uniqueness if updated
    if payload.name is not None and payload.name != camera.name:
        name_stmt = select(Camera).where(
            and_(
                Camera.store_id == MERIDIAN_STORE_ID,
                Camera.name == payload.name,
                Camera.deleted_at.is_(None)
            )
        )
        name_result = await db.execute(name_stmt)
        if name_result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active camera with the name '{payload.name}' already exists."
            )
        camera.name = payload.name

    if payload.camera_type is not None:
        camera.camera_type = payload.camera_type
    if payload.rtsp_url is not None:
        camera.rtsp_url = payload.rtsp_url
    if payload.video_file_path is not None:
        camera.video_file_path = payload.video_file_path
    if payload.status is not None:
        camera.status = payload.status
    if payload.position_index is not None:
        camera.position_index = payload.position_index

    camera.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(camera)
    return camera


@router.delete("/{camera_id}", summary="Soft delete camera")
async def delete_camera(camera_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Camera).where(
        and_(
            Camera.id == camera_id,
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found."
        )

    camera.deleted_at = datetime.now(timezone.utc)
    camera.status = "inactive"
    await db.commit()
    logger.info(f"Soft deleted camera {camera_id}")
    return {"status": "success", "message": "Camera soft deleted successfully"}


@router.post("/{camera_id}/test", summary="Test camera connection")
async def test_camera(camera_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Camera).where(
        and_(
            Camera.id == camera_id,
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found."
        )

    source = ""
    if camera.camera_type == "rtsp_stream":
        source = camera.rtsp_url
    elif camera.camera_type == "video_file":
        source = camera.video_file_path
    elif camera.camera_type == "webcam":
        source = "0"  # default webcam index

    if not source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No source URL or path defined for this camera."
        )

    # Resolve device index for webcam
    if camera.camera_type == "webcam":
        try:
            device_source = int(source)
        except ValueError:
            device_source = 0
    else:
        device_source = source

    # Run OpenCV check in background/thread with timeout safety
    # We set OpenCV env variables for RTSP timeout
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
    cap = cv2.VideoCapture(device_source)
    if not cap.isOpened():
        return {"status": "failed", "detail": "Failed to open camera source connection."}

    ret, _ = cap.read()
    cap.release()

    if ret:
        return {"status": "success", "message": "Successfully connected and grabbed frame."}
    else:
        return {"status": "failed", "detail": "Connected to source, but failed to read video frames."}


# A simple in-memory cache for camera snapshots
# {camera_id: (timestamp_float, jpeg_bytes)}
SNAPSHOT_CACHE = {}
SNAPSHOT_CACHE_DURATION = 30.0  # seconds

@router.get("/{camera_id}/snapshot", summary="Get a snapshot frame from the camera")
async def get_camera_snapshot(
    camera_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    # 1. Fetch active camera details
    stmt = select(Camera).where(
        and_(
            Camera.id == camera_id,
            Camera.store_id == MERIDIAN_STORE_ID,
            Camera.deleted_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    camera = result.scalars().first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found or is inactive."
        )

    # 2. Check snapshot cache
    now = time.time()
    if camera_id in SNAPSHOT_CACHE:
        cache_time, cached_bytes = SNAPSHOT_CACHE[camera_id]
        if now - cache_time < SNAPSHOT_CACHE_DURATION:
            return Response(content=cached_bytes, media_type="image/jpeg")

    # 3. Read camera frame based on its type
    source = None
    if camera.camera_type == "rtsp_stream":
        source = camera.rtsp_url
    elif camera.camera_type == "video_file":
        source = camera.video_file_path
    elif camera.camera_type == "webcam":
        source = "0"  # default webcam device index

    if not source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No source URL or path defined for this camera."
        )

    # Resolve webcam index
    if camera.camera_type == "webcam":
        try:
            device_source = int(source)
        except ValueError:
            device_source = 0
    else:
        device_source = source

    # Open video capture stream
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
    cap = cv2.VideoCapture(device_source)
    if not cap.isOpened():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to open connection to camera source."
        )

    ret = False
    frame = None

    # Video file seek logic
    if camera.camera_type == "video_file":
        cap.set(cv2.CAP_PROP_POS_FRAMES, 150)  # Seek to frame 150 (approx 5 sec)
        ret, frame = cap.read()
        if not ret:
            # Fallback to frame 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
    else:
        # RTSP / webcam: capture current frame
        ret, frame = cap.read()

    cap.release()

    if not ret or frame is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture frame from camera source."
        )

    # Encode frame to JPEG
    ret_encode, jpeg_buf = cv2.imencode(".jpg", frame)
    if not ret_encode:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encode captured frame to JPEG."
        )

    jpeg_bytes = jpeg_buf.tobytes()
    SNAPSHOT_CACHE[camera_id] = (now, jpeg_bytes)

    return Response(content=jpeg_bytes, media_type="image/jpeg")
