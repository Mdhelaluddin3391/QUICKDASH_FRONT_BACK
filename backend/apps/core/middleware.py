import uuid
import logging
from contextvars import ContextVar
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.cache import cache
from django.contrib.gis.geos import Point

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
            response = self.get_response(request)
            response['X-Request-ID'] = request_id
            return response
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
    Resolves Serviceable Warehouse based on Headers.
    """

    def process_request(self, request):
        request.warehouse = None
        request.user_coords = None

        lat = request.headers.get('X-Location-Lat')
        lng = request.headers.get('X-Location-Lng')
        address_id = request.headers.get('X-Address-ID')

        # Strategy A: Address ID (L2)
        if address_id and request.user.is_authenticated:
            from apps.customers.models import CustomerAddress
            try:
                address = CustomerAddress.objects.get(id=address_id, customer__user=request.user)
                request.user_coords = (address.latitude, address.longitude)
                request.warehouse = self._resolve_warehouse(address.latitude, address.longitude)
                return
            except CustomerAddress.DoesNotExist:
                pass 

        # Strategy B: Raw GPS (L1)
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
        
        # FIX: Increased precision to 5 decimals (~1.1 meters)
        cache_key = f"wh_poly_lookup_{round(lat, 5)}_{round(lng, 5)}"
        cached_wh_id = cache.get(cache_key)

        if cached_wh_id:
            try:
                return Warehouse.objects.get(id=cached_wh_id)
            except Warehouse.DoesNotExist:
                cache.delete(cache_key)

        point = Point(float(lng), float(lat), srid=4326)
        
        warehouse = Warehouse.objects.filter(
            delivery_zone__contains=point,
            is_active=True
        ).first()

        if warehouse:
            cache.set(cache_key, warehouse.id, timeout=300)
            return warehouse
        
        return None