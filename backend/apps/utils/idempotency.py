# apps/utils/idempotency.py
import functools
import hashlib
import json
import zlib
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.response import Response
from rest_framework import status

def idempotent(timeout=86400):
    """
    Decorator to ensure safe retry of non-safe HTTP methods (POST, PATCH).
    Stores COMPRESSED response in Redis for 'timeout' seconds.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(view_instance, request, *args, **kwargs):
            key = request.headers.get("Idempotency-Key")
            
            if not key:
                return Response(
                    {"error": "Idempotency-Key header is required."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 1. Security: Prevent DoS via massive keys
            if len(key) > 128:
                return Response(
                    {"error": "Idempotency-Key too long (max 128 chars)."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 2. Scope key by User to prevent collisions/spoofing
            user_id = request.user.id if request.user.is_authenticated else "anon"
            cache_key = f"idempotency:{user_id}:{key}"
            lock_key = f"lock:{cache_key}"

            # 3. Check Cache (Fast Path)
            cached_response = cache.get(cache_key)
            if cached_response:
                try:
                    # Decompress data
                    data_json = zlib.decompress(cached_response["data_compressed"]).decode("utf-8")
                    data = json.loads(data_json)
                    return Response(data, status=cached_response["status"])
                except (ValueError, zlib.error):
                    # Cache corruption fallback
                    pass

            # 4. Acquire Lock (Prevent concurrent execution of same key)
            if not cache.add(lock_key, "processing", timeout=30):
                return Response(
                    {"error": "Duplicate request in progress."}, 
                    status=status.HTTP_409_CONFLICT
                )

            try:
                # 5. Execute Logic
                response = func(view_instance, request, *args, **kwargs)

                # 6. Cache Success Responses Only (2xx)
                if 200 <= response.status_code < 300:
                    # PERFORMANCE FIX: Compress payload before storage
                    # Reduces Redis memory usage by ~90% for large JSONs
                    response_json = json.dumps(response.data, cls=DjangoJSONEncoder)
                    compressed_data = zlib.compress(response_json.encode("utf-8"))
                    
                    cache.set(cache_key, {
                        "status": response.status_code,
                        "data_compressed": compressed_data
                    }, timeout=timeout)
                
                return response
            finally:
                # 7. Release Lock
                cache.delete(lock_key)
        return wrapper
    return decorator