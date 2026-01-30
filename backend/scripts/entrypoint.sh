#!/bin/sh
# ==============================================================================
# PRODUCTION-GRADE ENTRYPOINT
# Designed for Railway, AWS ECS, Docker Compose
# Handles graceful startup with dependency checks, migrations, and signal handling
# ==============================================================================

set -e

# Color output for readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo "${GREEN}✅ $1${NC}"
}

log_warn() {
    echo "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo "${RED}❌ $1${NC}"
}

# ==============================================================================
# PHASE 1: ENVIRONMENT VALIDATION
# ==============================================================================
log_info "Starting Django entrypoint..."

# Validate critical environment variables
if [ -z "$DJANGO_SECRET_KEY" ] && [ "$DJANGO_ENV" != "development" ]; then
    log_error "DJANGO_SECRET_KEY is required in production"
    exit 1
fi

if [ -z "$DATABASE_URL" ] && [ -z "$POSTGRES_USER" ]; then
    log_error "DATABASE_URL or POSTGRES_* environment variables are required"
    exit 1
fi

if [ "$DJANGO_ENV" != "development" ] && [ -z "$REDIS_URL" ]; then
    log_warn "REDIS_URL not set - Celery tasks may not work correctly"
fi

log_success "Environment validation passed"

# ==============================================================================
# PHASE 2: WAIT FOR POSTGRESQL
# ==============================================================================
if [ -n "$DATABASE_URL" ] || [ -n "$POSTGRES_HOST" ]; then
    log_info "Waiting for PostgreSQL to be ready..."
    
    POSTGRES_HOST=${POSTGRES_HOST:-localhost}
    POSTGRES_PORT=${POSTGRES_PORT:-5432}
    
    # Retry logic with exponential backoff
    MAX_RETRIES=30
    RETRY_COUNT=0
    RETRY_DELAY=1
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if python3 - <<'EOF'
import psycopg2
import os
import sys

try:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB")
        )
    conn.close()
    sys.exit(0)
except Exception as e:
    sys.exit(1)
EOF
        then
            log_success "PostgreSQL is ready"
            break
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            log_warn "PostgreSQL not ready (attempt $RETRY_COUNT/$MAX_RETRIES), retrying in ${RETRY_DELAY}s..."
            sleep $RETRY_DELAY
            # Exponential backoff, max 5 seconds
            RETRY_DELAY=$((RETRY_DELAY * 2))
            if [ $RETRY_DELAY -gt 5 ]; then
                RETRY_DELAY=5
            fi
        else
            log_error "PostgreSQL failed to become ready after $MAX_RETRIES attempts"
            exit 1
        fi
    done
fi

# ==============================================================================
# PHASE 3: WAIT FOR REDIS
# ==============================================================================
if [ -n "$REDIS_URL" ]; then
    log_info "Waiting for Redis to be ready..."
    
    MAX_RETRIES=15
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if redis-cli -u "$REDIS_URL" ping 2>/dev/null | grep -q PONG; then
            log_success "Redis is ready"
            break
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            log_warn "Redis not ready (attempt $RETRY_COUNT/$MAX_RETRIES), retrying in 2s..."
            sleep 2
        else
            log_warn "Redis failed to become ready after $MAX_RETRIES attempts (non-critical)"
        fi
    done
fi

# ==============================================================================
# PHASE 4: FIX PERMISSIONS
# ==============================================================================
log_info "Setting up permissions..."

# Ensure directories exist
mkdir -p /app/staticfiles /app/media /app/logs

# Fix permissions (use gosu if available, fallback to chown)
if command -v gosu &> /dev/null; then
    gosu appuser:appgroup chmod -R 755 /app/staticfiles /app/media /app/logs 2>/dev/null || true
else
    chmod -R 755 /app/staticfiles /app/media /app/logs 2>/dev/null || true
fi

log_success "Permissions set"

# ==============================================================================
# PHASE 5: RUN MIGRATIONS (DISABLED TO PREVENT CRASH)
# ==============================================================================
# ⚠️ NOTE: Migrations are disabled in entrypoint to prevent Out-Of-Memory crashes 
# on Railway Starter Plan. You MUST run 'python manage.py migrate' manually via CLI.

if [ "$IS_PRIMARY" = "1" ] || [ "$IS_PRIMARY" = "true" ]; then
    log_info "Skipping automatic migrations to prevent boot crash..."
    
    # Original migration code (Commented out)
    # log_info "Running database migrations (PRIMARY INSTANCE)..."
    # if python3 manage.py migrate --noinput; then
    #     log_success "Migrations completed successfully"
    # else
    #     log_error "Migrations failed"
    #     exit 1
    # fi
else
    log_info "Skipping migrations (non-primary instance)"
fi

# ==============================================================================
# PHASE 6: COLLECT STATIC FILES (PRIMARY INSTANCE ONLY)
# ==============================================================================
if [ "$IS_PRIMARY" = "1" ] || [ "$IS_PRIMARY" = "true" ]; then
    log_info "Collecting static files (PRIMARY INSTANCE)..."
    
    if python3 manage.py collectstatic --noinput --clear; then
        log_success "Static files collected"
    else
        log_warn "Static file collection had issues (non-critical)"
    fi
else
    log_info "Skipping static file collection (non-primary instance)"
fi

# ==============================================================================
# PHASE 7: START APPLICATION
# ==============================================================================
log_info "Starting application server..."

if [ "$RUN_GUNICORN" = "1" ] || [ "$RUN_GUNICORN" = "true" ]; then
    # Start Gunicorn with ASGI worker (Uvicorn)
    PORT=${PORT:-5000}
    WORKERS=${WORKERS:-3}
    
    log_success "Starting Gunicorn on port $PORT with $WORKERS workers"
    
    # Execute with proper signal handling
    if command -v gosu &> /dev/null; then
        exec gosu appuser:appgroup gunicorn config.asgi:application \
            -k uvicorn.workers.UvicornWorker \
            --bind 0.0.0.0:$PORT \
            --workers $WORKERS \
            --worker-class uvicorn.workers.UvicornWorker \
            --timeout 120 \
            --graceful-timeout 30 \
            --keep-alive 5 \
            --access-logfile - \
            --error-logfile - \
            --log-level info
    else
        exec gunicorn config.asgi:application \
            -k uvicorn.workers.UvicornWorker \
            --bind 0.0.0.0:$PORT \
            --workers $WORKERS \
            --worker-class uvicorn.workers.UvicornWorker \
            --timeout 120 \
            --graceful-timeout 30 \
            --keep-alive 5 \
            --access-logfile - \
            --error-logfile - \
            --log-level info
    fi
else
    # Run auxiliary process (Celery worker, Celery beat, etc.)
    log_info "Starting auxiliary process: $@"
    exec "$@"
fi