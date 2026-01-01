# apps/payments/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from .refund_services import RefundService

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_refund_task(self, refund_id):
    try:
        RefundService.process_refund_gateway(refund_id)
        return "Refund Processed"
    except Exception as e:
        logger.error(f"Refund Task Failed: {e}")
        raise self.retry(exc=e)