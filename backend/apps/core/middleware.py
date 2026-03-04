import uuid
import logging
from contextvars import ContextVar
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib.gis.geos import Point
from django.conf import settings

logger = logging.getLogger(__name__)

_correlation_id = ContextVar("correlation_id", default=None)

def get_correlation_id():
    return _correlation_id.get()

class CorrelationIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        token = _correlation_id.set(request_id)
        request.correlation_id = request_id
        try:
            return self.get_response(request)
        finally:
            _correlation_id.reset(token)

class GlobalKillSwitchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            try:
                if cache.get("config:kill_switch:active"):
                    return JsonResponse(
                        {"error": {"code": "maintenance_mode", "message": "System maintenance."}}, 
                        status=503
                    )
            except Exception:
                return JsonResponse({"error": "System error"}, status=503)
        return self.get_response(request)

class LocationContextMiddleware(MiddlewareMixin):
    """
    Resolves Serviceable Warehouse based on Headers for the Mobile App/Frontend.
    """
    def process_request(self, request):
        request.warehouse = None
        request.user_coords = None

        lat = request.headers.get('X-Location-Lat')
        lng = request.headers.get('X-Location-Lng')
        address_id = request.headers.get('X-Address-ID')

        if address_id and request.user.is_authenticated:
            from apps.customers.models import CustomerAddress
            try:
                address = CustomerAddress.objects.get(id=address_id, customer__user=request.user)
                request.user_coords = (address.latitude, address.longitude)
                request.warehouse = self._resolve_warehouse(address.latitude, address.longitude)
                return
            except CustomerAddress.DoesNotExist:
                pass 

        if lat and lng:
            try:
                lat = float(lat)
                lng = float(lng)
                request.user_coords = (lat, lng)
                request.warehouse = self._resolve_warehouse(lat, lng)
            except (ValueError, TypeError):
                pass

    def _resolve_warehouse(self, lat, lng):
        from apps.warehouse.models import Warehouse
        point = Point(float(lng), float(lat), srid=4326)
        return Warehouse.objects.filter(delivery_zone__contains=point, is_active=True).first()