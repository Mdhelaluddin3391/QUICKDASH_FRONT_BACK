from django.urls import path
from .views import SendOTPAPIView, MyNotificationListAPIView
from .views import SubscribeFCMTokenView

urlpatterns = [
    path("send-otp/", SendOTPAPIView.as_view()),
    path("my-history/", MyNotificationListAPIView.as_view()),
    path('fcm/subscribe/', SubscribeFCMTokenView.as_view(), name='fcm-subscribe'),
]