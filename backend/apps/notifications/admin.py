from django.contrib import admin
from django.db import models
from django.contrib.auth import get_user_model

from .models import PhoneOTP, OTPAbuseLog, Notification, ManualPushNotification
from .services import NotificationService

User = get_user_model()

@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ['phone', 'otp', 'is_verified', 'created_at']

@admin.register(OTPAbuseLog)
class OTPAbuseLogAdmin(admin.ModelAdmin):
    list_display = ['phone', 'failed_attempts', 'blocked_until']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'type', 'is_read', 'created_at']

# --- MANUAL ADMIN PUSH ---
@admin.register(ManualPushNotification)
class ManualPushNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_audience', 'sent', 'created_at']
    list_filter = ['sent', 'target_audience']
    filter_horizontal = ['selected_users'] 
    readonly_fields = ['sent']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "selected_users":
            kwargs["queryset"] = User.objects.filter(
                models.Q(devices__isnull=False) | models.Q(fcm_token__isnull=False)
            ).distinct()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        
        obj = form.instance
        if not obj.sent:
            # 🔥 NAYA LOGIC: Topic ki jagah seedha users ko fetch karenge
            if obj.target_audience == 'all':
                users_to_send = User.objects.filter(
                    models.Q(devices__isnull=False) | models.Q(fcm_token__isnull=False)
                ).distinct()
            else:
                users_to_send = obj.selected_users.all()

            # Sabhi valid users ko loop karke notification bhej do
            for user in users_to_send:
                NotificationService.send_push(
                    user=user,
                    title=obj.title,
                    message=obj.message,
                    extra_data={"type": "admin_announcement"}
                )

            obj.sent = True
            obj.save(update_fields=['sent'])