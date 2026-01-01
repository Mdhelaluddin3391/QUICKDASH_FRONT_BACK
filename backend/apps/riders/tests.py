from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.riders.models import RiderProfile, RiderEarning, RiderPayout
from apps.riders.services import RiderService
from apps.warehouse.models import Warehouse

User = get_user_model()

class RiderServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919999999999", password="pass")
        self.user.roles.create(role="rider")
        self.wh = Warehouse.objects.create(name="W", code="W", location="POINT(0 0)")
        self.profile = RiderService.create_rider_profile(self.user)

    def test_availability_toggle(self):
        RiderService.set_availability(self.profile, True)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_available)

    def test_assign_warehouse(self):
        RiderService.assign_warehouse(self.profile, self.wh)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_warehouse, self.wh)

    def test_payout_generation(self):
        # 1. Add Earnings
        RiderService.add_earning(self.profile, 50, "order:1")
        RiderService.add_earning(self.profile, 50, "order:2")
        
        # 2. Generate Payout
        payout = RiderService.generate_payout(self.profile)
        
        self.assertIsNotNone(payout)
        self.assertEqual(payout.amount, 100)
        self.assertEqual(payout.status, "processing")
        
        # 3. Verify Earnings are linked
        self.assertEqual(self.profile.earnings.filter(payout=payout).count(), 2)
        
        # 4. Ensure Idempotency / Empty check
        payout2 = RiderService.generate_payout(self.profile)
        self.assertIsNone(payout2)