import time
import logging
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from .models import StoreSettings

logger = logging.getLogger(__name__)

def health_check(request):
    """
    Liveness Probe.
    Returns 200 if DB/Redis are up.
    Returns 503 ONLY if critical infrastructure is unreachable.
    """
    status_data = {
        "status": "ok", 
        "services": {"db": "ok", "redis": "ok", "beat": "ok"}
    }
    http_status = 200

    # 1. Check Database (Critical)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        logger.critical(f"Health Check DB Fail: {e}")
        status_data["status"] = "error"
        status_data["services"]["db"] = "unreachable"
        return JsonResponse(status_data, status=503)

    # 2. Check Redis (Critical)
    try:
        cache.set("health_ping", "pong", timeout=5)
        if cache.get("health_ping") != "pong":
            raise Exception("Redis R/W mismatch")
    except Exception as e:
        logger.critical(f"Health Check Redis Fail: {e}")
        status_data["status"] = "error"
        status_data["services"]["redis"] = "unreachable"
        return JsonResponse(status_data, status=503)

    # 3. Check Celery Beat (Non-Critical for Liveness, Critical for Alerts)
    # Don't fail the HTTP probe (503) just because Beat is slow, 
    # otherwise K8s will restart the Web container unnecessarily.
    try:
        last_beat = cache.get("celery_beat_health")
        if last_beat is None:
            status_data["services"]["beat"] = "warming_up"
        else:
            # If heartbeat is older than 90s, mark as stuck but keep HTTP 200
            if time.time() - float(last_beat) > 90:
                 status_data["services"]["beat"] = "stuck"
                 status_data["status"] = "degraded" 
    except Exception:
        status_data["services"]["beat"] = "unknown"

    return JsonResponse(status_data, status=http_status)


class AppConfigAPIView(APIView):
    """
    Public Bootstrap Endpoint for Frontend Apps.
    Controls versioning, force updates, and maintenance mode.
    SECURELY exposes public keys (like Google Maps) to authenticated/unauthenticated clients.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        # Fetch dynamic config from Redis or Env
        maintenance_mode = cache.get("config:maintenance_mode", False)
        
        return Response({
            "maintenance_mode": maintenance_mode,
            "keys": {
                "google_maps": getattr(settings, "GOOGLE_MAPS_KEY", ""),
            },
            "android": {
                "min_version": 102,
                "latest_version": 105,
                "force_update": False,
                "store_url": "https://play.google.com/store/apps/details?id=com.quickdash"
            },
            "ios": {
                "min_version": "1.0.2",
                "latest_version": "1.0.5",
                "force_update": False,
                "store_url": "https://apps.apple.com/app/id123456789"
            },
            "support": {
                "phone": "+919999999999",
                "email": "support@quickdash.com"
            }
        })
    



class StoreStatusAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        settings, created = StoreSettings.objects.get_or_create(pk=1)
        return Response({
            'is_store_open': settings.is_store_open,
            'store_closed_message': settings.store_closed_message
        })