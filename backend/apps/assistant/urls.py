# apps/assistant/urls.py - FULL UPDATED FILE
from django.urls import path
from .views import AIShoppingAssistantView

urlpatterns = [
    # Frontend /api/v1/assistant/chat/ call karta hai
    path("chat/", AIShoppingAssistantView.as_view(), name="ai-chat"),
]