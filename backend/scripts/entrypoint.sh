#!/bin/sh
set -e

echo "🚀 Starting Backend Entrypoint..."

# --------------------------------------------------
# Wait for PostgreSQL
# --------------------------------------------------
if [ -n "$POSTGRES_HOST" ]; then
  echo "⏳ Waiting for PostgreSQL..."
  while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
    sleep 0.5
  done
  echo "✅ PostgreSQL is available"
fi

# --------------------------------------------------
# Run migrations ONLY on primary container
# --------------------------------------------------
if [ "$IS_PRIMARY" = "1" ]; then
  echo "📦 Skipping automatic migrations (Manual Mode Enabled)..."
  
  # 👇 यह लाइन कमेंट कर दी गई है ताकि ऑटो-माइग्रेशन न हो
  # python manage.py migrate --noinput

  echo "🎨 Collecting static files (PRIMARY)..."
  python manage.py collectstatic --noinput --clear
else
  echo "⏭️ Skipping migrations (NOT PRIMARY)"
fi

# --------------------------------------------------
# Start Gunicorn ONLY for backend
# --------------------------------------------------
if [ "$RUN_GUNICORN" = "1" ]; then
  echo "🔥 Starting Gunicorn on 0.0.0.0:5000"
  exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:5000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
else
  echo "⚙️ Starting worker/beat process"
  exec "$@"
fi