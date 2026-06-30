# Purpose: Containerize the Edge Node Vision Pipeline for GPU-accelerated environments.
# Responsibilities:
# - Pre-export ReID weights to ONNX inside a temporary build container.
# - Install all system dependencies required to decode video files via ffmpeg.
# - Run on NVIDIA GPU using CUDA.
# - Run as a non-root user for security.

# ==========================================
# STAGE 1: ONNX Weight Exporter
# ==========================================
FROM python:3.11-slim AS exporter

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU, scipy, opencv-python-headless, gdown, tensorboard, onnx, onnxscript, and torchreid to run the ONNX export script
RUN pip install --no-cache-dir torch torchvision --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir scipy opencv-python-headless gdown tensorboard onnx onnxscript torchreid

# Copy exporter script and run it
COPY ./scripts /app/scripts
RUN python scripts/export_fastreid_onnx.py


# ==========================================
# STAGE 2: Runner (GPU-accelerated)
# ==========================================
FROM ultralytics/ultralytics:latest

# Security: non-root user
RUN addgroup --system appgroup && adduser --system --group appuser

WORKDIR /app

# Install additional requirements (onnxruntime-gpu for ReID acceleration, redis, etc.)
RUN pip install --no-cache-dir \
    lapx>=0.5.5 \
    onnxruntime-gpu>=1.17.0 \
    redis>=5.0.1 \
    python-json-logger>=2.0.7

# Copy ONNX weights from exporter stage and source code
COPY --from=exporter /app/weights /app/weights
COPY ./src /app/src

RUN chown -R appuser:appgroup /app

# Drop root privileges
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD pgrep -f "src.main" || exit 1

# Execute the pipeline daemon
CMD ["python", "-m", "src.main"]
