import razorpay
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Payment, Refund
from apps.audit.services import AuditService
from apps.utils.exceptions import BusinessLogicException

logger = logging.getLogger(__name__)

try:
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except Exception:
    client = None

class RefundService:
    @staticmethod
    def initiate_refund(payment: Payment) -> Refund:
        """
        Phase 1: Record Intent.
        Locks Payment row to prevent concurrent refunds.
        """
        with transaction.atomic():
            locked_payment = Payment.objects.select_for_update().get(id=payment.id)

            if hasattr(locked_payment, "refund"):
                return locked_payment.refund

            if locked_payment.status != "paid":
                 raise BusinessLogicException("Only paid orders can be refunded.")

            refund = Refund.objects.create(
                payment=locked_payment,
                amount=locked_payment.amount,
                status="initiated",
                created_at=timezone.now()
            )
            AuditService.refund_initiated(refund)
        
   
        from apps.payments.tasks import process_refund_task
        transaction.on_commit(lambda: process_refund_task.delay(refund.id))

        return refund

    @staticmethod
    def process_refund_gateway(refund_id: int):
        """
        Phase 2: External Call.
        """
        if not client: return

        try:
            refund = Refund.objects.get(id=refund_id)
            
            if refund.status == "processed":
                return

            payment = refund.payment
            amount_paise = int(refund.amount * 100)

            razorpay_refund = client.payment.refund(payment.provider_payment_id, {
                "amount": amount_paise,
                "speed": "normal",
                "notes": {"order_id": str(payment.order.id)}
            })
            
            with transaction.atomic():
                refund = Refund.objects.select_for_update().get(id=refund_id)
                refund.provider_refund_id = razorpay_refund.get("id")
                refund.status = "processed" 
                refund.save()
                
                AuditService.refund_completed(refund)

        except Exception as e:
            logger.error(f"Refund Gateway Error: {e}")