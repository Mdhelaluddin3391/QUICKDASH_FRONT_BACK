from celery import shared_task
from django.db import transaction
from django.utils import timezone
from .models import RiderProfile
from .services import RiderService
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_single_rider_payout(self, rider_id):
    """
    Helper task to process a single rider's payout atomically.
    Uses retries for transient database failures.
    """
    try:
        # Re-fetch inside task
        rider = RiderProfile.objects.get(id=rider_id)
        with transaction.atomic():
            payout = RiderService.generate_payout(rider)
            if payout:
                logger.info(f"Generated Payout #{payout.id} for Rider {rider.user.phone}")
                return True
    except RiderProfile.DoesNotExist:
        logger.error(f"Rider {rider_id} not found during payout generation.")
        return False
    except Exception as e:
        logger.error(f"Error generating payout for rider {rider_id}: {e}")
        # Retry logic: Exponential Backoff likely handled by Celery config, 
        # but here we ensure transient errors (DB locks) don't just vanish.
        raise self.retry(exc=e)

@shared_task
def process_daily_payouts():
    """
    Cron job to aggregate unpaid earnings into Payout records.
    Delegates to child tasks to prevent long-running DB transactions/locks.
    """
    logger.info("Starting Daily Payout Processing...")
    
    # Identify candidates
    riders_ids = RiderProfile.objects.filter(
        earnings__payout__isnull=True
    ).values_list('id', flat=True).distinct()

    count = 0
    for rider_id in riders_ids:
        # Async dispatch
        generate_single_rider_payout.delay(rider_id)
        count += 1

    logger.info(f"Queued {count} payout tasks.")
    return f"Queued {count} tasks"


from celery import shared_task
from django.db import transaction
from .models import RiderProfile
from .services import RiderService
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_single_rider_payout(self, rider_id):
    """
    Helper task to process a single rider's payout atomically.
    """
    try:
        rider = RiderProfile.objects.get(id=rider_id)
        # Using Service to handle locking and aggregation
        payout = RiderService.generate_payout(rider)
        if payout:
            logger.info(f"Generated Payout #{payout.id} for Rider {rider.user.phone} - Amount: {payout.amount}")
            return True
        return False
    except RiderProfile.DoesNotExist:
        logger.error(f"Rider {rider_id} not found during payout.")
        return False
    except Exception as e:
        logger.error(f"Error generating payout for rider {rider_id}: {e}")
        raise self.retry(exc=e)

@shared_task
def process_daily_payouts():
    """
    Cron job to trigger payouts.
    Iterates all riders with pending earnings.
    """
    logger.info("Starting Daily Payout Processing...")
    
    # Identify riders with at least one unpaid earning
    riders_ids = RiderProfile.objects.filter(
        earnings__payout__isnull=True
    ).values_list('id', flat=True).distinct()

    count = 0
    for rider_id in riders_ids:
        generate_single_rider_payout.delay(rider_id)
        count += 1

    return f"Queued {count} payout tasks"