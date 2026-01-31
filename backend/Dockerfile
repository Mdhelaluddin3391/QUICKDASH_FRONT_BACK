# Use Python 3.12 slim image
FROM python:3.12-slim

# 1. Ye line add karne se 'debconf' wali red warnings chali jayengi
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production

# Set work directory
WORKDIR /app

# Install system dependencies
# '-qq' flag output ko thoda shant rakhta hai
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
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn uvicorn

# Copy application code
COPY . .

# Create non-root user
RUN addgroup --system --gid 1000 appgroup && adduser --system --uid 1000 --gid 1000 appuser

# Create directories for static and media
RUN mkdir -p /app/staticfiles /app/media

# Change ownership
RUN chown -R appuser:appgroup /app

# Script permissions
COPY ./scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 5000

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]