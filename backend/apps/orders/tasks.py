from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Order
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Order
import logging

logger = logging.getLogger(__name__)


@shared_task(
    bind=True, 
    max_retries=5, 
    default_retry_delay=60, 
    autoretry_for=(Exception,), 
    retry_backoff=True, # Exponential Backoff
    retry_backoff_max=600 # Cap wait time at 10 mins
)

def send_order_confirmation_email(self, order_id, user_email):
    """
    Background task to send email.
    HARDENING:
    - Exponential backoff to prevent API rate limit hammering.
    - Explicit ignore for DoesNotExist (non-recoverable).
    """
    try:
        order = Order.objects.get(id=order_id)
        
        subject = f"Order #{order.id} Confirmed"
        message = f"Thank you! Your order total is {order.total_amount}."
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False, 
        )
        logger.info(f"Email sent for Order {order_id}")
        return "Sent"
    
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for email task. Skipping.")
        # Do not retry, it will never succeed
        return "Order Not Found"
        
    except Exception as e:
        logger.error(f"Email failed: {e}")
        raise