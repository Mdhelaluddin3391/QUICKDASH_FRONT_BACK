from django.contrib import admin
from django.db import models
from django.contrib.auth import get_user_model
import threading

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

# --- NAYA ADMIN PANEL LOGIC ---
@admin.register(ManualPushNotification)
class ManualPushNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'target_audience', 'sent', 'created_at']
    list_filter = ['sent', 'target_audience']
    filter_horizontal = ['selected_users'] # Isse user select karne ka box bahut sundar dikhega
    readonly_fields = ['sent']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "selected_users":
            # List mein sirf unhi users ko dikhayega jinke paas valid device token hai
            kwargs["queryset"] = User.objects.filter(
                models.Q(devices__isnull=False) | models.Q(fcm_token__isnull=False)
            ).distinct()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def save_related(self, request, form, formsets, change):
        """
        save_related isliye use kiya kyunki Django mein ManyToMany (users list) 
        hamesha normal save ke baad save hoti hai.
        """
        super().save_related(request, form, formsets, change)
        
        obj = form.instance
        if not obj.sent:
            
            # Background Thread function taaki admin website load hone mein time na lagaye
            def send_manual_push():
                if obj.target_audience == 'all':
                    # Sabhi valid users nikalo
                    users_to_send = User.objects.filter(
                        models.Q(devices__isnull=False) | models.Q(fcm_token__isnull=False)
                    ).distinct()
                else:
                    # Sirf chune hue users nikalo
                    users_to_send = obj.selected_users.all()

                for user in users_to_send:
                    try:
                        NotificationService.send_push(
                            user=user,
                            title=obj.title,
                            message=obj.message,
                            extra_data={"type": "admin_announcement"}
                        )
                    except Exception as e:
                        pass # Agar kisi ek par fail ho toh loop rukna nahi chahiye

                # Bhejne ke baad status 'sent = True' kardo
                obj.sent = True
                obj.save(update_fields=['sent'])

            # Thread ko start karo
            thread = threading.Thread(target=send_manual_push)
            thread.start()