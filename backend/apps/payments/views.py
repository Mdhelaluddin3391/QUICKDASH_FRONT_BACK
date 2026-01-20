# apps/payments/views.py
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
import razorpay
from apps.utils.idempotency import idempotent
from apps.orders.models import Order
from apps.payments.models import Payment, Refund
from .services import PaymentService

logger = logging.getLogger(__name__)


client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))



class CreatePaymentAPIView(APIView):
    """
    Initiates a Payment Intent (Order) with the Gateway.
    Compatible with Checkout.js 'UPI Only' flow.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        # 1. Validation: Ensure Order belongs to User and is in valid state
        order = get_object_or_404(Order, id=order_id, user=request.user)

        # Check if order is already paid to prevent double payment
        if order.payment_status == 'PAID':
             return Response(
                 {"error": "Order is already paid"}, 
                 status=status.HTTP_400_BAD_REQUEST
             )

        if order.status not in ['created', 'confirmed']:
             return Response(
                 {"error": f"Order is {order.status}, cannot initiate payment"}, 
                 status=status.HTTP_400_BAD_REQUEST
             )

        # 2. Create Payment Intent via Service
        try:
            payment = PaymentService.create_payment(order)
            
            # 3. Return Config for Frontend SDK
            return Response({
                "id": payment.provider_order_id,
                "amount": int(payment.amount * 100),
                "currency": "INR",
                "key": settings.RAZORPAY_KEY_ID,
                "name": "QuickDash",           # Added for UI
                "description": f"Order #{order.id}" # Added for UI
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Payment Init Failed: {str(e)}")
            return Response({"error": "Payment Gateway Error. Please try again."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class RazorpayVerifyAPIView(APIView):
    """
    Step 2: Verify Signature (The most critical Security Step).
    """
    permission_classes = [IsAuthenticated]

    @idempotent(timeout=300)
    def post(self, request):
        data = request.data
        payment_id = data.get("razorpay_payment_id")
        order_id = data.get("razorpay_order_id")
        signature = data.get("razorpay_signature")

        if not all([payment_id, order_id, signature]):
            return Response({"error": "Missing payment details"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(provider_order_id=order_id)
        except Payment.DoesNotExist:
            return Response({"error": "Invalid Order ID"}, status=status.HTTP_400_BAD_REQUEST)

        # [SECURITY LOGIC 3] Signature Verification
        # Hum frontend ke status par vishwas nahi karte. 
        # Hum Razorpay ke secret key se signature match karte hain.
        try:
            client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
        except razorpay.errors.SignatureVerificationError:
            PaymentService.mark_failed(payment)
            return Response({"error": "Payment Signature Verification Failed! Transaction may be fake."}, status=status.HTTP_400_BAD_REQUEST)

        # Mark Success in DB
        PaymentService.mark_paid(
            payment.id,
            provider_payment_id=payment_id,
            provider_order_id=order_id,
        )

        return Response({"status": "success", "message": "Payment Verified"})
    


    
class RazorpayWebhookAPIView(APIView):
    """
    Async Handler for Payment Confirmations & Refunds.
    CRITICAL: This is the source of truth if frontend network fails.
    """
    permission_classes = [AllowAny] # Webhooks are public but signed
    authentication_classes = []     # Disable JWT for this endpoint

    @idempotent(timeout=300)
    def post(self, request):
        # 1. Get Signature and Secret
        signature = request.headers.get("X-Razorpay-Signature")
        secret = settings.RAZORPAY_WEBHOOK_SECRET
        if not secret:
            logger.error("RAZORPAY_WEBHOOK_SECRET not set")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 2. Security Check (HMAC Verification)
        try:
            # Verify that the request actually came from Razorpay
            # We decode the body to string as required by some SDK versions
            client.utility.verify_webhook_signature(request.body.decode('utf-8'), signature, secret)
        except Exception as e:
            logger.warning(f"Webhook Signature Mismatch: {str(e)}")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # 3. Process the Event
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
                        # Lock payment row for update to avoid race conditions
                        payment = Payment.objects.select_for_update().get(provider_order_id=provider_order_id)
                        
                        if payment.status != "paid":
                            logger.info(f"Webhook: Marking Payment {payment.id} as PAID")
                            
                            # Update Payment & Order Status via Service
                            PaymentService.mark_paid(
                                payment.id,
                                provider_payment_id=provider_payment_id,
                                provider_order_id=provider_order_id
                            )
                        else:
                            logger.info(f"Webhook: Payment {payment.id} already PAID")

                    except Payment.DoesNotExist:
                        # Log but return 200 so Razorpay doesn't retry forever for a bad ID
                        logger.error(f"Webhook: Payment object not found for order_id {provider_order_id}")
                        return Response(status=status.HTTP_200_OK)

                # Case B: Refund Processed
                elif event == "refund.processed":
                    entity = payload["payload"]["refund"]["entity"]
                    provider_refund_id = entity["id"]
                    payment_id = entity["payment_id"] # Provider payment ID (not our DB ID)
                    
                    # Find refund via the payment's provider_id
                    # We lock the refund row to prevent conflicts
                    refund = Refund.objects.select_for_update().filter(
                        payment__provider_payment_id=payment_id
                    ).select_related('payment', 'payment__order').first()

                    if refund:
                        if refund.status != "processed":
                            refund.status = "processed"
                            refund.provider_refund_id = provider_refund_id
                            refund.save(update_fields=["status", "provider_refund_id"])
                            
                            # Ensure order is cancelled if not already
                            if refund.payment.order.status != "cancelled":
                                 refund.payment.order.status = "cancelled"
                                 refund.payment.order.save(update_fields=["status"])
                                 
                            logger.info(f"Webhook: Refund {refund.id} Processed")
                    else:
                        logger.warning(f"Webhook: No matching Refund found for payment_id {payment_id}")

        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            # Return 500 so Razorpay retries later (Transient errors like DB locks)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Always return 200 OK to Razorpay if processing was successful (or ignored)
        return Response(status=status.HTTP_200_OK)