from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class PhoneOTP(models.Model):
    phone = models.CharField(max_length=15, db_index=True)
    otp = models.CharField(max_length=6)
    attempts = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        from django.conf import settings
        expiry = getattr(settings, 'OTP_EXPIRY_SECONDS', 300)
        return timezone.now() > self.created_at + timezone.timedelta(seconds=expiry)

class OTPAbuseLog(models.Model):
    phone = models.CharField(max_length=15, unique=True)
    failed_attempts = models.IntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)

    def is_blocked(self):
        return self.blocked_until and timezone.now() < self.blocked_until

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=20)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

# --- MANUAL PUSH NOTIFICATION ---
class ManualPushNotification(models.Model):
    TARGET_CHOICES = (
        ('all', 'All Users (with App/Web)'),
        ('selected', 'Selected Users Only'),
    )
    title = models.CharField(max_length=200, help_text="Notification ka title")
    message = models.TextField(help_text="Notification ka main message")
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    
    selected_users = models.ManyToManyField(
        User, 
        blank=True, 
        help_text="Agar 'Selected Users' chuna hai, toh yahan se users select karein."
    )
    
    sent = models.BooleanField(default=False, help_text="Status check ki push send ho chuka hai ya nahi.")
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title