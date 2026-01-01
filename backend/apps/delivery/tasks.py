# apps/delivery/tasks.py
import logging
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.db import transaction

from apps.orders.models import Order
from apps.delivery.auto_assign import AutoRiderAssignmentService

logger = logging.getLogger(__name__)

@shared_task(
    bind=True, 
    max_retries=10, 
    default_retry_delay=30, 
    queue='high_priority'  # Critical for SLA
)
def retry_auto_assign_rider(self, order_id):
    """
    Background Task: Periodically attempts to assign a rider to an order.
    Uses 'AutoRiderAssignmentService' for intelligent, non-blocking matching.
    """
    try:
        order = Order.objects.get(id=order_id)
        
        # 1. State Check (Stop if cancelled or completed)
        if order.status in ["cancelled", "delivered", "failed"]:
            return f"Order in terminal state: {order.status}"
        
        # 2. Idempotency Check (Stop if already assigned)
        if hasattr(order, 'delivery') and order.delivery.rider:
            return "Already Assigned"

        # 3. Attempt Assignment
        # This service uses DB locking to safely find and assign a rider
        delivery = AutoRiderAssignmentService.assign(order)
        
        if delivery:
            logger.info(f"Rider {delivery.rider.id} assigned to Order {order_id}")
            return "Assigned"
        
        # 4. If failed, force retry (Exponential backoff handled by Celery config if set)
        logger.info(f"No rider found for Order {order_id}. Retrying...")
        raise self.retry()

    except MaxRetriesExceededError:
        # 5. Fallback: Move to Manual Intervention
        # This allows CS agents to see the order and manually assign or call riders
        with transaction.atomic():
            # Re-fetch with lock to prevent race conditions during status update
            order = Order.objects.select_for_update().get(id=order_id)
            if hasattr(order, 'delivery'):
                delivery = order.delivery
                delivery.job_status = 'manual_intervention'
                delivery.save(update_fields=['job_status'])
                
        logger.critical(f"Order {order_id} failed auto-assignment. Moved to Manual Intervention.")
        return "Manual Intervention"

    except Exception as exc:
        # Retry on transient system errors (DB connection, Redis blip)
        logger.error(f"System error in auto-assign task for Order {order_id}: {exc}")
        raise self.retry(exc=exc)