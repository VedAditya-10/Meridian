"""
Purpose: Core Vision Pipeline for edge-node processing.
Responsibilities:
- Capture frames from video files OR live camera devices (webcam/USB CCTV).
- Detect and track people using YOLOv8n + ByteTrack.
- Extract 2048-d person re-identification embeddings via ResNet50 ONNX model.
- Publish raw telemetry to Redis Stream 'telemetry_raw'.
- Publish processing status to Redis Pub/Sub 'pipeline_status'.
- Support graceful stop via threading.Event for live mode.

Source modes:
  "file"  — process a video file from start to finish, then exit.
  "live"  — continuous real-time capture loop; runs until stop_event is set.
"""

import logging
import threading
import time
import json
from typing import Callable, Literal, Optional

import cv2
import numpy as np
import redis
import onnxruntime as ort
from ultralytics import YOLO

logger = logging.getLogger("edge-node.pipeline")


class TelemetryClient:
    def __init__(self, redis_uri: str):
        self.client = redis.from_url(redis_uri)
        self.stream_name = "telemetry_raw"

    def publish(self, payload: dict):
        try:
            redis_payload = {
                "store_id":     payload["store_id"],
                "camera_id":    payload["camera_id"],
                "session_id":   payload["session_id"],
                "track_id":     str(payload["track_id"]),
                "bbox":         json.dumps(payload["bbox"]),
                "frame_width":  str(payload["frame_width"]),
                "frame_height": str(payload["frame_height"]),
                "embedding":    json.dumps(payload["embedding"]) if payload["embedding"] else "",
                "quality_score": str(payload["quality_score"]),
                "timestamp":    str(payload["timestamp"]),
            }
            # Trim stream to ~50k messages to prevent unbounded growth
            self.client.xadd(self.stream_name, redis_payload, maxlen=50000, approximate=True)
            logger.debug(f"Published telemetry for track_id {payload['track_id']}")
        except Exception as e:
            logger.error(f"Failed to publish telemetry: {e}")

    def publish_status(self, store_id: str, camera_id: str, status: str, progress: float = 0.0):
        """Publish processing status for dashboard monitoring."""
        try:
            status_payload = {
                "store_id":  store_id,
                "camera_id": camera_id,
                "status":    status,
                "progress":  str(progress),
                "timestamp": str(time.time()),
            }
            self.client.publish("pipeline_status", json.dumps(status_payload))
        except Exception as e:
            logger.error(f"Failed to publish status: {e}")


class ReIDExtractor:
    """
    Person re-identification feature extractor.
    Uses ResNet50 pretrained on ImageNet, exported to ONNX format.
    Outputs a 2048-dimensional L2-normalized embedding per person crop.
    """

    def __init__(self):
        logger.info("Loading ResNet50 ONNX ReID Extractor...")
        import os
        import sys

        # On Windows, try to find PyTorch's lib directory to load bundled CUDA/cuDNN DLLs
        if sys.platform.startswith("win"):
            try:
                import torch
                torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
                if os.path.exists(torch_lib):
                    logger.info(f"Adding PyTorch DLL directory to search path: {torch_lib}")
                    os.add_dll_directory(torch_lib)
                    os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
            except ImportError:
                logger.warning("PyTorch not found on host; proceeding without PyTorch DLL paths.")
            except Exception as e:
                logger.error(f"Failed to load PyTorch DLL directory: {e}")

        model_path = os.getenv("REID_MODEL_PATH", "weights/fastreid_r50.onnx")
        if not os.path.exists(model_path):
            logger.critical(f"ReID model weights file not found at: {model_path}")
            raise FileNotFoundError(f"ReID model weights file '{model_path}' not found!")
        
        providers = []
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
        providers.append("CPUExecutionProvider")
        
        logger.info(f"ONNX Runtime execution providers: {providers}")
        self.session = ort.InferenceSession(model_path, providers=providers)
        self._log_gpu_status()
        self.input_name = self.session.get_inputs()[0].name
        
        # Determine dimension dynamically from the ONNX model output
        self.embedding_dim = self.session.get_outputs()[0].shape[1]
        logger.info(f"Loaded ReID model {model_path} with output dimension: {self.embedding_dim}")
        
        # Preprocessing normalization constants (same as ImageNet/Market1501)
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def _log_gpu_status(self):
        import subprocess
        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader"],
                capture_output=True, text=True
            )
            logger.info(f"GPU Status: {result.stdout.strip()}")
        except Exception:
            logger.warning("nvidia-smi not available — cannot confirm GPU status")

    def extract(self, crop: np.ndarray) -> np.ndarray:
        try:
            # 1. Resize to (width=128, height=256)
            crop_resized = cv2.resize(crop, (128, 256), interpolation=cv2.INTER_LINEAR)
            
            # 2. Convert BGR to RGB
            crop_rgb = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2RGB)
            
            # 3. Normalize to [0.0, 1.0] and apply mean/std
            crop_normalized = crop_rgb.astype(np.float32) / 255.0
            crop_normalized = (crop_normalized - self.mean) / self.std
            
            # 4. Transpose from HWC (256, 128, 3) to CHW (3, 256, 128)
            crop_chw = np.transpose(crop_normalized, (2, 0, 1))
            
            # 5. Add batch dimension -> (1, 3, 256, 128)
            input_tensor = np.expand_dims(crop_chw, axis=0)
            
            # 6. Run inference
            outputs = self.session.run(None, {self.input_name: input_tensor})
            embedding = outputs[0][0] # shape (embedding_dim,)
            
            # 7. L2 Normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding
        except Exception as e:
            logger.error(f"Error extracting embedding: {e}")
            return np.zeros(self.embedding_dim, dtype=np.float32)


