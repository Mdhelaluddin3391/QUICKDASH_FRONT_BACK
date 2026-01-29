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

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
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

# Install Python packages from wheels (fast, no compilation)
RUN pip install --no-cache-dir /wheels/* \
    && pip install --no-cache-dir gunicorn uvicorn \
    && rm -rf /wheels

# Copy application code (IMPORTANT: /app/manage.py exists)
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

# Expose port
EXPOSE 5000

# Health check (fast endpoint check)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD netcat -z localhost 5000 || exit 1

# Switch to non-root user
USER appuser

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden by docker-compose or orchestrator)
CMD ["gunicorn"]
