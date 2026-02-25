from django.db import models
from django.conf import settings
from django.utils import timezone

class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError("Audit logs are immutable (bulk update blocked)")

    def delete(self):
        raise RuntimeError("Audit logs are immutable (bulk delete blocked)")

class AuditLogManager(models.Manager):
    def get_queryset(self):
        return AuditLogQuerySet(self.model, using=self._db)

class AuditLog(models.Model):
    """
    Immutable system-level audit logs for security & compliance.
    """
    ACTION_CHOICES = (
        ("order_created", "Order Created"),
        ("order_cancelled", "Order Cancelled"),
        ("payment_success", "Payment Success"),
        ("payment_failed", "Payment Failed"),
        ("refund_initiated", "Refund Initiated"),
        ("refund_completed", "Refund Completed"),
        ("delivery_completed", "Delivery Completed"),
        ("delivery_failed", "Delivery Failed"),
        ("manual_assignment", "Manual Assignment"),
        ("admin_inventory_update", "Admin Inventory Update"),
        ("gst_invoice_generated", "GST Invoice Generated"),
        ("refund_failed", "Refund Failed"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    action = models.CharField(max_length=50, choices=ACTION_CHOICES)

    reference_id = models.CharField(
        max_length=100,
        help_text="Order ID / Payment ID / Refund ID",
    )

    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(default=timezone.now)

    objects = AuditLogManager()
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["reference_id"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise RuntimeError("Audit logs are immutable (update blocked)")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit logs are immutable (delete blocked)")

    def __str__(self):
        return f"{self.action} | {self.reference_id}"