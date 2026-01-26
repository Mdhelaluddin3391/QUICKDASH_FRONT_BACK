#!/bin/sh
set -e

echo "Starting Entrypoint..."

# ------------------------------------------------------------------------------
# 1. WAIT FOR DATABASES (Postgres & Redis)
# ------------------------------------------------------------------------------
if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for PostgreSQL ($POSTGRES_HOST:$POSTGRES_PORT)..."
  while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 0.5
  done
  echo "PostgreSQL is available"
fi

if [ -n "$REDIS_HOST" ]; then
  echo "Waiting for Redis ($REDIS_HOST:$REDIS_PORT)..."
  while ! nc -z "$REDIS_HOST" "$REDIS_PORT"; do
    sleep 0.5
  done
  echo "Redis is available"
fi

# ------------------------------------------------------------------------------
# 2. FIX PERMISSIONS
# ------------------------------------------------------------------------------
# Fix Permissions (Root task)
echo "Fixing permissions..."
chown -R appuser:appgroup /app/staticfiles /app/media || true

# ------------------------------------------------------------------------------
# 3. RUN MIGRATIONS & STATIC (Primary Container Only)
# ------------------------------------------------------------------------------
if [ "$IS_PRIMARY" = "1" ]; then
  echo "Running migrations..."
  gosu appuser python manage.py migrate --noinput
  
  echo "Collecting static files..."
  gosu appuser python manage.py collectstatic --noinput --clear
fi

# ------------------------------------------------------------------------------
# 4. START PROCESS
# ------------------------------------------------------------------------------
if [ "$RUN_GUNICORN" = "1" ]; then
  echo "Starting ASGI Server on 0.0.0.0:5000 as appuser"
  exec gosu appuser gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:5000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
else
  # This executes the command passed from docker-compose (e.g., celery worker)
  echo "Starting auxiliary process (Celery Worker/Beat) as appuser"
  echo "Command: $@"
  exec gosu appuser "$@"
fi