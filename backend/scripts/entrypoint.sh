#!/bin/sh
set -e

echo "🚀 Starting Entrypoint..."

# ------------------------------------------------------------
# 1. ENV VALIDATION
# ------------------------------------------------------------
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL is required"
    exit 1
fi

# ------------------------------------------------------------
# 2. WAIT FOR POSTGRES
# ------------------------------------------------------------
echo "⏳ Waiting for PostgreSQL..."
until python3 - <<'EOF'
import psycopg2, os, sys
try:
    psycopg2.connect(os.getenv("DATABASE_URL"))
    sys.exit(0)
except Exception:
    sys.exit(1)
EOF
do
    echo "⏳ Postgres not ready, sleeping..."
    sleep 2
done
echo "✅ PostgreSQL ready"

# ------------------------------------------------------------
# 3. RUN MIGRATIONS
# ------------------------------------------------------------
echo "🧱 Running database migrations..."
python manage.py migrate --noinput
echo "✅ Migrations completed"

# Create superuser if configured (Optional, safe to keep)
if [ "$CREATE_SUPERUSER" = "True" ]; then
    python manage.py create_superuser_auto || true
fi

# Collect static files
echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput --clear

# ------------------------------------------------------------
# 4. EXECUTE COMMAND
# ------------------------------------------------------------
# Agar command arguments ($@) pass kiye gaye hain (jaise local dev mein runserver), toh wo run karein.
if [ "$#" -gt 0 ]; then
    echo "⚙️ Executing command: $@"
    exec "$@"
else
    # Default Production Command (Gunicorn)
    PORT=${PORT:-8000}
    WORKERS=${WORKERS:-3}
    echo "🚀 Starting Gunicorn on port $PORT..."
    exec gunicorn config.asgi:application \
        -k uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:$PORT \
        --workers $WORKERS \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
fi