# apps/delivery/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import status
from django.shortcuts import get_object_or_404
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Delivery
from .serializers import DeliverySerializer, DeliveryCompleteSerializer
from .services import DeliveryService, StorageService
from .tasks import retry_auto_assign_rider
from apps.orders.models import Order
from apps.riders.models import RiderProfile

class AdminAssignDeliveryAPIView(APIView):
    """
    Admin-only: Assign a specific rider to an order.
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        order_id = request.data.get("order_id")
        rider_id = request.data.get("rider_id")

        order = get_object_or_404(Order, id=order_id)
        rider = get_object_or_404(RiderProfile, id=rider_id)

        if rider.current_warehouse != order.warehouse:
            return Response(
                {"error": "Rider location mismatch (Different Warehouse)"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Pass 'request.user' as the actor for audit logging
        delivery = DeliveryService.assign_rider(order, rider, actor=request.user)
        return Response(DeliverySerializer(delivery).data, status=status.HTTP_201_CREATED)


class MyDeliveriesAPIView(APIView):
    """
    Rider: List assigned deliveries.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "User is not a rider"}, status=status.HTTP_403_FORBIDDEN)
             
        rider = request.user.rider_profile
        qs = Delivery.objects.filter(rider=rider)\
            .select_related('order', 'order__warehouse', 'order__user')\
            .order_by("-created_at")
            
        return Response(DeliverySerializer(qs, many=True).data)


class DeliveryCompleteAPIView(APIView):
    """
    Rider: Mark delivery as complete (Requires OTP & Proof).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, delivery_id):
        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "User is not a rider"}, status=status.HTTP_403_FORBIDDEN)

        delivery = get_object_or_404(
            Delivery,
            id=delivery_id,
            rider=request.user.rider_profile,
        )

        serializer = DeliveryCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        DeliveryService.mark_delivered(
            delivery,
            otp=serializer.validated_data["otp"],
            proof_image_key=serializer.validated_data.get("proof_image_key"),
        )

        return Response({"status": "delivered"})


class RiderLocationPingAPIView(APIView):
    """
    Rider: High-frequency GPS updates.
    Secured with ScopedRateThrottle & WebSocket broadcast.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'location_ping'

    def post(self, request, order_id):
        try:
            lat = float(request.data.get("latitude"))
            lng = float(request.data.get("longitude"))
        except (TypeError, ValueError):
            return Response({"error": "Invalid coordinates"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Bounds Check
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return Response({"error": "Coordinates out of bounds"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Authorization Check (Optimized)
        # Ensure user is the assigned rider for this active order
        is_authorized = Order.objects.filter(
            id=order_id,
            delivery__rider__user=request.user,
            delivery__status__in=['picked_up', 'out_for_delivery']
        ).exists()

        if not is_authorized:
            return Response({"error": "Unauthorized or inactive delivery"}, status=status.HTTP_403_FORBIDDEN)

        # 3. Broadcast to WebSocket (Fire & Forget)
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"tracking_{order_id}",
                {
                    "type": "location_broadcast",
                    "lat": lat,
                    "lng": lng,
                    "rider_id": request.user.id
                }
            )
        except Exception:
            pass # Fail silently to keep HTTP API fast

        return Response({"status": "synced"})


class GenerateUploadURLAPIView(APIView):
    """
    Rider: Get secure presigned URL for proof upload.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "User is not a rider"}, status=status.HTTP_403_FORBIDDEN)

        order = get_object_or_404(Order, id=order_id)
        
        # Verify assignment
        if not hasattr(order, 'delivery') or order.delivery.rider != request.user.rider_profile:
            return Response({"error": "You are not assigned to this order"}, status=status.HTTP_403_FORBIDDEN)

        try:
            # Generate Secure POST Policy
            data = StorageService.generate_presigned_post(order_id, "image/jpeg")
            return Response(data)
        except Exception:
            return Response({"error": "Storage service unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RiderAcceptDeliveryAPIView(APIView):
    """
    Rider: Accept or Reject an assigned delivery.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, delivery_id):
        if not hasattr(request.user, 'rider_profile'):
             return Response({"error": "Not a rider"}, status=status.HTTP_403_FORBIDDEN)
             
        action = request.data.get("action")
        if action not in ['accept', 'reject']:
            return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
            
        delivery = get_object_or_404(Delivery, id=delivery_id)
        
        # Security: Ensure it's assigned to THIS rider
        if delivery.rider != request.user.rider_profile:
             return Response({"error": "This delivery is not assigned to you"}, status=status.HTTP_403_FORBIDDEN)

        if action == 'accept':
            if delivery.status != 'assigned':
                 return Response({"error": "Delivery no longer available"}, status=status.HTTP_400_BAD_REQUEST)
            # Logic for acceptance (Updates timestamp, etc.)
            return Response({"status": "accepted"})
            
        elif action == 'reject':
            # Release back to pool
            delivery.rider = None
            delivery.job_status = 'searching'
            delivery.status = 'assigned' # Reset state
            delivery.save()
            
            # Trigger re-assignment
            retry_auto_assign_rider.delay(delivery.order.id)
            
            return Response({"status": "rejected"})


class HandoverVerificationAPIView(APIView):
    """
    Rider: Verify package handover from warehouse (Scan).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        if not order_id:
            return Response({"error": "Order ID required"}, status=status.HTTP_400_BAD_REQUEST)

        # Ensure order exists and is ready for handover
        order = get_object_or_404(Order, id=order_id)
        
        if order.status != "packed":
             return Response({"error": "Order is not ready for handover"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "verified", "order_id": order.id})