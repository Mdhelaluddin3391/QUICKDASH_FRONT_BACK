from django.db import models
from django.utils import timezone
from apps.warehouse.models import Warehouse

class SurgeRule(models.Model):
    """
    Configuration for Surge Pricing per Warehouse.
    """
    warehouse = models.OneToOneField(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="surge_rule",
    )

    max_multiplier = models.FloatField(default=2.0)
    base_factor = models.FloatField(default=0.1)

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"SurgeRule ({self.warehouse.code})"