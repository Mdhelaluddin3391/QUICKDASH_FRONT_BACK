# apps/accounts/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import UserRole

User = get_user_model()

class AccountServiceTestCase(TestCase):
    def test_create_user_manager(self):
        user = User.objects.create_user(phone="+919999999999", password="password123")
        self.assertEqual(user.phone, "+919999999999")
        self.assertTrue(user.check_password("password123"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        admin = User.objects.create_superuser(phone="+919999999900", password="adminpass")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_phone_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(phone=None, password="pass")

class AuthAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(phone="+919876543210", password="testpass")
        UserRole.objects.create(user=self.user, role="customer")

    def test_customer_registration(self):
        payload = {"phone": "+919988776655"}
        response = self.client.post("/api/v1/auth/register/customer/", payload)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.filter(phone="+919988776655").exists())
        user = User.objects.get(phone="+919988776655")
        self.assertTrue(user.roles.filter(role="customer").exists())

    def test_me_endpoint_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone"], self.user.phone)

    def test_me_endpoint_unauthenticated(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)