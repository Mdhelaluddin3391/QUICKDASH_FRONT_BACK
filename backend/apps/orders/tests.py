from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.warehouse.models import Warehouse, StorageZone, Aisle, Rack, Bin
from apps.inventory.models import InventoryItem
from apps.orders.models import Order
from apps.orders.services import OrderService
from apps.riders.models import RiderProfile

User = get_user_model()

class OrderIntegrationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # User & Auth
        self.user = User.objects.create_user(phone="+919999999999", password="pass")
        self.client.force_authenticate(user=self.user)
        
        # Warehouse Setup
        self.wh = Warehouse.objects.create(
            name="WH", code="WH1", warehouse_type="dark_store", 
            city="BLR", state="KA", location="POINT(0 0)"
        )
        
        # Inventory Setup
        zone = StorageZone.objects.create(warehouse=self.wh, name="Z")
        aisle = Aisle.objects.create(zone=zone, number="1")
        rack = Rack.objects.create(aisle=aisle, number="1")
        bin = Bin.objects.create(rack=rack, bin_code="B1")
        
        self.item = InventoryItem.objects.create(
            bin=bin, sku="MILK", product_name="Milk",
            price=50, total_stock=100
        )

        # Rider
        self.rider_user = User.objects.create_user(phone="+918888888888", password="pass")
        self.rider_user.roles.create(role="rider")
        self.rider = RiderProfile.objects.create(
            user=self.rider_user, current_warehouse=self.wh, 
            is_active=True, is_available=True
        )

    def test_full_order_flow(self):
        """
        Test: Create -> Reserve -> Cancel -> Release
        """
        # 1. Create Order
        order = OrderService.create_order(
            user=self.user,
            warehouse=self.wh,
            items=[{"sku": "MILK", "quantity": 2}],
            delivery_type="express"
        )
        
        self.assertEqual(order.total_amount, 100) # 50 * 2
        
        # Check Inventory Reserved
        self.item.refresh_from_db()
        self.assertEqual(self.item.reserved_stock, 2)
        self.assertEqual(self.item.available_stock, 98)

        # 2. Cancel Order
        OrderService.cancel_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, "cancelled")

        # Check Inventory Released
        self.item.refresh_from_db()
        self.assertEqual(self.item.reserved_stock, 0)
        self.assertEqual(self.item.available_stock, 100)

    def test_create_order_out_of_stock(self):
        with self.assertRaises(Exception) as context:
             OrderService.create_order(
                user=self.user,
                warehouse=self.wh,
                items=[{"sku": "MILK", "quantity": 101}],
                delivery_type="express"
            )
        self.assertIn("Insufficient stock", str(context.exception))