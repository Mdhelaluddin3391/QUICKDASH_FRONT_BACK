from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.permissions import AllowAny
from rest_framework import status
from .services import OTPService
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.permissions import AllowAny
from rest_framework import status
from .services import OTPService


try:
    from ipware import get_client_ip
except ImportError:
    def get_client_ip(request):
        return request.META.get('REMOTE_ADDR'), False



class SendOTPAPIView(APIView):
    """
    Public Endpoint: Triggers OTP SMS.
    """
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
            
           
            return Response({
                "status": "otp_sent", 
                "debug_otp": otp 
            })
            
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