from django.test import TestCase
from django.core.cache import cache
from unittest.mock import patch
from rest_framework.test import APIClient
from rest_framework import status

from apps.notifications.services import OTPService, OTPAbuseService
from apps.notifications.models import PhoneOTP, OTPAbuseLog
from apps.utils.exceptions import BusinessLogicException

class OTPServiceTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.phone = "+919999999999"

    @patch("apps.notifications.services.requests.post")
    def test_send_otp_success(self, mock_post):
        mock_post.return_value.status_code = 200
        
        OTPService.create_and_send(self.phone)
        
        self.assertTrue(PhoneOTP.objects.filter(phone=self.phone).exists())
        # Ensure cooldown is set
        self.assertTrue(cache.get(f"otp_cooldown:{self.phone}"))

    def test_verify_otp_success(self):
        OTPService.create_and_send(self.phone) # Generates DB entry
        otp_obj = PhoneOTP.objects.filter(phone=self.phone).first()
        
        result = OTPService.verify(self.phone, otp_obj.otp)
        self.assertTrue(result)
        
        otp_obj.refresh_from_db()
        self.assertTrue(otp_obj.is_verified)

    def test_verify_otp_failure_count(self):
        OTPService.create_and_send(self.phone)
        otp_obj = PhoneOTP.objects.filter(phone=self.phone).first()
        
        with self.assertRaises(BusinessLogicException):
            OTPService.verify(self.phone, "000000") # Wrong OTP

        otp_obj.refresh_from_db()
        self.assertEqual(otp_obj.attempts, 1)

    def test_abuse_blocking(self):
        # Simulate max failures
        for _ in range(OTPAbuseService.MAX_FAILS):
            OTPAbuseService.record_failure(self.phone)
            
        with self.assertRaises(BusinessLogicException) as context:
            OTPService.create_and_send(self.phone)
        
        self.assertIn("Blocked", str(context.exception))

class NotificationAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.phone = "+918888888888"
        cache.clear()

    @patch("apps.notifications.services.OTPService.send_sms")
    def test_send_otp_api(self, mock_send):
        response = self.client.post("/api/v1/notifications/send-otp/", {"phone": self.phone})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(PhoneOTP.objects.filter(phone=self.phone).exists())

    def test_verify_otp_api(self):
        PhoneOTP.objects.create(phone=self.phone, otp="123456")
        
        response = self.client.post("/api/v1/notifications/verify-otp/", {
            "phone": self.phone,
            "otp": "123456"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)