# Purpose: Containerize the Identity Resolution Service (ReID).
# Responsibilities:
# - Securely run the Identity Matcher daemon.
# - Optimize build caching using multi-stage builds.

# ==========================================
# STAGE 1: Builder
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install GCC and libpq-dev to compile the asyncpg PostgreSQL driver
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
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

# Install the minimal runtime library for PostgreSQL connections
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Bring over the compiled wheels
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels

# Copy the ReID source code
COPY ./src /app/src

RUN chown -R appuser:appgroup /app
USER appuser

# Health check — verifies the ReID Python process is alive.
# Headless daemon: uses process probe instead of HTTP endpoint.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD grep -q "src.main" /proc/1/cmdline || exit 1

# Principal Note: Run directly as a module to handle SIGTERM gracefully.
CMD ["python", "-m", "src.main"]
