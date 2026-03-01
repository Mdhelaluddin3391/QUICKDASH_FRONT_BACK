from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name="customer_profile"
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Customer {self.user}"

class CustomerAddress(models.Model):
    LABEL_CHOICES = (
        ("HOME", "Home"),
        ("WORK", "Work"),
        ("OTHER", "Other"),
    )

    customer = models.ForeignKey(
        "customers.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="addresses"
    )

    latitude = models.DecimalField(max_digits=18, decimal_places=15)
    longitude = models.DecimalField(max_digits=18, decimal_places=15)
    
    house_no = models.CharField(max_length=50)
    floor_no = models.CharField(max_length=50, blank=True)
    apartment_name = models.CharField(max_length=100, blank=True)
    landmark = models.CharField(max_length=100, blank=True)
    
    city = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=20, blank=True)

    google_address_text = models.TextField()
    
    label = models.CharField(max_length=10, choices=LABEL_CHOICES, default="HOME")
    receiver_name = models.CharField(max_length=100, blank=True)
    receiver_phone = models.CharField(max_length=15, blank=True)
    
    is_default = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.label}: {self.house_no}, {self.google_address_text}"

class SupportTicket(models.Model):
    ISSUE_CHOICES = (
        ("missing_item", "Missing Item"),
        ("damaged", "Damaged Item"),
        ("late", "Late Delivery"),
        ("other", "Other"),
    )
    
    STATUS_CHOICES = (
        ("open", "Open"),
        ("resolved", "Resolved"),
        ("rejected", "Rejected"),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    order = models.ForeignKey(
        'orders.Order', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name="tickets"
    )
    
    issue_type = models.CharField(max_length=20, choices=ISSUE_CHOICES)
    description = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    admin_response = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket #{self.id} - {self.issue_type}"