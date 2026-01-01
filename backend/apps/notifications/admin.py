# apps/notifications/admin.py
from django.contrib import admin
from .models import PhoneOTP, Notification, OTPAbuseLog

@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ("phone", "otp", "is_verified", "attempts", "created_at")
    search_fields = ("phone",)
    list_filter = ("is_verified", "created_at")
    readonly_fields = ("created_at",)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "title", "created_at")
    search_fields = ("user__phone", "title")
    list_filter = ("type", "created_at")

@admin.register(OTPAbuseLog)
class OTPAbuseLogAdmin(admin.ModelAdmin):
    list_display = ("phone", "failed_attempts", "blocked_until", "last_attempt")
    search_fields = ("phone",)