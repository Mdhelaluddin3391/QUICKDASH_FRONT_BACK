# apps/payments/urls.py
from django.urls import path
from .views import (
    CreatePaymentAPIView, 
    RazorpayVerifyAPIView, 
    RazorpayWebhookAPIView
)

urlpatterns = [
    path("create/<int:order_id>/", CreatePaymentAPIView.as_view()),
    path("verify/razorpay/", RazorpayVerifyAPIView.as_view()),
    path("webhook/razorpay/", RazorpayWebhookAPIView.as_view()),
]