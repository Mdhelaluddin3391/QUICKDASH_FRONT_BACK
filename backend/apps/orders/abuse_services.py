# apps/orders/abuse_services.py
from django.utils import timezone
from datetime import timedelta
from django.db.models import F
from .models import OrderAbuseLog
from apps.utils.exceptions import BusinessLogicException  # Use Custom Exception

class OrderAbuseService:
    MAX_CANCELS = 3
    BLOCK_HOURS = 24

    @staticmethod
    def check(user):
        log, _ = OrderAbuseLog.objects.get_or_create(user=user)
        if log.is_blocked():
            # Calculate remaining time for better UX
            remaining = log.blocked_until - timezone.now()
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            
            time_str = f"{hours}h {minutes}m"
            
            raise BusinessLogicException(
                f"Account blocked due to frequent cancellations. Try again in {time_str}.",
                code="user_blocked"
            )

    @staticmethod
    def record_cancel(user):
        log, _ = OrderAbuseLog.objects.get_or_create(user=user)
        
        log.cancelled_orders = F("cancelled_orders") + 1
        log.save(update_fields=["cancelled_orders"])
        log.refresh_from_db()

        if log.cancelled_orders >= OrderAbuseService.MAX_CANCELS:
            log.blocked_until = timezone.now() + timedelta(hours=OrderAbuseService.BLOCK_HOURS)
            log.save(update_fields=["blocked_until"])