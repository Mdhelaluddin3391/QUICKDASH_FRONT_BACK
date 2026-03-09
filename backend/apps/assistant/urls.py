from django.urls import path
from .views import AIShoppingAssistantView

urlpatterns = [
    path("chat/", AIShoppingAssistantView.as_view(), name="ai-chat"),
]