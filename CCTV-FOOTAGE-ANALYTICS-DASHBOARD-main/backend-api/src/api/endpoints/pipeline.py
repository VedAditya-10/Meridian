"""
Purpose: Pipeline Management API — Video Upload & Live Camera Control.
Responsibilities:
- Accept uploaded video files and trigger the edge-node vision pipeline.
- Start / stop live camera (webcam / USB camera) feeds.
- Report the status of all currently running pipeline jobs.
- Run all CV pipelines in background threads so the async API stays responsive.
Dependencies: fastapi, python-multipart, edge-node pipeline (imported directly)
"""

import logging
import os
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["Pipeline Control"])

# ─────────────────────────────────────────────────────────────────────────────
# Temporary upload directory — files are deleted after processing completes
# ─────────────────────────────────────────────────────────────────────────────
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/cctv_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# In-memory job registry
# Key: camera_id (str)
# Value: PipelineJob instance
# ─────────────────────────────────────────────────────────────────────────────
_jobs: Dict[str, "PipelineJob"] = {}
_jobs_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

class PipelineJob:
    """Tracks one running vision pipeline (one camera source)."""

    def __init__(
        self,
        camera_id: str,
        store_id: str,
        source: str,
        source_type: Literal["file", "live"],
    ):
        self.camera_id = camera_id
        self.store_id = store_id
        self.source = source
        self.source_type = source_type
        self.status: str = "QUEUED"   # QUEUED | PROCESSING | COMPLETE | ERROR | STOPPED
        self.progress: float = 0.0
        self.error: Optional[str] = None
        self.started_at: float = time.time()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def stop(self):
        """Signal the pipeline to stop cleanly."""
        self._stop_event.set()

    def to_dict(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "store_id": self.store_id,
            "source_type": self.source_type,
            "source": self.source if self.source_type == "live" else Path(self.source).name,
            "status": self.status,
            "progress": round(self.progress, 1),
            "error": self.error,
            "started_at": self.started_at,
        }


class JobStatusResponse(BaseModel):
    camera_id: str
    store_id: str
    source_type: str
    source: str
    status: str
    progress: float
    error: Optional[str] = None
    started_at: float


class StartLiveRequest(BaseModel):
    camera_id: str
    store_id: str
    device_index: int = 0  # 0 = default webcam, 1 = second camera, etc.


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline runner — runs in a background thread
# ─────────────────────────────────────────────────────────────────────────────

def _run_pipeline_thread(job: PipelineJob):
    """
    Executes the VisionPipeline inside a daemon thread.
    Imports the edge-node pipeline module directly — this avoids a network call
    and means the entire CV stack runs inside the same container/process.
    """
    try:
        # Try multiple locations for the edge-node source code:
        # 1. Docker volume mount at /edge-node/src (set in docker-compose)
        # 2. Relative path from this file (for local dev outside Docker)
        edge_src_candidates = [
            Path("/edge-node/src"),                       # Docker volume mount
            Path(__file__).parents[4] / "edge-node" / "src",  # Local dev
        ]
        
        edge_src_found = False
        for candidate in edge_src_candidates:
            if candidate.exists() and (candidate / "pipeline.py").exists():
                if str(candidate) not in sys.path:
                    sys.path.insert(0, str(candidate))
                edge_src_found = True
                logger.info(f"Found edge-node source at: {candidate}")
                break
        
        if not edge_src_found:
            raise ImportError(
                "Edge-node source code not found. "
                "For GPU mode, run the pipeline from your host terminal instead. "
                "See the walkthrough for instructions."
            )

        from pipeline import VisionPipeline  # type: ignore

        redis_uri = os.getenv("REDIS_URI", "redis://redis:6379/0")

        pipeline = VisionPipeline(
            store_id=job.store_id,
            camera_id=job.camera_id,
            video_source=job.source,
            redis_uri=redis_uri,
            stop_event=job._stop_event,
            source_type=job.source_type,
        )

        # Wire the job progress callback into the pipeline
        def _on_progress(status: str, progress: float):
            job.status = status
            job.progress = progress

        pipeline.on_progress = _on_progress
        job.status = "PROCESSING"

        success = pipeline.run()

        if job._stop_event.is_set():
            job.status = "STOPPED"
        elif success:
            job.status = "COMPLETE"
            job.progress = 100.0
        else:
            job.status = "ERROR"
            job.error = "Pipeline returned failure."

    except Exception as exc:
        logger.error(f"Pipeline thread error for {job.camera_id}: {exc}", exc_info=True)
        job.status = "ERROR"
        job.error = str(exc)
    finally:
        # Clean up the uploaded temp file after processing
        if job.source_type == "file" and Path(job.source).exists():
            try:
                os.remove(job.source)
                logger.info(f"Cleaned up temp file: {job.source}")
            except Exception:
                pass

        with _jobs_lock:
            # Keep the job in the registry for status inspection but mark it done
            pass


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a video file and trigger pipeline processing",
    response_model=JobStatusResponse,
)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CCTV footage video file (.mp4, .avi, .mkv, .mov)"),
    camera_id: str = Form(..., description="Logical camera identifier, e.g. 'cam-1'"),
    store_id: str = Form(
        default="a1b2c3d4-0001-4000-8000-000000000001",
        description="Store UUID to attribute this footage to",
    ),
):
    """
    Accepts a video file upload and starts the vision pipeline asynchronously.
    The pipeline runs in a background thread — this endpoint returns immediately
    with a job descriptor. Poll GET /pipeline/status for progress.
    """
    # Validate file extension
    allowed_extensions = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".m4v"}
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(allowed_extensions)}",
        )

    # Reject if a job for this camera_id is already running
    with _jobs_lock:
        existing = _jobs.get(camera_id)
        if existing and existing.status in ("QUEUED", "PROCESSING"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Camera '{camera_id}' already has an active pipeline job. Stop it first.",
            )

    # Save the uploaded file to disk (streaming to avoid memory blow-up for large files)
    unique_name = f"{camera_id}_{uuid.uuid4().hex}{suffix}"
    dest_path = UPLOAD_DIR / unique_name

    try:
        with dest_path.open("wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                f.write(chunk)
        logger.info(f"Saved uploaded video: {dest_path} ({dest_path.stat().st_size / 1024 / 1024:.1f} MB)")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {exc}",
        )

    # Create job and start thread
    job = PipelineJob(
        camera_id=camera_id,
        store_id=store_id,
        source=str(dest_path),
        source_type="file",
    )
    with _jobs_lock:
        _jobs[camera_id] = job

    thread = threading.Thread(target=_run_pipeline_thread, args=(job,), daemon=True)
    job._thread = thread
    thread.start()

    logger.info(f"Started video pipeline job for camera '{camera_id}' from file '{file.filename}'")
    return JobStatusResponse(**job.to_dict())


