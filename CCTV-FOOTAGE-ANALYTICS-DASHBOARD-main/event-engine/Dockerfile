# Purpose: Containerize the highly-performant Event Engine.
# Responsibilities:
# - Provide a minimal, secure runtime for the Python worker daemon.
# - Ensure no unnecessary OS dependencies are shipped to production.

# ==========================================
# STAGE 1: Builder
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install GCC purely for compiling the Shapely C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# ==========================================
# STAGE 2: Runner
# ==========================================
FROM python:3.11-slim

# Secure non-root daemon user
RUN addgroup --system appgroup && adduser --system --group appuser

WORKDIR /app

# Bring over the compiled wheels (containing the optimized Shapely binaries)
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels

# Copy only the source code needed for the Event Engine
COPY ./src /app/src

RUN chown -R appuser:appgroup /app
USER appuser

# Health check — verifies the Python process is alive.
# The event engine is a headless daemon (no HTTP server), so we check
# that the main process is running via a simple process probe.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD grep -q "src.main" /proc/1/cmdline || exit 1

# Principal Note: The Event Engine is a long-running daemon, not a web server.
# We invoke it directly as a Python module to ensure it receives OS signals properly.
CMD ["python", "-m", "src.main"]
