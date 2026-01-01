# apps/catalog/tests.py
from django.test import TestCase
from unittest.mock import patch
from rest_framework.test import APIClient
from apps.catalog.models import Category, Product

class CatalogCacheTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Setup Data for Cache Miss Scenario
        self.category = Category.objects.create(name="Dairy", slug="dairy", is_active=True)
        self.product = Product.objects.create(
            category=self.category,
            name="Milk",
            sku="MILK-001",
            mrp="50.00",
            is_active=True
        )

    @patch("apps.catalog.views.cache")
    def test_cache_logic(self, mock_cache):
        """
        Verifies that the View checks Cache first, then DB.
        """
        
        # Case 1: Cache Miss
        # ------------------
        mock_cache.get.return_value = None  
        # Mock 'add' to return True (Spin Lock acquired)
        mock_cache.add.return_value = True 

        response = self.client.get("/api/v1/catalog/categories/")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], "Dairy")
        
        # Verify it tried to populate cache
        self.assertTrue(mock_cache.set.called)
        
        # Case 2: Cache Hit
        # -----------------
        mock_cache.set.reset_mock()
        fake_data = [{"id": 999, "name": "Cached Cat", "slug": "cached", "products": []}]
        mock_cache.get.return_value = fake_data

        response = self.client.get("/api/v1/catalog/categories/")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, fake_data) # Returns mock data
        mock_cache.set.assert_not_called() # DB skipped