def _compute_quality_score(crop: np.ndarray) -> float:
    """
    Combined quality score: resolution adequacy + sharpness (Laplacian variance).
    Rejects blurry or too-small crops that would pollute the embedding database.
    Returns 0.0 for rejected crops, 0.0-1.0 for accepted ones.
    """
    h, w = crop.shape[:2]
    if h < 128 or w < 64:
        return 0.0

    resolution_score = min(1.0, (h * w) / (256 * 128))

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    sharpness_score = min(1.0, sharpness / 500.0)

    return round(0.6 * resolution_score + 0.4 * sharpness_score, 3)


class VisionPipeline:
    def __init__(
        self,
        store_id: str,
        camera_id: str,
        video_source: str,
        redis_uri: str,
        source_type: Literal["file", "live"] = "file",
        stop_event: Optional[threading.Event] = None,
        on_progress: Optional[Callable[[str, float], None]] = None,
    ):
        self.store_id = store_id
        self.camera_id = camera_id
        self.video_source = video_source
        self.source_type = source_type

        # stop_event is set externally to interrupt a running pipeline cleanly
        self._stop_event = stop_event or threading.Event()

        # Optional progress callback so the API job tracker can update its state
        self.on_progress = on_progress or (lambda status, progress: None)

        logger.info(f"Initializing VisionPipeline | camera={camera_id} | mode={source_type}")
        import uuid
        self.session_id = str(uuid.uuid4())
        self.telemetry_client = TelemetryClient(redis_uri)
        self.extractor = ReIDExtractor()

        import os
        from pathlib import Path
        logger.info("Loading YOLOv8n detector...")
        yolo_path = "yolov8n.pt"
        candidates = [
            Path("yolov8n.pt"),
            Path("../yolov8n.pt"),
            Path(__file__).parents[1] / "yolov8n.pt",
            Path(__file__).parents[2] / "yolov8n.pt",
        ]
        for cand in candidates:
            if cand.exists():
                yolo_path = str(cand.resolve())
                logger.info(f"Found YOLOv8 weights at: {yolo_path}")
                break
        else:
            logger.warning("YOLOv8 weights 'yolov8n.pt' not found in search paths. Ultralytics will attempt to download them.")
        self.detector = YOLO(yolo_path)

        # For file mode: 2 FPS effective to keep CPU load manageable
        # For live mode: 5 FPS effective to drastically reduce CPU/GPU load
        self.target_fps = 2 if source_type == "file" else 5

        # Track-specific embedding cache: track_id -> last_seen_timestamp
        # Prevents re-extracting embeddings for the same ongoing track (saves ~8ms per frame)
        self.extracted_tracks: dict = {}

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────────

    def run(self) -> bool:
        """Dispatch to file or live mode."""
        if self.source_type == "file":
            return self._run_file_mode()
        else:
            return self._run_live_mode()

    # ─────────────────────────────────────────────────────────────────────────
    # File mode — process a video file from start to finish
    # ─────────────────────────────────────────────────────────────────────────

    def _run_file_mode(self) -> bool:
        """
        Reads a video file frame-by-frame, sampling at target_fps.
        Emits COMPLETE when done or STOPPED if stop_event fires.
        """
        logger.info(f"[FILE] Starting: camera={self.camera_id} source={self.video_source}")

        # OpenCV can open both local file paths and integer device indices as strings
        source = self.video_source
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.critical(f"Failed to open video source: {source}")
            self.telemetry_client.publish_status(self.store_id, self.camera_id, "ERROR")
            self.on_progress("ERROR", 0.0)
            return False

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_skip = max(1, int(video_fps / self.target_fps))

        logger.info(
            f"[FILE] {total_frames} frames @ {video_fps:.1f} FPS → "
            f"sampling every {frame_skip} frames ({self.target_fps} FPS effective)"
        )
        self.telemetry_client.publish_status(self.store_id, self.camera_id, "PROCESSING", 0.0)
        self.on_progress("PROCESSING", 0.0)

        frame_count = 0
        processed_count = 0

        try:
            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    logger.info(
                        f"[FILE] {self.camera_id} complete — "
                        f"processed {processed_count}/{frame_count} frames"
                    )
                    break

                frame_count += 1
                if frame_count % frame_skip != 0:
                    continue

                current_time = time.time()
                self._process_frame(frame, current_time)
                processed_count += 1

                if processed_count % 50 == 0:
                    progress = (frame_count / total_frames * 100.0) if total_frames > 0 else 0.0
                    logger.info(f"[FILE] {self.camera_id} progress: {progress:.1f}%")
                    self.telemetry_client.publish_status(self.store_id, self.camera_id, "PROCESSING", progress)
                    self.on_progress("PROCESSING", progress)

                # Throttle to avoid burning 100% CPU on file processing
                elapsed = time.time() - current_time
                sleep_time = max(0.0, (1.0 / self.target_fps) - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info(f"[FILE] {self.camera_id} interrupted by user")
        finally:
            cap.release()
            import os
            if not os.path.exists('/.dockerenv'):
                cv2.destroyAllWindows()

        if self._stop_event.is_set():
            self.telemetry_client.publish_status(self.store_id, self.camera_id, "STOPPED")
            self.on_progress("STOPPED", 0.0)
            return False

        self.telemetry_client.publish_status(self.store_id, self.camera_id, "COMPLETE", 100.0)
        self.on_progress("COMPLETE", 100.0)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Live mode — continuous real-time capture from a camera device
    # ─────────────────────────────────────────────────────────────────────────

    def _run_live_mode(self) -> bool:
        """
        Opens a camera device (webcam / USB camera) and processes frames
        continuously until stop_event is set from the outside.
        """
        # video_source is the device index (e.g. "0" for default webcam)
        try:
            device_index = int(self.video_source)
        except ValueError:
            device_index = 0

        logger.info(f"[LIVE] Starting: camera={self.camera_id} device_index={device_index}")

        cap = cv2.VideoCapture(device_index)
        if not cap.isOpened():
            logger.critical(f"Failed to open camera device index {device_index}")
            self.telemetry_client.publish_status(self.store_id, self.camera_id, "ERROR")
            self.on_progress("ERROR", 0.0)
            return False

        # Request a reasonable resolution from the hardware
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        actual_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        logger.info(f"[LIVE] Camera opened: {cap.get(cv2.CAP_PROP_FRAME_WIDTH):.0f}x"
                    f"{cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f} @ {actual_fps:.1f} FPS")

        self.telemetry_client.publish_status(self.store_id, self.camera_id, "PROCESSING", 0.0)
        self.on_progress("PROCESSING", 0.0)

        frame_count = 0
        last_status_time = time.time()
        last_process_time = 0.0
        STATUS_INTERVAL_SEC = 5.0  # Broadcast live status every 5 seconds

        try:
            while not self._stop_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"[LIVE] {self.camera_id}: failed to read frame (camera disconnected?)")
                    time.sleep(0.5)
                    continue

                frame_count += 1
                current_time = time.time()

                # Skip processing if we exceed the target FPS (e.g. 5 FPS)
                if self.target_fps is not None:
                    if current_time - last_process_time < (1.0 / self.target_fps):
                        continue

                self._process_frame(frame, current_time)
                last_process_time = current_time

                # Broadcast a keep-alive status every STATUS_INTERVAL_SEC
                if current_time - last_status_time >= STATUS_INTERVAL_SEC:
                    self.telemetry_client.publish_status(
                        self.store_id, self.camera_id, "PROCESSING", 0.0
                    )
                    self.on_progress("PROCESSING", 0.0)
                    last_status_time = current_time

        except KeyboardInterrupt:
            logger.info(f"[LIVE] {self.camera_id} interrupted by user")
        finally:
            cap.release()
            import os
            if not os.path.exists('/.dockerenv'):
                cv2.destroyAllWindows()
            logger.info(f"[LIVE] {self.camera_id} camera released after {frame_count} frames")

        self.telemetry_client.publish_status(self.store_id, self.camera_id, "STOPPED")
        self.on_progress("STOPPED", 0.0)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Shared frame processing
    # ─────────────────────────────────────────────────────────────────────────

    def _process_frame(self, frame: np.ndarray, timestamp: float):
        """
        Runs YOLOv8 + ByteTrack on one frame.
        For each detected person: computes quality score, conditionally extracts
        a ReID embedding, and publishes telemetry to Redis.
        """
        results = self.detector.track(
            frame, tracker="bytetrack.yaml", persist=True, classes=[0], verbose=False
        )

        if not results or results[0].boxes is None or results[0].boxes.id is None:
            import os
            if not os.path.exists('/.dockerenv') and os.getenv("SHOW_VIDEO", "true").lower() == "true":
                cv2.imshow(f"Store Intelligence - Camera: {self.camera_id}", frame)
                cv2.waitKey(1)
            return

        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.cpu().numpy()

        h, w = frame.shape[:2]

        # Expire stale track cache entries (person left camera view >15 s ago)
        for tid, t_last in list(self.extracted_tracks.items()):
            if timestamp - t_last > 15.0:
                self.extracted_tracks.pop(tid, None)

        for i in range(len(boxes)):
            x1, y1, x2, y2 = map(int, boxes[i])
            track_id = int(track_ids[i])

            # Clamp to frame boundaries
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if track_id in self.extracted_tracks:
                # Already have a good embedding for this track — reuse it
                embedding = None
                quality_score = 0.0
                self.extracted_tracks[track_id] = timestamp
            else:
                crop = frame[y1:y2, x1:x2]
                quality_score = _compute_quality_score(crop)

                if quality_score <= 0.0:
                    embedding = None
                else:
                    embedding = self.extractor.extract(crop)
                    if quality_score > 0.4:
                        self.extracted_tracks[track_id] = timestamp

            self.telemetry_client.publish({
                "store_id":     self.store_id,
                "camera_id":    self.camera_id,
                "session_id":   self.session_id,
                "track_id":     track_id,
                "bbox":         {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                "frame_width":  w,
                "frame_height": h,
                "embedding":    embedding.tolist() if embedding is not None else None,
                "quality_score": quality_score,
                "timestamp":    timestamp,
            })

        # Draw visualization if enabled
        import os
        if not os.path.exists('/.dockerenv') and os.getenv("SHOW_VIDEO", "true").lower() == "true":
            vis_frame = frame.copy()
            for i in range(len(boxes)):
                x1, y1, x2, y2 = map(int, boxes[i])
                track_id = int(track_ids[i])
                
                # Draw bounding box
                cv2.rectangle(vis_frame, (x1, y1), (x2, y2), (241, 102, 99), 2)
                
                # Draw track ID label
                label = f"ID: {track_id}"
                (w_label, h_label), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(vis_frame, (x1, y1 - h_label - 6), (x1 + w_label + 6, y1), (241, 102, 99), cv2.FILLED)
                cv2.putText(vis_frame, label, (x1 + 3, y1 - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            cv2.imshow(f"Store Intelligence - Camera: {self.camera_id}", vis_frame)
            cv2.waitKey(1)
