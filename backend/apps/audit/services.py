from django.utils import timezone
from .models import AuditLog

class AuditService:
    """
    Centralized Audit Logging.
    Writes immutable logs for compliance and debugging.
    """

    @staticmethod
    def log(action, reference_id, user, metadata):
        AuditLog.objects.create(
            user=user,
            action=action,
            reference_id=reference_id,
            metadata=metadata,
            created_at=timezone.now()
        )


    @staticmethod
    def order_created(order):
        AuditService.log(
            action="order_created",
            reference_id=str(order.id),
            user=order.user,
            metadata={
                "amount": str(order.total_amount),
                "warehouse": order.warehouse.id,
                "delivery_type": order.delivery_type,
            },
        )

    @staticmethod
    def order_cancelled(order):
        AuditService.log(
            action="order_cancelled",
            reference_id=str(order.id),
            user=order.user,
            metadata={"status": order.status},
        )

    @staticmethod
    def payment_success(payment):
        AuditService.log(
            action="payment_success",
            reference_id=str(payment.id),
            user=payment.order.user,
            metadata={
                "order_id": payment.order.id,
                "amount": str(payment.amount),
                "provider_id": payment.provider_payment_id,
            },
        )

    @staticmethod
    def payment_failed(payment):
        AuditService.log(
            action="payment_failed",
            reference_id=str(payment.id),
            user=payment.order.user,
            metadata={"order_id": payment.order.id},
        )

    @staticmethod
    def refund_initiated(refund):
        AuditService.log(
            action="refund_initiated",
            reference_id=str(refund.id),
            user=refund.payment.order.user,
            metadata={
                "payment_id": refund.payment.id,
                "amount": str(refund.amount),
            },
        )

    @staticmethod
    def refund_completed(refund):
        AuditService.log(
            action="refund_completed",
            reference_id=str(refund.id),
            user=refund.payment.order.user,
            metadata={"provider_refund_id": refund.provider_refund_id},
        )

    @staticmethod
    def delivery_completed(delivery):
        AuditService.log(
            action="delivery_completed",
            reference_id=str(delivery.id),
            user=delivery.rider.user,
            metadata={
                "order_id": delivery.order.id,
                "rider_id": delivery.rider.id,
            },
        )