import razorpay
import logging
import hmac
import hashlib
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Payment
from apps.audit.services import AuditService
from apps.delivery.tasks import retry_auto_assign_rider
from apps.delivery.auto_assign import AutoRiderAssignmentService
from apps.utils.resilience import CircuitBreaker, CircuitBreakerOpenException
from apps.utils.exceptions import BusinessLogicException

try:
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except Exception:
    client = None

logger = logging.getLogger(__name__)

class PaymentService:

    @staticmethod
    @transaction.atomic
    def create_payment(order):
        """
        Creates a payment intent on the Gateway.
        Idempotent: Returns existing payment if order is already linked.
        """
        from apps.orders.models import Order
        order = Order.objects.select_for_update().get(id=order.id)

        if hasattr(order, "payment"):
            return order.payment

        if not client:
            raise BusinessLogicException("Payment Gateway not configured", code="config_error")

        @CircuitBreaker(service_name="razorpay", failure_threshold=5, recovery_timeout=30)
        def _call_gateway():
            amount_paise = int(order.total_amount * 100)
            return client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "receipt": str(order.id),
                "notes": {"order_id": str(order.id)}
            })

        try:
            razorpay_order = _call_gateway()
        except CircuitBreakerOpenException:
            raise BusinessLogicException("Payment system busy. Please try later.", code="gateway_down")
        except Exception as e:
            logger.error(f"Razorpay Create Error: {e}")
            raise BusinessLogicException("Payment Gateway Error", code="gateway_error")

        return Payment.objects.create(
            order=order,
            amount=order.total_amount,
            provider_order_id=razorpay_order['id'],
            status="created",
        )

    @staticmethod
    @transaction.atomic
    def mark_paid(payment_id, provider_payment_id, provider_order_id):
        """
        Transitions Payment to PAID and Order to CONFIRMED.
        Secure against Replay Attacks.
        """
        try:
            payment = Payment.objects.select_for_update().get(id=payment_id)
        except Payment.DoesNotExist:
            raise BusinessLogicException("Payment not found", code="not_found")

        if payment.status == "paid":
            if payment.provider_payment_id != provider_payment_id:
                logger.critical(f"Security Alert: Payment {payment.id} ID Mismatch! Stored: {payment.provider_payment_id}, New: {provider_payment_id}")
            return payment

        if payment.provider_order_id and payment.provider_order_id != provider_order_id:
             raise BusinessLogicException("Order ID Mismatch - Potential Fraud", code="fraud_check")

        payment.provider_payment_id = provider_payment_id
        payment.status = "paid"
        payment.save()

        order = payment.order
        if order.status == "cancelled":
             logger.warning(f"Payment received for cancelled order {order.id}. Auto-refund logic required.")
        else:
            order.status = "confirmed"
            order.save(update_fields=["status"])

        transaction.on_commit(lambda: AuditService.payment_success(payment))
        transaction.on_commit(lambda: PaymentService._trigger_delivery(order.id))
        
        return payment

    @staticmethod
    def _trigger_delivery(order_id):
        """
        Triggers Rider Assignment logic.
        """
        try:
            from apps.orders.models import Order
            order = Order.objects.get(id=order_id)
            
            delivery = AutoRiderAssignmentService.assign(order)
            
            if not delivery:
                retry_auto_assign_rider.delay(order.id)
        except Exception as e:
            logger.error(f"Delivery trigger failed for {order_id}: {e}")
            retry_auto_assign_rider.delay(order_id)

    @staticmethod
    def verify_razorpay_signature(order_id, payment_id, signature) -> bool:
        if not client: return False
        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
            return True
        except Exception:
            return False

    @staticmethod
    def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
        """
        Secure HMAC verification (Constant Time).
        """
        if not (body and signature and secret):
            return False
        
        generated_signature = hmac.new(
            key=secret.encode('utf-8'),
            msg=body,
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(generated_signature, signature)

    @staticmethod
    @transaction.atomic
    def mark_failed(payment_id):
        """
        Transitions Payment to FAILED and RELEASES reserved inventory.
        """
        from apps.inventory.services import InventoryService
        
        payment = Payment.objects.select_for_update().get(id=payment_id)
        if payment.status == "failed":
            return payment

        payment.status = "failed"
        payment.save()

        InventoryService.release_stock_for_order(payment.order)
        
        AuditService.payment_failed(payment)
        return payment

class ReconciliationService:
    @staticmethod
    def reconcile_stuck_orders():
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(minutes=10)
        
        stuck_payments = Payment.objects.filter(
            status="created",
            created_at__lt=cutoff_time
        ).select_related('order')

        if not client: return

        for payment in stuck_payments:
            try:
                provider_data = client.order.fetch(payment.provider_order_id)
                
                if provider_data.get('status') == 'paid':
                    logger.info(f"Reconciling stuck payment {payment.id}")
                    attempts = provider_data.get('attempts', [])
                    attempt_id = attempts[0]['id'] if attempts else "reconciled_no_id"
                    
                    PaymentService.mark_paid(
                        payment.id, 
                        provider_payment_id=attempt_id, 
                        provider_order_id=payment.provider_order_id
                    )
                elif provider_data.get('status') == 'attempted':
                    payment.status = 'failed'
                    payment.save(update_fields=['status'])
                    
            except Exception as e:
                logger.error(f"Reconciliation error for {payment.id}: {e}")