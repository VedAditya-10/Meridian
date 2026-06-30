"""
Purpose: Entry point for the Edge Node Vision Pipeline.
Responsibilities:
- Parse configuration from environment variables.
- Support two operating modes:
    1. Single camera mode (CAMERA_ID + VIDEO_PATH or RTSP_URL)
    2. Sequential multi-camera mode (CAMERA_LIST env var)
- In both modes, supports 'file' and 'live' source types.
- Publishes raw telemetry to Redis for downstream services.

Usage (Docker):
    docker run -e CAMERA_LIST="cam-1:/videos/entrance.mp4,cam-2:/videos/floor.mp4" edge-node
    docker run -e CAMERA_ID=cam-1 -e VIDEO_PATH=/videos/test.mp4 edge-node
    docker run -e CAMERA_ID=cam-live -e DEVICE_INDEX=0 -e SOURCE_TYPE=live edge-node
"""

import os
import logging
import time
import threading

from src.pipeline import VisionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("edge-node.main")


def main():
    logger.info("Starting Edge Node Service...")

    redis_uri = os.getenv("REDIS_URI", "redis://redis:6379/0")
    store_id = os.getenv("STORE_ID", "a1b2c3d4-0001-4000-8000-000000000001")

    # Detect source type: "file" (default) or "live" (webcam/USB camera)
    source_type = os.getenv("SOURCE_TYPE", "file")

    # ──────────────────────────────────────────────────────────────────────
    # Mode 1: Sequential multi-camera (CAMERA_LIST env var)
    # Format: "cam-1:/videos/entrance.mp4,cam-2:/videos/floor.mp4"
    # ──────────────────────────────────────────────────────────────────────
    camera_list_env = os.getenv("CAMERA_LIST", "")

    if camera_list_env:
        pairs = [p.strip() for p in camera_list_env.split(",") if p.strip()]
        cameras = []
        for pair in pairs:
            parts = pair.split(":", 1)
            if len(parts) == 2:
                cameras.append((parts[0].strip(), parts[1].strip()))
            else:
                logger.warning(f"Invalid camera pair format: {pair}. Expected 'cam_id:/path/to/video'")

        logger.info(f"Sequential processing mode: {len(cameras)} cameras to process")

        for i, (camera_id, video_source) in enumerate(cameras):
            logger.info(f"=== Processing Camera {i+1}/{len(cameras)}: {camera_id} ===")

            stop_event = threading.Event()

            pipeline = VisionPipeline(
                store_id=store_id,
                camera_id=camera_id,
                video_source=video_source,
                redis_uri=redis_uri,
                source_type=source_type,
                stop_event=stop_event,
            )

            success = pipeline.run()

            if success:
                logger.info(f"Camera {camera_id} completed successfully.")
            else:
                logger.error(f"Camera {camera_id} failed.")

            # Brief pause between cameras to let the ReID service catch up
            if i < len(cameras) - 1:
                logger.info("Pausing 5 seconds before next camera...")
                time.sleep(5)

        logger.info("=== All cameras processed. Edge node shutting down. ===")

    else:
        # ──────────────────────────────────────────────────────────────────
        # Mode 2: Single camera (backward compatible)
        # ──────────────────────────────────────────────────────────────────
        camera_id = os.getenv("CAMERA_ID", "cam-1")
        video_path = os.getenv("VIDEO_PATH", "")
        rtsp_url = os.getenv("RTSP_URL", "")
        device_index = os.getenv("DEVICE_INDEX", "")

        # Determine source
        if source_type == "live":
            source = device_index if device_index else "0"
        else:
            source = video_path if video_path else rtsp_url

        if not source:
            logger.critical("No VIDEO_PATH, RTSP_URL, or DEVICE_INDEX provided!")
            return

        stop_event = threading.Event()

        pipeline = VisionPipeline(
            store_id=store_id,
            camera_id=camera_id,
            video_source=source,
            redis_uri=redis_uri,
            source_type=source_type,
            stop_event=stop_event,
        )

        pipeline.run()


if __name__ == "__main__":
    main()
