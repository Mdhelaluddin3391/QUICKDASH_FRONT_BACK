
import os
import multiprocessing

CPU_COUNT = multiprocessing.cpu_count()
DEFAULT_WORKERS = (CPU_COUNT * 2) + 1
workers = int(os.getenv("GUNICORN_WORKERS", DEFAULT_WORKERS))

worker_class = "uvicorn.workers.UvicornWorker"

port = int(os.getenv("PORT", 5000))
bind = [f"0.0.0.0:{port}"]

proc_name = "quickdash-api"


timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))

graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))

keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))


access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

accesslog = "-"
errorlog = "-"

loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")


max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 100))


forwarded_allow_ips = "*"

access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
)


preload_app = True


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
