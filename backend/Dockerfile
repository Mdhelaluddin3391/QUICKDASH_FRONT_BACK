# ==============================================================================
# PRODUCTION-GRADE DOCKERFILE FOR DJANGO + POSTGIS
# Optimized for Railway, AWS ECS, Docker Compose
# ==============================================================================

# Stage 1: Builder (compile Python dependencies)
FROM python:3.12-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libproj-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and build wheels
COPY backend/requirements.txt ./
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# ==============================================================================
# Stage 2: Runtime (minimal production image)
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production

# Set working directory
WORKDIR /app

# Install runtime dependencies only
# Removed 'netcat-openbsd' as internal healthcheck is removed
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    binutils \
    gdal-bin \
    libmagic1 \
    gosu \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /build/wheels /wheels

# Copy requirements
COPY backend/requirements.txt ./

# Install Python packages from wheels
RUN pip install --no-cache-dir /wheels/* \
    && pip install --no-cache-dir gunicorn uvicorn \
    && rm -rf /wheels

# Copy application code
COPY backend/ /app/

# Create non-root user for security
RUN groupadd --system --gid 1000 appgroup && \
    useradd --system --uid 1000 --gid 1000 appuser && \
    mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R appuser:appgroup /app

# Copy entrypoint script
COPY backend/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && \
    chown appuser:appgroup /entrypoint.sh

# Expose port (Documentation purpose mostly, Railway ignores this and injects PORT env var)
EXPOSE 5000

# --- FIX: REMOVED HEALTHCHECK ---
# Railway handles healthchecks automatically via HTTP requests.
# Hardcoding port 5000 here caused crashes because Railway uses random ports.
# --------------------------------

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["gunicorn"]