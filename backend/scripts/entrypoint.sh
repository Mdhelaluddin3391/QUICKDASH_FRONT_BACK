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

# Fix Permissions (Root का काम)
# यह line ensure करती है कि host volumes पर appuser लिख सके
echo "Fixing permissions..."
chown -R appuser:appgroup /app/staticfiles /app/media || true

# Run tasks ONLY on primary container
if [ "$IS_PRIMARY" = "1" ]; then
  echo "Collecting static files..."
  # gosu appuser का मतलब: यह कमांड appuser बनकर चलाओ
  gosu appuser python manage.py collectstatic --noinput --clear
fi

# Start Server (Switch user to appuser)
if [ "$RUN_GUNICORN" = "1" ]; then
  echo "Starting ASGI Server on 0.0.0.0:5000 as appuser"
  # 'exec gosu appuser' से पूरी प्रोसेस अब appuser बन जाएगी
  exec gosu appuser gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:5000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
else
  echo "Starting worker/beat process as appuser"
  exec gosu appuser "$@"
fi