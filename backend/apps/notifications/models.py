from django.db import models
from django.utils import timezone
from django.conf import settings
from django.db.models import JSONField

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
    

class ManualPushNotification(models.Model):
    title = models.CharField(max_length=255, help_text="Example: 🏏 World Cup Mega Offer!")
    message = models.TextField(help_text="Example: Order your snacks now and enjoy the match.")
    topic = models.CharField(
        max_length=100, 
        default="global", 
        help_text="FCM Topic name. Default is 'global' (bhejne ke liye sabko). Aap 'promotions' bhi use kar sakte hain."
    )
    extra_data = models.JSONField(
        blank=True, 
        null=True, 
        help_text='Optional JSON data for app routing. Example: {"target_url": "/offers"}'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(
        default=False, 
        help_text="Admin me save hote hi ye True ho jayega. (Read Only)"
    )

    class Meta:
        verbose_name = "Manual Push Notification"
        verbose_name_plural = "Manual Push Notifications"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {'(Sent)' if self.is_sent else '(Pending)'}"