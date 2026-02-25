from django.db import models
from django.utils import timezone
from django.db.models import Q
from apps.orders.models import Order
from apps.riders.models import RiderProfile

class Delivery(models.Model):
    STATUS_CHOICES = (
        ("assigned", "Assigned"),
        ("picked_up", "Picked Up"),
        ("out_for_delivery", "Out For Delivery"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
    )

    JOB_STATUS_CHOICES = (
        ("searching", "Searching"),
        ("assigned", "Assigned"),
        ("manual_intervention", "Manual Intervention"),
    )

    job_status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES, default="searching")

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="delivery",
    )

    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.PROTECT,
        related_name="deliveries",
        null=True, 
        blank=True
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="assigned")
    otp = models.CharField(max_length=6)

    proof_image = models.CharField(max_length=255, blank=True, null=True)
    
    dispatch_location = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=['rider', 'status'], 
                name='active_rider_delivery_idx',
                condition=Q(status__in=['assigned', 'picked_up', 'out_for_delivery'])
            ),
            models.Index(fields=['rider', '-created_at']),
        ]

    def __str__(self):
        return f"Delivery {self.order.id} - {self.status}"