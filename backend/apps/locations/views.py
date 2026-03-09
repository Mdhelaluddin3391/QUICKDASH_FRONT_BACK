import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.conf import settings
from .models import GeoLocation
from .serializers import GeoLocationSerializer
from .services import LocationService
from django.core.cache import cache

class GeocodeAPIView(APIView):
    """
    Proxies requests to OpenStreetMap Nominatim with Caching & Resilience.
    """
    permission_classes = [AllowAny] 

    def get(self, request):
        try:
            lat = float(request.query_params.get('lat'))
            lon = float(request.query_params.get('lon'))
        except (TypeError, ValueError):
            return Response({"error": "Invalid coordinates"}, status=status.HTTP_400_BAD_REQUEST)

       
        lat_r = round(lat, 4)
        lon_r = round(lon, 4)
        
        cache_key = f"geocode:{lat_r}:{lon_r}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        headers = {
            'User-Agent': 'QuickDash-App/1.0 (contact@quickdash.com)',
            'Referer': 'https://quickdash.com' 
        }
        
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
            resp = requests.get(url, headers=headers, timeout=3) 
            
            if resp.status_code == 200:
                data = resp.json()
                
                result = {
                    "display_name": data.get("display_name"),
                    "address": data.get("address", {}),
                    "place_id": data.get("place_id")
                }
                
                cache.set(cache_key, result, timeout=86400)
                return Response(result)
            else:
                logger.error(f"Geocoding Provider Error: {resp.status_code}")
                return Response(
                    {"error": "Location service temporarily unavailable"}, 
                    status=status.HTTP_502_BAD_GATEWAY
                )
        except Exception as e:
            logger.error(f"Geocoding Exception: {e}")
            return Response(
                {"error": "Unable to detect location address"}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

class SaveLocationAPIView(APIView):
    """
    Saves a raw geolocation pin (e.g. from Map Picker).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GeoLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        location = LocationService.save_location(user, serializer.validated_data)
        return Response(GeoLocationSerializer(location).data, status=status.HTTP_201_CREATED)


class MyLocationsListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        locs = GeoLocation.objects.filter(user=request.user, is_active=True).order_by("-created_at")
        return Response(GeoLocationSerializer(locs, many=True).data)