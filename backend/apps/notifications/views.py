# apps/notifications/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.permissions import AllowAny
from rest_framework import status
from .services import OTPService

# apps/notifications/views.py (Existing file mein add karein)
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer
# Security: Use ipware to robustly determine client IP and prevent spoofing.
# It handles proxy chains, private IPs, and IPv6 correctly.
try:
    from ipware import get_client_ip
except ImportError:
    # Safe Fallback if library is missing (e.g. during minimal CI runs)
    def get_client_ip(request):
        return request.META.get('REMOTE_ADDR'), False

class SendOTPAPIView(APIView):
    """
    Public Endpoint: Triggers OTP SMS.
    Strictly throttled to prevent SMS pumping attacks.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_send'
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get("phone")
        if not phone:
            return Response({"error": "phone required"}, status=status.HTTP_400_BAD_REQUEST)

        # Bot Detection: Extract Real IP Securely to prevent spoofing
        client_ip, is_routable = get_client_ip(request)
        
        # Fallback for direct access but prioritize X-Forwarded-For via ipware
        if not client_ip:
            client_ip = request.META.get('REMOTE_ADDR')

        # Delegate to Service which now handles IP-based rate limiting in Redis
        try:
            OTPService.create_and_send(phone, ip_address=client_ip)
            return Response({"status": "otp_sent", "debug_otp": otp})
        except Exception as exc:
            # Map BusinessLogicException to friendly client response
            from apps.utils.exceptions import BusinessLogicException
            if isinstance(exc, BusinessLogicException):
                return Response({
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "type": "BusinessLogicError"
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            # Re-raise unexpected errors so they show up in logs and Sentry
            raise




class MyNotificationListAPIView(generics.ListAPIView):
    """
    User: View past notifications history.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')



# class VerifyOTPAPIView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         phone = request.data.get("phone")
#         otp = request.data.get("otp")

#         if not phone or not otp:
#              return Response({"error": "Missing phone or otp"}, status=status.HTTP_400_BAD_REQUEST)

#         OTPService.verify(phone, otp)
        
#         # If verify succeeds, frontend will proceed to auth token exchange
#         # (Usually separate endpoint, or we can issue token here. 
#         #  Sticking to verify-only per spec).
#         return Response({"status": "otp_verified"})