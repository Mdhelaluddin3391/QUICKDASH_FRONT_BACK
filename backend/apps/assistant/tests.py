from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch
from apps.utils.resilience import CircuitBreakerOpenException

User = get_user_model()

class AIAssistantTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(phone="+919999999999", password="pass")
        self.client.force_authenticate(user=self.user)
        cache.clear()

    @patch("apps.assistant.views.AIShoppingAssistantView.call_llm_provider")
    def test_successful_query(self, mock_llm):
        mock_llm.return_value = {"reply": "Hello", "action": None}
        
        response = self.client.post("/api/v1/assistant/chat/", {"query": "Milk"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reply"], "Hello")

    @patch("apps.assistant.views.AIShoppingAssistantView.call_llm_provider")
    def test_circuit_breaker_open(self, mock_llm):
        # Simulate Circuit Breaker Exception
        mock_llm.side_effect = CircuitBreakerOpenException("Open")
        
        response = self.client.post("/api/v1/assistant/chat/", {"query": "Milk"})
        
        # Should catch exception and return 503 user friendly message
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("having trouble connecting", response.data["reply"])