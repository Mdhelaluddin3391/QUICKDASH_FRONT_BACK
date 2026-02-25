import os
import logging
from celery import Celery
from celery.schedules import crontab
from celery.signals import before_task_publish, task_prerun, task_failure, worker_ready
from kombu import Queue
from apps.core.middleware import get_correlation_id, _correlation_id


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')


app.conf.task_queues = (
    Queue('default', routing_key='default'),
    Queue('high_priority', routing_key='high_priority'),
    Queue('low_priority', routing_key='low_priority'),
)

app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'


app.conf.task_acks_late = True

app.conf.worker_prefetch_multiplier = 1

app.conf.task_reject_on_worker_lost = True

app.conf.broker_connection_retry_on_startup = True
app.conf.broker_connection_max_retries = 10

app.conf.broker_heartbeat = 60
app.conf.broker_pool_limit = 10


app.conf.task_time_limit = 3600 

app.conf.task_soft_time_limit = 3000  

app.conf.worker_max_tasks_per_child = 100


if app.conf.get('CELERY_RESULT_BACKEND'):
    app.conf.result_expires = 3600  
    app.conf.result_backend_transport_options = {
        'retry_on_timeout': True,
        'socket_connect_timeout': 5,
        'socket_timeout': 5,
    }


app.autodiscover_tasks()



@before_task_publish.connect
def transfer_correlation_id(headers=None, **kwargs):
    """Propagate request ID from web request to Celery task."""
    if headers is None:
        headers = {}
    request_id = get_correlation_id()
    if request_id:
        headers['X-Request-ID'] = request_id

@task_prerun.connect
def restore_correlation_id(task=None, **kwargs):
    """Restore request ID in Celery task context."""
    if task and task.request and task.request.headers:
        request_id = task.request.headers.get('X-Request-ID')
        if request_id:
            _correlation_id.set(request_id)


@task_prerun.connect
def close_old_connections(**kwargs):
    """
    Prevents 'connection already closed' errors with PgBouncer/Docker.
    Ensures each task starts with a fresh database connection.
    """
    from django.db import close_old_connections
    close_old_connections()

logger = logging.getLogger('celery.dlq')

@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, **opts):
    """Log permanent task failures for alerting and debugging."""
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

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Log when worker is ready to process tasks."""
    logger.info(f"[CELERY] Worker is ready to process tasks")


app.conf.beat_schedule = {
    'reconcile-inventory-every-10-mins': {
        'task': 'apps.core.tasks.reconcile_inventory_redis_db',
        'schedule': crontab(minute='*/10'),
        'options': {'queue': 'default', 'expires': 600},
    },
    'monitor-stuck-orders-every-5-mins': {
        'task': 'apps.core.tasks.monitor_stuck_orders',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'default', 'expires': 300},
    },
    'assign-unassigned-orders-every-5-mins': {
        'task': 'apps.delivery.tasks.periodic_assign_unassigned_orders',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'high_priority', 'expires': 300},
    },
    'process-rider-payouts-daily': {
        'task': 'apps.riders.tasks.process_daily_payouts',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'default', 'expires': 86400},
    },
    'health-check-heartbeat': {
        'task': 'apps.core.tasks.beat_heartbeat',
        'schedule': crontab(minute='*'),
        'options': {'queue': 'default', 'expires': 60},
    },
}


app.conf.task_routes = {
    'apps.delivery.tasks.retry_auto_assign_rider': {'queue': 'high_priority'},
    'apps.delivery.tasks.assign_rider_to_order': {'queue': 'high_priority'},
    'apps.delivery.tasks.periodic_assign_unassigned_orders': {'queue': 'high_priority'},
    'apps.notifications.tasks.send_otp_sms': {'queue': 'high_priority'},
    'apps.orders.tasks.send_order_confirmation_email': {'queue': 'high_priority'},
    
    'apps.core.tasks.*': {'queue': 'default'},
    
    'apps.assistant.views.*': {'queue': 'low_priority'},
}


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger.info(" Celery configuration loaded")
