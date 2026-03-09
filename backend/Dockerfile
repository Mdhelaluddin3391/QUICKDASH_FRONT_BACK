FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libproj-dev \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_ENV=production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    binutils \
    gdal-bin \
    libmagic1 \
    redis-tools \
    netcat-openbsd \
    gosu \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir /wheels/* \
    && pip install --no-cache-dir gunicorn uvicorn \
    && rm -rf /wheels

COPY . /app/

RUN groupadd --system --gid 1000 appgroup && \
    useradd --system --uid 1000 --gid 1000 appuser && \
    mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R appuser:appgroup /app

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]