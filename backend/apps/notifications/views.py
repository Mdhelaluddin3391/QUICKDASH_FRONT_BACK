import logging
from firebase_admin import messaging # Firebase notifications ke liye

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework import generics
from django.conf import settings
from .services import OTPService
from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)

# IP address fetch karne ke liye fallback mechanism
try:
    from ipware import get_client_ip
except ImportError:
    def get_client_ip(request):
        return request.META.get('REMOTE_ADDR'), False


class SendOTPAPIView(APIView):
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
            
            # Response Data Prepare Karein
            response_data = {"status": "otp_sent"}
            
            # SMART FALLBACK: Agar Twilio Configure NAHI hai, tabhi OTP response mein bhejo
            has_twilio = bool(getattr(settings, 'TWILIO_ACCOUNT_SID', None) and 
                              getattr(settings, 'TWILIO_AUTH_TOKEN', None) and 
                              getattr(settings, 'TWILIO_PHONE_NUMBER', None))
            
            if not has_twilio or settings.DEBUG:
                response_data["debug_otp"] = otp
                
            return Response(response_data, status=status.HTTP_200_OK)
            
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
        # User ki saari notifications fetch karna, latest pehle aayegi
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


class SubscribeFCMTokenView(APIView):
    # Logged out users bhi subscribe kar payein isliye AllowAny
    permission_classes = [AllowAny] 

    def post(self, request):
        token = request.data.get('token')
        
        if not token:
            return Response({"error": "FCM Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # 1. Agar user logged in hai, toh uska token DB (User model) mein save karein
            if request.user.is_authenticated:
                request.user.fcm_token = token
                request.user.save(update_fields=['fcm_token'])
                logger.info(f"FCM Token saved for user {request.user.phone}")

            # 2. Token ko topics par subscribe karein (sabke liye - global alerts ke liye)
            topics = ['promotions', 'new_arrivals']
            for topic in topics:
                # Firebase Admin SDK ka use karke token ko topic se jodna
                response = messaging.subscribe_to_topic([token], topic)
                logger.info(f"Subscribed token to {topic}: {response.success_count} success")

            return Response({"message": "Successfully subscribed to notifications!"}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error subscribing token: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)