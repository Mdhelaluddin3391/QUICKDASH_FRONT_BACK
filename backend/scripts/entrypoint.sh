#!/bin/sh
set -e

echo "Starting Backend Entrypoint..."

# Wait for PostgreSQL
if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for PostgreSQL..."
  while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 0.5
  done
  echo "PostgreSQL is available"
fi

# Run tasks ONLY on primary container
if [ "$IS_PRIMARY" = "1" ]; then
  echo "Collecting static files..."
  python manage.py collectstatic --noinput --clear
fi

# Start ASGI Server (for WebSockets support)
if [ "$RUN_GUNICORN" = "1" ]; then
  echo "Starting ASGI Server on 0.0.0.0:5000"
  exec gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:5000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
else
  echo "Starting worker/beat process"
  exec "$@"
fi