@router.post(
    "/start-live",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a live camera / webcam feed",
    response_model=JobStatusResponse,
)
async def start_live_camera(req: StartLiveRequest):
    """
    Starts a continuous live capture from a camera device (webcam, USB camera).
    device_index=0 is the default system webcam.
    The pipeline loops indefinitely until POST /pipeline/stop is called.
    """
    with _jobs_lock:
        existing = _jobs.get(req.camera_id)
        if existing and existing.status in ("QUEUED", "PROCESSING"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Camera '{req.camera_id}' already has an active pipeline job.",
            )

    # OpenCV accepts integer device indices as video sources
    source = str(req.device_index)

    job = PipelineJob(
        camera_id=req.camera_id,
        store_id=req.store_id,
        source=source,
        source_type="live",
    )
    with _jobs_lock:
        _jobs[req.camera_id] = job

    thread = threading.Thread(target=_run_pipeline_thread, args=(job,), daemon=True)
    job._thread = thread
    thread.start()

    logger.info(f"Started live camera pipeline for camera '{req.camera_id}' (device index {req.device_index})")
    return JobStatusResponse(**job.to_dict())


@router.get(
    "/status",
    summary="Get status of all pipeline jobs",
    response_model=List[JobStatusResponse],
)
async def get_pipeline_status():
    """Returns all pipeline jobs (running, completed, or errored) in newest-first order."""
    with _jobs_lock:
        jobs = list(_jobs.values())
    return [JobStatusResponse(**j.to_dict()) for j in sorted(jobs, key=lambda j: -j.started_at)]


@router.post(
    "/stop/{camera_id}",
    summary="Stop a running pipeline job",
    status_code=status.HTTP_200_OK,
)
async def stop_pipeline(camera_id: str):
    """
    Signals a running pipeline to stop cleanly.
    For file pipelines this interrupts processing mid-video.
    For live pipelines this ends the capture loop.
    """
    with _jobs_lock:
        job = _jobs.get(camera_id)

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No job found for camera '{camera_id}'")

    if job.status not in ("QUEUED", "PROCESSING"):
        return {"message": f"Job for '{camera_id}' is already in terminal state: {job.status}"}

    job.stop()
    logger.info(f"Stop signal sent to pipeline job for camera '{camera_id}'")
    return {"message": f"Stop signal sent to '{camera_id}'. Status will update shortly."}


@router.delete(
    "/clear",
    summary="Clear all completed/errored/stopped jobs from the registry",
    status_code=status.HTTP_200_OK,
)
async def clear_completed_jobs():
    """Removes finished jobs from the in-memory registry to keep the status list clean."""
    with _jobs_lock:
        terminal_states = {"COMPLETE", "ERROR", "STOPPED"}
        to_remove = [cid for cid, j in _jobs.items() if j.status in terminal_states]
        for cid in to_remove:
            del _jobs[cid]
    return {"cleared": len(to_remove)}
