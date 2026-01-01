from django.test import TestCase
from decimal import Decimal
from apps.pricing.services import SurgePricingService
from apps.pricing.models import SurgeRule
from apps.warehouse.models import Warehouse
from apps.orders.models import Order
from apps.riders.models import RiderProfile
from django.contrib.auth import get_user_model

User = get_user_model()

class SurgePricingTestCase(TestCase):
    def setUp(self):
        self.wh = Warehouse.objects.create(name="W", code="W", location="POINT(0 0)")
        SurgeRule.objects.create(warehouse=self.wh, max_multiplier=2.0, base_factor=0.5)
        
        self.user = User.objects.create_user(phone="+919999999999")
        self.order = Order.objects.create(
            user=self.user, warehouse=self.wh, status="created", 
            total_amount=100, delivery_type="express"
        )

    def test_no_riders_max_surge(self):
        # 0 riders, 1 order -> Max Surge
        factor = SurgePricingService.calculate(self.order)
        self.assertEqual(factor, Decimal("2.0"))

    def test_balanced_surge(self):
        # 1 Rider, 1 Active Order
        rider_user = User.objects.create_user(phone="+918888888888")
        RiderProfile.objects.create(
            user=rider_user, current_warehouse=self.wh, is_active=True, is_available=True
        )
        # Create an active order in system
        Order.objects.create(
            user=self.user, warehouse=self.wh, status="confirmed", 
            total_amount=100, delivery_type="express"
        )
        
        # Formula: 1 + (Active / Riders) * Factor => 1 + (1/1)*0.5 = 1.5
        factor = SurgePricingService.calculate(self.order)
        self.assertEqual(factor, Decimal("1.5"))