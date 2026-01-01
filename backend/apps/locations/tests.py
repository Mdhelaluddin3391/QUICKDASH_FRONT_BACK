from django.test import TestCase
from apps.locations.services import LocationService

class LocationServiceTestCase(TestCase):
    def test_distance_calculation(self):
        # Approx distance between Indiranagar (12.9716, 77.6412) and Koramangala (12.9352, 77.6245) is ~4km
        dist = LocationService.calculate_distance_km(12.9716, 77.6412, 12.9352, 77.6245)
        self.assertAlmostEqual(dist, 4.4, delta=0.5)

    def test_is_serviceable(self):
        # Within 10km
        self.assertTrue(LocationService.is_serviceable(12.9716, 77.6412, 12.9352, 77.6245, max_distance_km=10))
        # Far away
        self.assertFalse(LocationService.is_serviceable(12.0, 77.0, 28.0, 77.0))