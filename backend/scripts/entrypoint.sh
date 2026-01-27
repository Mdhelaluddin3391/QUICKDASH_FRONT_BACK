#!/bin/sh
set -e

echo "🚀 Starting Entrypoint..."

# --------------------------------------------------
# 1. WAIT FOR POSTGRES
# --------------------------------------------------
if [ -n "$POSTGRES_HOST" ]; then
  echo "⏳ Waiting for PostgreSQL ($POSTGRES_HOST:$POSTGRES_PORT)..."
  while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 0.5
  done
  echo "✅ PostgreSQL is available"
fi

# --------------------------------------------------
# 2. WAIT FOR REDIS
# --------------------------------------------------
if [ -n "$REDIS_URL" ]; then
  echo "⏳ Waiting for Redis..."
  until redis-cli -u "$REDIS_URL" ping | grep -q PONG; do
    sleep 0.5
  done
  echo "✅ Redis is available"
fi

# --------------------------------------------------
# 3. FIX PERMISSIONS
# --------------------------------------------------
echo "🔐 Fixing permissions..."
chown -R appuser:appgroup /app/staticfiles /app/media || true

# --------------------------------------------------
# 4. MIGRATIONS & STATIC (PRIMARY ONLY)
# --------------------------------------------------
if [ "$IS_PRIMARY" = "1" ]; then
  echo "🗄 Running migrations..."
  gosu appuser python manage.py migrate --noinput

  echo "🎨 Collecting static files..."
  gosu appuser python manage.py collectstatic --noinput --clear
fi

# --------------------------------------------------
# 5. START SERVER
# --------------------------------------------------
if [ "$RUN_GUNICORN" = "1" ]; then
  echo "🌐 Starting Gunicorn ASGI server"
  exec gosu appuser gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
else
  echo "⚙️ Starting auxiliary process"
  exec "$@"
fi
