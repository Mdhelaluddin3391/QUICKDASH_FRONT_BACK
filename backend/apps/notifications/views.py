import logging
from firebase_admin import messaging
from apps.accounts.models import UserDevice
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
            response_data = {"status": "otp_sent"}
            
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
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
class SubscribeFCMTokenView(APIView):
    permission_classes = [AllowAny] 

    def post(self, request):
        fcm_token = request.data.get('token') or request.data.get('fcm_token')

        if not fcm_token:
            return Response({"error": "FCM Token required"}, status=400)

        # 🔥 NAYA CODE: Agar kisi purane user par ye token chipka hai toh usko delete kar do
        UserDevice.objects.filter(fcm_token=fcm_token).exclude(user=request.user).delete()

        # Ab securely is current user ke paas save kar do
        UserDevice.objects.get_or_create(
            user=request.user,
            fcm_token=fcm_token,
            defaults={'device_type': 'app_or_web'}
        )
        
        # Fallback ke liye purane model par bhi update kar sakte hain
        request.user.fcm_token = fcm_token
        request.user.save(update_fields=['fcm_token'])

        return Response({"message": "Successfully subscribed to push notifications."})