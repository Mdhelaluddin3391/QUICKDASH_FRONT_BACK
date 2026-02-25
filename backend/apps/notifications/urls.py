from django.urls import path
from .views import SendOTPAPIView, MyNotificationListAPIView

urlpatterns = [
    path("send-otp/", SendOTPAPIView.as_view()),
    path("my-history/", MyNotificationListAPIView.as_view()),
]