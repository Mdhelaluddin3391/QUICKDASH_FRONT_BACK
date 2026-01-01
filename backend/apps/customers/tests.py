# apps/customers/tests.py
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from apps.customers.models import Customer, CustomerAddress, SupportTicket
from apps.customers.services import CustomerService

User = get_user_model()


class CustomerProfileAPIViewTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919999999999")
        self.client.force_authenticate(user=self.user)

    def test_get_customer_profile(self):
        url = reverse("customer_profile")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone"], self.user.phone)


class CustomerAddressViewsTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919999999998")
        self.customer = Customer.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        self.address = CustomerService.add_address(
            self.user,
            {
                "label": "Home",
                "address_line": "123 Street",
                "latitude": 12.9716,
                "longitude": 77.5946,
            },
        )

    def test_create_address(self):
        url = reverse("customer_address_create")
        data = {
            "label": "Work",
            "address_line": "456 Avenue",
            "latitude": 12.9717,
            "longitude": 77.5947,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CustomerAddress.objects.count(), 2)

    def test_list_addresses(self):
        url = reverse("customer_address_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_update_address(self):
        url = reverse(
            "customer_address_update", kwargs={"address_id": self.address.id}
        )
        data = {"label": "New Home"}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.address.refresh_from_db()
        self.assertEqual(self.address.label, "New Home")

    def test_set_default_address(self):
        url = reverse(
            "customer_address_set_default", kwargs={"address_id": self.address.id}
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.address.refresh_from_db()
        self.assertTrue(self.address.is_default)

    def test_delete_address(self):
        url = reverse("customer_address_delete", kwargs={"address_id": self.address.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.address.refresh_from_db()
        self.assertTrue(self.address.is_deleted)


class SupportTicketViewsTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919999999997")
        self.customer = Customer.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)
        self.ticket = SupportTicket.objects.create(
            customer=self.customer, subject="Test Ticket", body="This is a test ticket."
        )

    def test_create_ticket(self):
        url = reverse("support_ticket_create")
        data = {"subject": "New Ticket", "body": "This is a new ticket."}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(SupportTicket.objects.count(), 2)

    def test_list_tickets(self):
        url = reverse("support_ticket_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_ticket_detail(self):
        url = reverse("support_ticket_detail", kwargs={"id": self.ticket.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["subject"], self.ticket.subject)
