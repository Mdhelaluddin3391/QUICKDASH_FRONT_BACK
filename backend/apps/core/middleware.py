# apps/core/middleware.py
import uuid
import logging
from contextvars import ContextVar
from django.http import JsonResponse
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ContextVar is essential for async/ASGI safety (unlike threading.local)
_correlation_id = ContextVar("correlation_id", default=None)

def get_correlation_id():
    return _correlation_id.get()

class CorrelationIDMiddleware:
    """
    Attaches a unique Request ID to every request for distributed tracing.
    Crucial for debugging across Nginx, Gunicorn, Celery, and Postgres.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Prefer upstream header from LB/Nginx
        request_id = request.headers.get('X-Request-ID')
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # 2. Set context variable for this request chain
        token = _correlation_id.set(request_id)
        
        # 3. Attach to request object for easy view access
        request.correlation_id = request_id

        try:
            response = self.get_response(request)
            # 4. Expose in Response Header for client-side tracing
            response['X-Request-ID'] = request_id
            return response
        finally:
            # 5. Clean up context to prevent leakage in async pools
            _correlation_id.reset(token)


class GlobalKillSwitchMiddleware:
    """
    Emergency Stop: Rejects state-changing requests if KILL_SWITCH is active.
    Used during critical incidents or maintenance.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only block state-changing methods (POST, PUT, PATCH, DELETE)
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            try:
                # Key: 'config:kill_switch:active'
                if cache.get("config:kill_switch:active"):
                    logger.warning(f"Kill Switch Blocked Request: {request.path} | IP: {request.META.get('REMOTE_ADDR')}")
                    return self._reject_request(request)
                    
            except Exception as e:
                # SECURITY FIX: Fail Closed
                # If Redis is down, we cannot guarantee the system is safe to write to.
                # We block write traffic to prevent data corruption or inconsistencies.
                logger.critical(f"CRITICAL: Kill Switch State Unknown (Redis Down). Blocking Write Traffic. Error: {e}")
                return JsonResponse(
                    {
                        "error": {
                            "code": "system_outage", 
                            "message": "System is temporarily unavailable due to internal checks."
                        }
                    }, 
                    status=503
                )

        return self.get_response(request)

    def _reject_request(self, request):
        return JsonResponse(
            {
                "error": {
                    "code": "maintenance_mode", 
                    "message": "System is under maintenance. Read-only mode active."
                }
            }, 
            status=503
        )