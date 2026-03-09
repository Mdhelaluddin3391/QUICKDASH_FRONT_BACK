from django.urls import path
from .views import AuditLogListAPIView

urlpatterns = [
    path("logs/", AuditLogListAPIView.as_view()),
]
