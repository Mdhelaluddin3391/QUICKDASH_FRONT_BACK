import time
import logging
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.views.generic import TemplateView, View
from django.shortcuts import redirect
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages

from .models import StoreSettings
from apps.warehouse.models import Warehouse

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

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        logger.critical(f"Health Check DB Fail: {e}")
        status_data["status"] = "error"
        status_data["services"]["db"] = "unreachable"
        return JsonResponse(status_data, status=503)

    try:
        cache.set("health_ping", "pong", timeout=5)
        if cache.get("health_ping") != "pong":
            raise Exception("Redis R/W mismatch")
    except Exception as e:
        logger.critical(f"Health Check Redis Fail: {e}")
        status_data["status"] = "error"
        status_data["services"]["redis"] = "unreachable"
        return JsonResponse(status_data, status=503)

 
    try:
        last_beat = cache.get("celery_beat_health")
        if last_beat is None:
            status_data["services"]["beat"] = "warming_up"
        else:
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
        settings_obj, created = StoreSettings.objects.get_or_create(pk=1)
        return Response({
            'is_store_open': settings_obj.is_store_open,
            'store_closed_message': settings_obj.store_closed_message
        })


# --- ENTERPRISE ADMIN WAREHOUSE SELECTION VIEWS ---

class AdminWarehouseSelectView(UserPassesTestMixin, TemplateView):
    """Renders the UI for the Admin to choose their operational store."""
    template_name = 'admin/select_warehouse.html'

    def test_func(self):
        # Only allow staff/admin users
        return self.request.user.is_authenticated and self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch only active warehouses to show on the screen
        context['warehouses'] = Warehouse.objects.filter(is_active=True).order_by('warehouse_type', 'name')
        return context


class SetAdminWarehouseView(UserPassesTestMixin, View):
    """Processes the admin's selection, locks it into the session, and redirects to the dashboard."""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def get(self, request, warehouse_id, *args, **kwargs):
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id, is_active=True)
            # Lock the selection in the session securely
            request.session['selected_warehouse_id'] = warehouse.id
            request.session['selected_warehouse_name'] = warehouse.name
            messages.success(request, f"Operational Command switched to: {warehouse.name}")
        except Warehouse.DoesNotExist:
            messages.error(request, "Selected warehouse is invalid or inactive.")
        
        # Redirect back to the main admin dashboard
        return redirect('admin:index')