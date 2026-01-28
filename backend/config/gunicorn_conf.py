# ==============================================================================
# PRODUCTION-GRADE GUNICORN CONFIGURATION
# Optimized for Railway, AWS ECS, Docker Compose
# ==============================================================================

import os
import multiprocessing

# ==============================================================================
# WORKER CONFIGURATION
# ==============================================================================
# Calculate workers: (2 * CPU_COUNT) + 1
# For 2 CPU environment: 5 workers
# For 4 CPU environment: 9 workers
# Can be overridden with GUNICORN_WORKERS env var
CPU_COUNT = multiprocessing.cpu_count()
DEFAULT_WORKERS = (CPU_COUNT * 2) + 1
workers = int(os.getenv("GUNICORN_WORKERS", DEFAULT_WORKERS))

# Uvicorn worker for ASGI (async support for WebSockets, etc.)
worker_class = "uvicorn.workers.UvicornWorker"

# ==============================================================================
# SERVER SOCKET CONFIGURATION
# ==============================================================================
# Bind to all interfaces, respecting PORT env var
port = int(os.getenv("PORT", 5000))
bind = [f"0.0.0.0:{port}"]

# ==============================================================================
# PROCESS NAMING
# ==============================================================================
proc_name = "quickdash-api"

# ==============================================================================
# TIMEOUT CONFIGURATION
# ==============================================================================
# Timeout for individual requests (120 seconds)
# Long requests should return partial responses or stream data
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))

# Timeout for graceful worker shutdown
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))

# Keep-alive timeout for connection reuse
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

# ==============================================================================
# LOGGING CONFIGURATION
# Logs MUST go to stdout/stderr for container environments
# ==============================================================================
# Access log format for request tracking
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Log to stdout (important for container environments like Railway, ECS)
accesslog = "-"
errorlog = "-"

# Log level: debug, info, warning, error, critical
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# ==============================================================================
# WORKER BEHAVIOR
# ==============================================================================
# Max simultaneous clients per worker
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))

# Random jitter to prevent thundering herd on restart
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 100))

# ==============================================================================
# SECURITY & RELIABILITY
# ==============================================================================
# Forwarded allow IPs (for X-Forwarded-For headers from proxies)
# Allow all IPs since we trust the reverse proxy (Railway/AWS)
forwarded_allow_ips = "*"

# Enable access logs
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
)

# ==============================================================================
# PRELOAD APP
# Preload the Django application in the master process
# Reduces worker startup time and memory footprint
# ==============================================================================
preload_app = True

# ==============================================================================
# LIFECYCLE HOOKS
# ==============================================================================
def when_ready(server):
    """Called after the server is started."""
    print(f"[GUNICORN] Server is ready. Spawned {workers} workers")

def on_starting(server):
    """Called just before the master process is initialized."""
    print(f"[GUNICORN] Starting Gunicorn with {workers} workers on 0.0.0.0:{port}")
    print(f"[GUNICORN] Worker class: {worker_class}")
    print(f"[GUNICORN] Timeout: {timeout}s, Graceful timeout: {graceful_timeout}s")

def on_exit(server):
    """Called just before exiting Gunicorn."""
    print("[GUNICORN] Server shutting down")
