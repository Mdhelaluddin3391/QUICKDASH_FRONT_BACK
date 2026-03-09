import logging
from firebase_admin import messaging # Ye import add karna zaroori hai

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework import generics

from .services import OTPService
from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)

try:
    from ipware import get_client_ip
except ImportError:
    def get_client_ip(request):
        return request.META.get('REMOTE_ADDR'), False

class SendOTPAPIView(APIView):
    # ... (Aapka OTP wala code same rahega) ...
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_send'
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        if not phone:
            return Response({"error": "phone required"}, status=status.HTTP_400_BAD_REQUEST)

        client_ip, is_routable = get_client_ip(request)
        if not client_ip:
            client_ip = request.META.get('REMOTE_ADDR')

        try:
            otp = OTPService.create_and_send(phone, ip_address=client_ip)
            return Response({"status": "otp_sent", "debug_otp": otp})
            
        except Exception as exc:
            from apps.utils.exceptions import BusinessLogicException
            if isinstance(exc, BusinessLogicException):
                return Response({
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "type": "BusinessLogicError"
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            raise


class MyNotificationListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


class SubscribeFCMTokenView(APIView):
    # Logged out users bhi subscribe kar payein isliye AllowAny
    permission_classes = [AllowAny] 

    def post(self, request):
        token = request.data.get('token')
        
        if not token:
            return Response({"error": "FCM Token is required"}, status=400)

        try:
            # Token ko in topics par subscribe kar rahe hain
            topics = ['promotions', 'new_arrivals']
            
            for topic in topics:
                # Firebase Admin SDK ka use karke token ko topic se jodna
                response = messaging.subscribe_to_topic([token], topic)
                logger.info(f"Subscribed token to {topic}: {response.success_count} success")

            return Response({"message": "Successfully subscribed to notifications!"}, status=200)
            
        except Exception as e:
            logger.error(f"Error subscribing token: {e}")
            return Response({"error": str(e)}, status=500)