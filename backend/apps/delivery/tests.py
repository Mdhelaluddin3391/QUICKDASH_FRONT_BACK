# apps/delivery/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from apps.warehouse.models import Warehouse
from apps.orders.models import Order
from apps.delivery.models import Delivery
from apps.delivery.services import DeliveryService
from apps.delivery.auto_assign import AutoRiderAssignmentService
from apps.riders.models import RiderProfile

User = get_user_model()

class DeliveryServiceTestCase(TestCase):
    def setUp(self):
        self.wh = Warehouse.objects.create(name="WH", code="W1", warehouse_type="dark_store", location="POINT(0 0)")
        self.customer = User.objects.create_user(phone="+919000000000", password="pass")
        self.rider_user = User.objects.create_user(phone="+919111111111", password="pass")
        self.rider_user.roles.create(role="rider")
        
        self.rider = RiderProfile.objects.create(
            user=self.rider_user, current_warehouse=self.wh, 
            is_active=True, is_available=True
        )
        
        self.order = Order.objects.create(
            user=self.customer, warehouse=self.wh, status="packed", 
            delivery_type="express", total_amount=200
        )
        self.order.items.create(sku="SKU1", quantity=1, price=200, product_name="P1")

    def test_auto_assign(self):
        # Force Assignment
        DeliveryService.initiate_delivery_search(self.order)
        
        delivery = AutoRiderAssignmentService.assign(self.order)
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.rider, self.rider)
        self.assertEqual(delivery.status, "assigned")

    def test_mark_delivered_success(self):
        delivery = DeliveryService.initiate_delivery_search(self.order)
        delivery.rider = self.rider
        delivery.status = "picked_up"
        delivery.otp = "123456"
        delivery.save()

        # Mock Inventory Commit logic
        with patch("apps.inventory.services.InventoryService.commit_stock"):
             DeliveryService.mark_delivered(delivery, "123456")
        
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "delivered")
        
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "delivered")

class DeliveryAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(phone="+918888888888", password="pass")
        self.wh = Warehouse.objects.create(name="W", code="W", location="POINT(0 0)")
        self.order = Order.objects.create(
            user=self.user, warehouse=self.wh,
            status="out_for_delivery", total_amount=100, delivery_type="express"
        )
        
        # Assign Rider
        self.rider_user = User.objects.create_user(phone="+917777777777", password="pass")
        self.rider_user.roles.create(role="rider")
        self.rider_profile = RiderProfile.objects.create(user=self.rider_user)
        
        self.delivery = Delivery.objects.create(order=self.order, rider=self.rider_profile, status="out_for_delivery")
        
        self.client.force_authenticate(user=self.rider_user)

    def test_location_ping_security(self):
        # 1. Valid Ping
        response = self.client.post(f"/api/v1/delivery/location/ping/{self.order.id}/", {
            "latitude": 12.9716, "longitude": 77.5946
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 2. Invalid Bounds
        response = self.client.post(f"/api/v1/delivery/location/ping/{self.order.id}/", {
            "latitude": 100.00, "longitude": 200.00
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Unassigned Order Check
        other_order = Order.objects.create(
            user=self.user, warehouse=self.wh, status="created", total_amount=100, delivery_type="express"
        )
        response = self.client.post(f"/api/v1/delivery/location/ping/{other_order.id}/", {
            "latitude": 12.0, "longitude": 77.0
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)