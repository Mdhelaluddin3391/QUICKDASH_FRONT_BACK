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
# 2. FIX PERMISSIONS (Since we start as root)
# ------------------------------------------------------------
# Docker volumes runtime par mount hote hain, isliye yahan chown zaroori hai
echo "🔧 Fixing permissions for static and media..."
chown -R appuser:appgroup /app/staticfiles /app/media /app/logs

# ------------------------------------------------------------
# 3. WAIT FOR POSTGRES
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
# 4. RUN MIGRATIONS & COLLECTSTATIC (Conditional)
# ------------------------------------------------------------
# Agar command 'celery' nahi hai, tabhi ye steps run karein.
# Isse race condition (DuplicateTable error) bachegi.
if [ "$1" != "celery" ]; then
    echo "🧱 Running database migrations..."
    # Run as appuser to avoid permission issues with generated files
    gosu appuser python manage.py migrate --noinput
    echo "✅ Migrations completed"

    # --- AUTO SUPERUSER CREATION ---
    echo "👤 Checking/Creating Superuser..."
    gosu appuser python manage.py create_superuser_auto || true
    # -------------------------------

    echo "🎨 Collecting static files..."
    gosu appuser python manage.py collectstatic --noinput --clear
else
    echo "⏩ Skipping migrations for worker process..."
fi

# ------------------------------------------------------------
# 5. EXECUTE COMMAND (Drop Privileges)
# ------------------------------------------------------------
# Agar command arguments ($@) pass kiye gaye hain (jaise runserver ya celery)
if [ "$#" -gt 0 ]; then
    echo "⚙️ Executing command as appuser: $@"
    exec gosu appuser "$@"
else
    # Default Production Command (Gunicorn)
    PORT=${PORT:-8000}
    WORKERS=${WORKERS:-3}
    echo "🚀 Starting Gunicorn on port $PORT..."
    exec gosu appuser gunicorn config.asgi:application \
        -k uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:$PORT \
        --workers $WORKERS \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
fi