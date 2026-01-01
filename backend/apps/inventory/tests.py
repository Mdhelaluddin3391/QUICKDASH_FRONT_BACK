# apps/inventory/tests.py
from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch, MagicMock

from apps.warehouse.models import Warehouse, StorageZone, Aisle, Rack, Bin
from apps.inventory.models import InventoryItem
from apps.inventory.services import InventoryService
from apps.utils.exceptions import BusinessLogicException

class InventoryServiceTestCase(TestCase):
    def setUp(self):
        cache.clear()
        
        # Setup Topology
        self.wh = Warehouse.objects.create(
            name="Test WH", code="WH01", warehouse_type="dark_store", 
            city="Test City", state="TS", location="POINT(0 0)"
        )
        zone = StorageZone.objects.create(warehouse=self.wh, name="Z1")
        aisle = Aisle.objects.create(zone=zone, number="A1")
        rack = Rack.objects.create(aisle=aisle, number="R1")
        self.bin = Bin.objects.create(rack=rack, bin_code="B01")

        # Setup Item
        self.item = InventoryItem.objects.create(
            bin=self.bin, sku="SKU-1", product_name="Test Product",
            price=100.00, total_stock=10, reserved_stock=0
        )

    def test_add_stock(self):
        InventoryService.add_stock(self.item, 5, "grn_123")
        self.item.refresh_from_db()
        self.assertEqual(self.item.total_stock, 15)

    def test_reserve_stock_success(self):
        InventoryService.reserve_stock(self.item, 2, "test_ref")
        self.item.refresh_from_db()
        self.assertEqual(self.item.reserved_stock, 2)
        self.assertEqual(self.item.available_stock, 8)

    def test_reserve_stock_insufficient(self):
        with self.assertRaises(BusinessLogicException):
            InventoryService.reserve_stock(self.item, 11, "test_ref")

    def test_commit_stock(self):
        InventoryService.reserve_stock(self.item, 2)
        InventoryService.commit_stock(self.item, 2)
        
        self.item.refresh_from_db()
        self.assertEqual(self.item.total_stock, 8)
        self.assertEqual(self.item.reserved_stock, 0)

    @patch("apps.inventory.services.r")
    def test_reserve_stock_cached_flow(self, mock_redis):
        # Mock Lua Script Object
        mock_script = MagicMock()
        mock_redis.register_script.return_value = mock_script
        
        # Scenario 1: Cache Hit (Success)
        mock_script.return_value = 1 
        success = InventoryService.reserve_stock_cached("SKU-1", self.wh.id, 1)
        self.assertTrue(success)

        # Scenario 2: Cache Miss -> Rehydrate -> Hit
        # First call returns -1 (Miss), Second call returns 1 (Success)
        mock_script.side_effect = [-1, 1] 
        success = InventoryService.reserve_stock_cached("SKU-1", self.wh.id, 1)
        
        self.assertTrue(success)
        # Ensure it tried to set the key from DB
        mock_redis.set.assert_called()