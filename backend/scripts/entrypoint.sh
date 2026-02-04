#!/bin/sh
set -e

echo "🚀 Starting Django Production Entrypoint..."

# ------------------------------------------------------------
# 1. ENV VALIDATION
# ------------------------------------------------------------
if [ -z "$DJANGO_SECRET_KEY" ]; then
    echo "❌ DJANGO_SECRET_KEY is required"
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL is required"
    exit 1
fi

echo "✅ Environment validated"

# ------------------------------------------------------------
# 2. WAIT FOR POSTGRES
# ------------------------------------------------------------
echo "⏳ Waiting for PostgreSQL..."

MAX_RETRIES=30
COUNT=0

until python3 - <<'EOF'
import psycopg2, os, sys
try:
    psycopg2.connect(os.getenv("DATABASE_URL"))
    sys.exit(0)
except Exception:
    sys.exit(1)
EOF
do
    COUNT=$((COUNT+1))
    if [ $COUNT -ge $MAX_RETRIES ]; then
        echo "❌ PostgreSQL not available after retries"
        exit 1
    fi
    echo "⏳ Postgres not ready ($COUNT/$MAX_RETRIES)..."
    sleep 2
done

echo "✅ PostgreSQL ready"

# ------------------------------------------------------------
# 3. RUN MIGRATIONS
# ------------------------------------------------------------
echo "🧱 Running database migrations..."
python manage.py migrate --noinput
echo "✅ Migrations completed"


# echo "👤 Creating superuser if needed..."
# python manage.py create_superuser_auto



# ------------------------------------------------------------
# 4. COLLECT STATIC FILES
# ------------------------------------------------------------
echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput --clear
echo "✅ Static files collected"

# ------------------------------------------------------------
# 5. START GUNICORN
# ------------------------------------------------------------
PORT=${PORT:-10000}     # Render usually uses 10000
WORKERS=${WORKERS:-3}

echo "🚀 Starting Gunicorn on port $PORT..."

exec gunicorn config.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --workers $WORKERS \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
