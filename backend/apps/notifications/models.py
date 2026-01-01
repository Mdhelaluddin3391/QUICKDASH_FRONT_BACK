# apps/notifications/models.py
from django.db import models
from django.utils import timezone
from django.conf import settings

class PhoneOTP(models.Model):
    phone = models.CharField(max_length=15, db_index=True)
    otp = models.CharField(max_length=6)

    is_verified = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["phone", "created_at"]),
        ]

    def is_expired(self):
        # 5 minutes TTL
        return (timezone.now() - self.created_at).total_seconds() > 300


class Notification(models.Model):
    TYPE_CHOICES = (
        ("sms", "SMS"),
        ("push", "Push"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    title = models.CharField(max_length=100)
    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)


class OTPAbuseLog(models.Model):
    """
    Tracks failed attempts per phone number to prevent brute-force.
    """
    phone = models.CharField(max_length=15, db_index=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    last_attempt = models.DateTimeField(auto_now=True)

    def is_blocked(self):
        return self.blocked_until and self.blocked_until > timezone.now()