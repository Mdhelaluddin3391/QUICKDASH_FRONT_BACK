from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from .managers import UserManager

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model where phone number is the unique identifier.
    """
    phone = models.CharField(max_length=15, unique=True, db_index=True)
    email = models.EmailField(blank=True, null=True)
    
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []  

    def __str__(self):
        return self.phone


class UserRole(models.Model):
    """
    Role-Based Access Control (RBAC).
    A user can have multiple roles (e.g., Customer AND Rider).
    """
    ROLE_CHOICES = (
        ("customer", "Customer"),
        ("rider", "Rider"),
        ("employee", "Employee"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="roles")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ("user", "role")

    def __str__(self):
        return f"{self.user.phone} - {self.role}"


class Address(models.Model):
    """
    User Address model for storing user addresses.
    """
    ADDRESS_TYPE_CHOICES = (
        ("home", "Home"),
        ("work", "Work"),
        ("other", "Other"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES, default="home")
    street_address = models.TextField()
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.user.phone} - {self.address_type}: {self.street_address}"