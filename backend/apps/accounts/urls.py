# apps/accounts/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    MeAPIView, 
    CustomerRegisterAPIView, 
    WebSocketTicketAPIView,
    LogoutAPIView,
    RequestPasswordResetAPIView,
    SetNewPasswordAPIView,
    DeleteAccountAPIView
)

urlpatterns = [
    path("me/", MeAPIView.as_view()),
    path("register/customer/", CustomerRegisterAPIView.as_view()),
    
    # [AUDIT FIX] Added Token Refresh Endpoint
    path("refresh/", TokenRefreshView.as_view(), name='token_refresh'),
    
    path("ws/ticket/", WebSocketTicketAPIView.as_view()),
    path("logout/", LogoutAPIView.as_view()),
    
    # Password Management
    path("password-reset/", RequestPasswordResetAPIView.as_view()),
    path("password-reset/confirm/", SetNewPasswordAPIView.as_view()),

    path("delete/", DeleteAccountAPIView.as_view()),
]