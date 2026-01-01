# apps/riders/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.warehouse.models import Warehouse

User = settings.AUTH_USER_MODEL

class RiderProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="rider_profile"
    )

    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=False)

    current_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="riders",
    )

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            # Critical Index for Auto-Assignment Service
            models.Index(
                fields=['current_warehouse', 'is_active', 'is_available'],
                name='rider_assign_idx'
            ),
        ]

    @property
    def is_kyc_verified(self):
        # MVP Rule: Must have verified License + RC
        required = {'license', 'rc'}
        verified_docs = set(
            self.documents.filter(status='verified').values_list('doc_type', flat=True)
        )
        return required.issubset(verified_docs)

    def __str__(self):
        return f"Rider {self.user.phone}"


class RiderDocument(models.Model):
    DOC_TYPE_CHOICES = (
        ("license", "Driving License"),
        ("pan", "PAN Card"),
        ("aadhar", "Aadhar Card"),
        ("rc", "Vehicle RC"),
    )
    
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    )

    rider = models.ForeignKey(RiderProfile, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    file_key = models.CharField(max_length=255, help_text="S3 Key")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_notes = models.TextField(blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("rider", "doc_type")


class RiderPayout(models.Model):
    """
    Aggregated Payout Record (Weekly/Daily Settlement).
    """
    STATUS_CHOICES = (
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    rider = models.ForeignKey(RiderProfile, on_delete=models.PROTECT, related_name="payouts")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="processing")
    
    transaction_ref = models.CharField(max_length=100, blank=True) # Bank Transaction ID
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout {self.id} - {self.amount}"


class RiderEarning(models.Model):
    """
    Granular earning log per order/bonus.
    """
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.CASCADE,
        related_name="earnings",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100) # e.g. "Order #123"
    
    payout = models.ForeignKey(
        RiderPayout, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="earnings"
    )
    
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['rider', '-created_at']),
        ]

    def __str__(self):
        return f"{self.rider} +{self.amount}"