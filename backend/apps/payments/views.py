# apps/payments/views.py
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.orders.models import Order
from apps.payments.models import Payment, Refund
from .services import PaymentService

logger = logging.getLogger(__name__)

class CreatePaymentAPIView(APIView):
    """
    Initiates a Payment Intent (Order) with the Gateway.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        # 1. Validation: Ensure Order belongs to User and is in valid state
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status not in ['created', 'confirmed']:
             return Response(
                 {"error": f"Order is {order.status}, cannot initiate payment"}, 
                 status=status.HTTP_400_BAD_REQUEST
             )

        # 2. Create Payment Intent
        try:
            payment = PaymentService.create_payment(order)
        except Exception as e:
            # PaymentService handles logic exceptions, bubble up standard error
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # 3. Return Config for Frontend SDK
        return Response({
            "id": payment.provider_order_id,
            "amount": int(payment.amount * 100),
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID
        }, status=status.HTTP_201_CREATED)


class RazorpayVerifyAPIView(APIView):
    """
    Verifies the signature sent by Frontend after successful payment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get("razorpay_payment_id")
        order_id = request.data.get("razorpay_order_id")
        signature = request.data.get("razorpay_signature")

        if not all([payment_id, order_id, signature]):
            return Response({"error": "Missing payment details"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Find local payment record
            payment = Payment.objects.get(provider_order_id=order_id)
        except Payment.DoesNotExist:
            return Response({"error": "Invalid order ID"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Local Signature Verification
        if not PaymentService.verify_razorpay_signature(order_id, payment_id, signature):
            PaymentService.mark_failed(payment)
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Mark Paid & Trigger Delivery
        # Service handles its own transaction.atomic()
        PaymentService.mark_paid(
            payment.id,
            provider_payment_id=payment_id,
            provider_order_id=order_id,
        )

        return Response({"status": "payment verified"})


class RazorpayWebhookAPIView(APIView):
    """
    Async Handler for Payment Confirmations & Refunds.
    CRITICAL: This is the source of truth if frontend network fails.
    """
    permission_classes = [AllowAny] # Webhooks are public but signed
    authentication_classes = []     # Disable JWT for this endpoint

    def post(self, request):
        signature = request.headers.get("X-Razorpay-Signature")
        secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", None)
        
        # 1. Security Check (HMAC)
        if not PaymentService.verify_webhook_signature(request.body, signature, secret):
            logger.warning("Webhook Signature Mismatch")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        payload = request.data
        event = payload.get("event")
        
        try:
            # FIX: Ensure entire webhook processing is Atomic
            # This prevents partial updates (e.g., Refund updated but Order status not)
            with transaction.atomic():
                
                # Case A: Payment Captured (Success)
                if event == "payment.captured":
                    entity = payload["payload"]["payment"]["entity"]
                    provider_order_id = entity["order_id"]
                    provider_payment_id = entity["id"]
                    
                    try:
                        # Lock payment row for update
                        payment = Payment.objects.select_for_update().get(provider_order_id=provider_order_id)
                        
                        if payment.status != "paid":
                            logger.info(f"Webhook: Marking Payment {payment.id} as PAID")
                            # Service handles idempotency internally
                            PaymentService.mark_paid(
                                payment.id,
                                provider_payment_id=provider_payment_id,
                                provider_order_id=provider_order_id
                            )
                    except Payment.DoesNotExist:
                        # Log but return 200 so Razorpay doesn't retry forever for a bad ID
                        logger.error(f"Webhook: Payment not found for {provider_order_id}")

                # Case B: Refund Processed
                elif event == "refund.processed":
                    entity = payload["payload"]["refund"]["entity"]
                    provider_refund_id = entity["id"]
                    payment_id = entity["payment_id"] # Provider payment ID
                    
                    # Lock refund row via payment lookup
                    refund = Refund.objects.select_for_update().filter(
                        payment__provider_payment_id=payment_id
                    ).select_related('payment', 'payment__order').first()

                    if refund and refund.status != "processed":
                        refund.status = "processed"
                        refund.provider_refund_id = provider_refund_id
                        refund.save(update_fields=["status", "provider_refund_id"])
                        
                        # Ensure order is cancelled if not already
                        if refund.payment.order.status != "cancelled":
                             refund.payment.order.status = "cancelled"
                             refund.payment.order.save(update_fields=["status"])
                             
                        logger.info(f"Webhook: Refund {refund.id} Processed")

        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            # Return 500 so Razorpay retries later (Transient errors like DB locks)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)