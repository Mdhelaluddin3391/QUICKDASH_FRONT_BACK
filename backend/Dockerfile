# ------------------------------------------------------------
# Base image
# ------------------------------------------------------------
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production

# ------------------------------------------------------------
# Work directory
# ------------------------------------------------------------
WORKDIR /app

# ------------------------------------------------------------
# System dependencies
# ------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends -qq \
    gcc \
    libpq-dev \
    netcat-openbsd \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    libmagic1 \
    gosu \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Python dependencies (IMPORTANT: backend/requirements.txt)
# ------------------------------------------------------------
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn uvicorn

# ------------------------------------------------------------
# 🔥 COPY ONLY BACKEND CODE INTO /app
# This ensures: /app/manage.py exists
# ------------------------------------------------------------
COPY backend/ /app/

# ------------------------------------------------------------
# Create non-root user
# ------------------------------------------------------------
RUN addgroup --system --gid 1000 appgroup \
    && adduser --system --uid 1000 --gid 1000 appuser

# ------------------------------------------------------------
# Static & media directories
# ------------------------------------------------------------
RUN mkdir -p /app/staticfiles /app/media
RUN chown -R appuser:appgroup /app

# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------
COPY backend/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ------------------------------------------------------------
# Expose port
# ------------------------------------------------------------
EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
