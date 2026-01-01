# apps/locations/services.py
import math
from decimal import Decimal
from .models import GeoLocation

class LocationService:
    EARTH_RADIUS_KM = 6371

    @staticmethod
    def calculate_distance_km(lat1, lon1, lat2, lon2) -> float:
        """
        Calculates distance between two points using Haversine formula.
        Returns distance in Kilometers.
        """
        # Convert to float for math operations
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )

        c = 2 * math.asin(math.sqrt(a))
        return LocationService.EARTH_RADIUS_KM * c

    @staticmethod
    def is_serviceable(
        customer_lat,
        customer_lon,
        warehouse_lat,
        warehouse_lon,
        max_distance_km: int = 10,
    ) -> bool:
        distance = LocationService.calculate_distance_km(
            customer_lat,
            customer_lon,
            warehouse_lat,
            warehouse_lon,
        )
        return distance <= max_distance_km

    @staticmethod
    def save_location(user, data: dict) -> GeoLocation:
        return GeoLocation.objects.create(
            user=user,
            label=data.get("label", "Pinned"),
            address_text=data.get("address_text", ""),
            latitude=Decimal(str(data["latitude"])),
            longitude=Decimal(str(data["longitude"])),
        )