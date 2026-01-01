# apps/locations/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class GeoLocation(models.Model):
    """
    Generic location model for auditing or auxiliary location data.
    (Note: Customer addresses are stored in customers.CustomerAddress)
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="locations",
        null=True,
        blank=True,
    )

    label = models.CharField(max_length=50, blank=True)  # e.g. "Pinned Location"
    address_text = models.TextField()

    # Precision: 6 decimal places (~11cm)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.label} ({self.latitude}, {self.longitude})"