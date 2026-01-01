# config/celery.py
import os
import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import before_task_publish, task_prerun, task_failure
from kombu import Queue

# Set default settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')

# ------------------------------------------------------------------------------
# RELIABILITY: Queue Definitions
# ------------------------------------------------------------------------------
app.conf.task_queues = (
    Queue('default', routing_key='default'),
    Queue('high_priority', routing_key='high_priority'),
    Queue('low_priority', routing_key='low_priority'),
)

app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'

# Worker Reliability Defaults
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.task_reject_on_worker_lost = True
# CRITICAL: Retry connecting to broker on startup (Docker robustness)
app.conf.broker_connection_retry_on_startup = True

app.autodiscover_tasks()

# ------------------------------------------------------------------------------
# TRACING: Propagate Request ID from Web to Worker
# ------------------------------------------------------------------------------
from apps.core.middleware import get_correlation_id, _correlation_id

@before_task_publish.connect
def transfer_correlation_id(headers=None, **kwargs):
    if headers is None: headers = {}
    request_id = get_correlation_id()
    if request_id:
        headers['X-Request-ID'] = request_id

@task_prerun.connect
def restore_correlation_id(task=None, **kwargs):
    if task.request.headers:
        request_id = task.request.headers.get('X-Request-ID')
        if request_id:
            _correlation_id.set(request_id)

# ------------------------------------------------------------------------------
# DB HARDENING
# ------------------------------------------------------------------------------
@task_prerun.connect
def close_old_connections(**kwargs):
    """
    Prevents 'connection already closed' errors with PgBouncer/Docker.
    """
    from django.db import close_old_connections
    close_old_connections()

# ------------------------------------------------------------------------------
# DEAD LETTER LOGGING
# ------------------------------------------------------------------------------
logger = logging.getLogger('celery.dlq')

@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, **opts):
    task_name = sender.name if sender else 'unknown_task'
    logger.critical(
        f"[DLQ] Task Failed Permanently: {task_name} (ID: {task_id})",
        extra={
            'task_name': task_name,
            'task_id': task_id,
            'args': args,
            'kwargs': kwargs,
            'exception': str(exception)
        }
    )

# ------------------------------------------------------------------------------
# BEAT SCHEDULE
# ------------------------------------------------------------------------------
app.conf.beat_schedule = {
    'reconcile-inventory-every-10-mins': {
        'task': 'apps.core.tasks.reconcile_inventory_redis_db',
        'schedule': crontab(minute='*/10'),
    },
    'monitor-stuck-orders-every-5-mins': {
        'task': 'apps.core.tasks.monitor_stuck_orders',
        'schedule': crontab(minute='*/5'),
    },
    'process-rider-payouts-daily': {
        'task': 'apps.riders.tasks.process_daily_payouts',
        'schedule': crontab(hour=1, minute=0), 
    },
    'health-check-heartbeat': {
        'task': 'apps.core.tasks.beat_heartbeat',
        'schedule': crontab(minute='*'), 
    },
}

app.conf.task_routes = {
    'apps.delivery.tasks.retry_auto_assign_rider': {'queue': 'high_priority'},
    'apps.notifications.tasks.send_otp_sms': {'queue': 'high_priority'},
    'apps.orders.tasks.send_order_confirmation_email': {'queue': 'high_priority'},
    'apps.core.tasks.*': {'queue': 'default'},
    'apps.assistant.views.*': {'queue': 'low_priority'},
}