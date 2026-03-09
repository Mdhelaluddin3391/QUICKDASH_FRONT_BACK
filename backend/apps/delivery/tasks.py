import logging
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.orders.models import Order
from apps.delivery.auto_assign import AutoRiderAssignmentService

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    max_retries=10,
    default_retry_delay=30,
    queue='high_priority' 
)
def retry_auto_assign_rider(self, order_id):
    """
    Background Task: Periodically attempts to assign a rider to an order.
    Uses 'AutoRiderAssignmentService' for intelligent, non-blocking matching.
    """
    try:
        order = Order.objects.get(id=order_id)

        if order.status in ["cancelled", "delivered", "failed"]:
            return f"Order in terminal state: {order.status}"

        if hasattr(order, 'delivery') and order.delivery.rider:
            return "Already Assigned"

        delivery = AutoRiderAssignmentService.assign(order)

        if delivery:
            logger.info(f"Rider {delivery.rider.id} assigned to Order {order_id}")
            return "Assigned"

        logger.info(f"No rider found for Order {order_id}. Retrying...")
        raise self.retry()

    except MaxRetriesExceededError:
        
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            if hasattr(order, 'delivery'):
                delivery = order.delivery
                delivery.job_status = 'manual_intervention'
                delivery.save(update_fields=['job_status'])

        logger.critical(f"Order {order_id} failed auto-assignment. Moved to Manual Intervention.")
        return "Manual Intervention"

    except Exception as exc:
        logger.error(f"System error in auto-assign task for Order {order_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def assign_rider_to_order(self, order_id):
    """
    Task to assign a rider to an order using AutoRiderAssignmentService.
    If no rider is found, logs the event and optionally retries softly.
    """
    try:
        order = Order.objects.get(id=order_id)

        if order.status != "packed":
            logger.info(f"Order {order_id} is no longer in 'packed' status. Skipping assignment.")
            return "Skipped"

        if hasattr(order, 'delivery') and order.delivery.rider:
            logger.info(f"Order {order_id} is already assigned. Skipping.")
            return "Already Assigned"

        delivery = AutoRiderAssignmentService.assign(order)

        if delivery:
            logger.info(f"Rider {delivery.rider.id} assigned to Order {order_id}")
            return "Assigned"
        else:
            logger.warning(f"No rider found for Order {order_id}. Retrying softly.")
            raise self.retry(countdown=60, max_retries=5)

    except MaxRetriesExceededError:
        logger.error(f"Max retries exceeded for Order {order_id}. No rider assigned.")
        return "Failed - No Rider"

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} does not exist.")
        return "Order Not Found"

    except Exception as exc:
        logger.error(f"Unexpected error in assign_rider_to_order for Order {order_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task(queue='low_priority')
def periodic_assign_unassigned_orders():
    """
    Safety Net: Har 5-10 minute main chalega.
    Check karega agar koi 'packed' order galti se miss ho gaya ho.
    """
    yesterday = timezone.now() - timedelta(hours=24)
    
    stuck_orders = Order.objects.filter(
        status='packed',
        created_at__gte=yesterday,
        delivery__rider__isnull=True
    )

    count = 0
    for order in stuck_orders:
        retry_auto_assign_rider.delay(order.id)
        count += 1
    
    return f"Retried assignment for {count} stuck orders."