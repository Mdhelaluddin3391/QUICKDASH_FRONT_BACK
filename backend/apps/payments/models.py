# apps/payments/models.py
from django.db import models
from django.utils import timezone
from apps.orders.models import Order

class Payment(models.Model):
    STATUS_CHOICES = (
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    )

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="payment",
    )

    provider = models.CharField(max_length=50, default="razorpay")
    provider_order_id = models.CharField(max_length=100, blank=True, db_index=True)
    provider_payment_id = models.CharField(max_length=100, blank=True)

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.id} ({self.status})"


class Refund(models.Model):
    STATUS_CHOICES = (
        ("initiated", "Initiated"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    )

    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="refund",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    provider_refund_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="initiated")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Refund {self.id} ({self.status})"