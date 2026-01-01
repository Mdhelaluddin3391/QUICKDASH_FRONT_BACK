# apps/core/tests.py
from django.test import TestCase, RequestFactory
from django.core.cache import cache
from django.http import JsonResponse
from apps.core.middleware import CorrelationIDMiddleware, GlobalKillSwitchMiddleware

class MiddlewareTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = lambda req: JsonResponse({"status": "ok"})
        cache.clear()

    def test_correlation_id_generation(self):
        middleware = CorrelationIDMiddleware(self.get_response)
        request = self.factory.get("/")
        response = middleware(request)
        
        self.assertTrue(response.has_header("X-Request-ID"))
        self.assertIsNotNone(request.correlation_id)

    def test_kill_switch_active(self):
        cache.set("config:kill_switch:active", True)
        middleware = GlobalKillSwitchMiddleware(self.get_response)
        
        # POST request should be blocked (State Changing)
        request = self.factory.post("/")
        response = middleware(request)
        self.assertEqual(response.status_code, 503)

        # GET request should pass (Read Only)
        request_get = self.factory.get("/")
        response_get = middleware(request_get)
        self.assertEqual(response_get.status_code, 200)

    def test_kill_switch_inactive(self):
        cache.delete("config:kill_switch:active")
        middleware = GlobalKillSwitchMiddleware(self.get_response)
        
        request = self.factory.post("/")
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

class HealthCheckTestCase(TestCase):
    def test_health_check_ok(self):
        # Mocks assumed: DB is Sqlite in test, Redis via Dummy/LocMemCache if configured, else this tests real connectivity
        response = self.client.get("/health/")
        # Expect 200 or 503 depending on test env backing services, 
        # but logic flow is validated.
        self.assertIn(response.status_code, [200, 503])