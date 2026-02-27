import uuid
import time
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken
from rest_framework_simplejwt.exceptions import TokenError
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings

import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth as firebase_auth
import json
if not firebase_admin._apps:
    
    firebase_creds_env = os.getenv('FIREBASE_JSON_CREDENTIALS')
    
    if firebase_creds_env:
        cred_dict = json.loads(firebase_creds_env)
        cred = credentials.Certificate(cred_dict)
    else:
        firebase_key_path = os.path.join(settings.BASE_DIR, 'firebase-key.json')
        cred = credentials.Certificate(firebase_key_path)
        
    firebase_admin.initialize_app(cred)

from .serializers import (
    UserSerializer, 
    PasswordResetRequestSerializer, 
    PasswordResetConfirmSerializer
)
from .services import AccountService
from apps.notifications.services import OTPService 

User = get_user_model()

class RegistrationThrottle(AnonRateThrottle):
    scope = 'registration'

class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class CustomerRegisterAPIView(APIView):
    """
    Combines OTP Verification AND Registration/Login.
    Supports both Firebase Token Verification and Local OTP Fallback.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RegistrationThrottle]

    def post(self, request):
        login_type = request.data.get("login_type", "local") 
        phone = request.data.get("phone")

        if login_type == "firebase":
            firebase_token = request.data.get("token")
            if not firebase_token:
                return Response({"error": "Firebase token missing"}, status=status.HTTP_400_BAD_REQUEST)
            try:
                decoded_token = firebase_auth.verify_id_token(firebase_token)
                phone = decoded_token.get('phone_number') 
            except Exception as e:
                return Response({"error": f"Firebase Verification Failed: {str(e)}"}, status=status.HTTP_401_UNAUTHORIZED)
        
        else:
            otp = request.data.get("otp")
            if not phone or not otp:
                return Response({"error": "Phone and OTP required"}, status=status.HTTP_400_BAD_REQUEST)
            try:
                OTPService.verify(phone, otp)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not phone:
             return Response({"error": "Invalid phone number"}, status=status.HTTP_400_BAD_REQUEST)

        user = AccountService.create_customer(phone)
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "message": "Login successful", 
            "user_id": user.id,
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }, status=status.HTTP_200_OK)

class WebSocketTicketAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        ticket = str(uuid.uuid4())
        cache.set(f"ws_ticket:{ticket}", request.user.id, timeout=30)
        return Response({"ticket": ticket})



class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == 'bearer':
                    raw_token = parts[1]
                    try:
                        token = UntypedToken(raw_token)
                        jti = token['jti']
                        exp = token['exp']
                        ttl = int(exp - time.time())
                        if ttl > 0: cache.set(f"blocklist:{jti}", "true", timeout=ttl)
                    except TokenError: pass
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                jti = token['jti']
                cache.set(f"blocklist:{jti}", "true", timeout=86400 * 7)
            return Response({"status": "logged_out"})
        except Exception:
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)



class RequestPasswordResetAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.filter(email=email).first()
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            link = f"https://quickdash.com/reset-password?uid={uid}&token={token}"
            send_mail("Password Reset Request", f"Click here to reset your password: {link}", settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
        return Response({"message": "If email exists, reset link sent."})

class SetNewPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            uid = force_str(urlsafe_base64_decode(serializer.validated_data['uidb64']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Invalid link"}, status=status.HTTP_400_BAD_REQUEST)
        token = serializer.validated_data['token']
        if not default_token_generator.check_token(user, token):
             return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({"status": "password_reset_complete"})


class DeleteAccountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.is_active = False 
        user.save()
        return Response({"status": "account_deleted"})