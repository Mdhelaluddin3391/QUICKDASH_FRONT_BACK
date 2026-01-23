# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set environment variables for Python and Django
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production

# Set work directory
WORKDIR /app

# Install system dependencies
# - gcc, libpq-dev for PostgreSQL
# - netcat for health checks
# - binutils, libproj-dev, gdal-bin, libgdal-dev for GeoDjango
# - libmagic1 for file type detection
RUN apt-get update && apt-get install -y --no-install-recommends \
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
    && pip install gunicorn

# Copy application code
COPY . .

# Create non-root user with UID 1000 to match common host UID
# This prevents permission issues with volume mounts
RUN addgroup --system --gid 1000 appgroup && adduser --system --uid 1000 --gid 1000 appuser

# Create directories for static and media files
RUN mkdir -p /app/staticfiles /app/media

# Change ownership of app directory to appuser
# Note: This will be overridden by volume mounts, but ensures initial ownership
RUN chown -R appuser:appgroup /app

# Copy and set executable permissions for entrypoint script
COPY ./scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 5000

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
