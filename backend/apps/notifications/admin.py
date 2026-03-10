from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from .models import ManualPushNotification
from .services import NotificationService
# Import Export Magic for Master Admin
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin

from .models import PhoneOTP, Notification, OTPAbuseLog

User = get_user_model()

# ==========================================
# 1. CSV EXPORT RESOURCES
# ==========================================
class PhoneOTPResource(resources.ModelResource):
    class Meta:
        model = PhoneOTP
        fields = ('id', 'phone', 'is_verified', 'attempts', 'created_at')
        export_order = ('id', 'phone', 'is_verified', 'attempts', 'created_at')

class NotificationResource(resources.ModelResource):
    user_phone = fields.Field(column_name='User Phone', attribute='user', widget=widgets.ForeignKeyWidget(User, 'phone'))
    class Meta:
        model = Notification
        fields = ('id', 'user_phone', 'type', 'title', 'message', 'created_at')

class OTPAbuseLogResource(resources.ModelResource):
    class Meta:
        model = OTPAbuseLog
        fields = ('id', 'phone', 'failed_attempts', 'blocked_until', 'last_attempt')


# ==========================================
# 2. MASTER ADMIN VIEWS
# ==========================================
@admin.register(PhoneOTP)
class PhoneOTPAdmin(ImportExportModelAdmin):
    """UPGRADED: Track OTP Deliveries & Verifications globally"""
    resource_class = PhoneOTPResource
    
    list_display = (
        'id', 'phone', 'otp_masked', 'is_verified_badge', 
        'attempts', 'is_expired_badge', 'created_at_date'
    )
    list_display_links = ('id', 'phone')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('phone',)
    list_per_page = 50
    date_hierarchy = 'created_at'
    actions = ['mark_verified', 'reset_attempts']

    fieldsets = (
        ('OTP Information', {
            'fields': ('phone', 'otp', 'is_verified', 'attempts')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at',)

    def otp_masked(self, obj):
        return "●●●●●●" 
    otp_masked.short_description = "OTP"

    def is_verified_badge(self, obj):
        if obj.is_verified:
            return format_html('<span style="color: green; font-weight: bold;">✓ Verified</span>')
        return format_html('<span style="color: orange; font-weight: bold;">⏳ Pending</span>')
    is_verified_badge.short_description = "Status"

    def is_expired_badge(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red; font-weight: bold;">✗ Expired</span>')
        return format_html('<span style="color: green;">✓ Active</span>')
    is_expired_badge.short_description = "Expiry"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M:%S')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    @admin.action(description='✅ Mark selected OTPs as verified')
    def mark_verified(self, request, queryset):
        updated = queryset.filter(is_verified=False).update(is_verified=True)
        self.message_user(request, f"{updated} OTPs successfully marked as verified.")

    @admin.action(description='🔄 Reset attempts for selected OTPs')
    def reset_attempts(self, request, queryset):
        updated = queryset.update(attempts=0)
        self.message_user(request, f"Attempts reset to 0 for {updated} OTP records.")


@admin.register(Notification)
class NotificationAdmin(ImportExportModelAdmin):
    """UPGRADED: Global view for System Notifications"""
    resource_class = NotificationResource
    
    list_display = (
        'id', 'user_phone', 'type_badge', 'title', 
        'message_preview', 'created_at_date'
    )
    list_display_links = ('id', 'user_phone')
    list_filter = ('type', 'created_at')
    search_fields = ('user__phone', 'user__first_name', 'title', 'message')
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 50
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Recipient', {
            'fields': ('user',)
        }),
        ('Notification Details', {
            'fields': ('type', 'title', 'message')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at',)

    def user_phone(self, obj):
        if obj.user:
            return format_html('<b>{}</b>', obj.user.phone)
        return "N/A"
    user_phone.short_description = "User"
    user_phone.admin_order_field = 'user__phone'

    def type_badge(self, obj):
        colors = {'sms': '#007bff', 'push': '#28a745'}
        color = colors.get(obj.type, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; font-weight:bold;">{}</span>', color, obj.get_type_display().upper())
    type_badge.short_description = "Type"

    def message_preview(self, obj):
        return obj.message[:60] + "..." if len(obj.message) > 60 else obj.message
    message_preview.short_description = "Message"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Sent On"
    created_at_date.admin_order_field = 'created_at'


@admin.register(OTPAbuseLog)
class OTPAbuseLogAdmin(ImportExportModelAdmin):
    """UPGRADED: Monitor and Manage Spammers / System Abuse"""
    resource_class = OTPAbuseLogResource
    
    list_display = (
        'id', 'phone', 'failed_attempts', 'is_blocked_badge', 
        'blocked_until_date', 'last_attempt_date'
    )
    list_display_links = ('id', 'phone')
    list_filter = ('blocked_until', 'last_attempt')
    search_fields = ('phone',)
    list_per_page = 50
    actions = ['unblock_numbers', 'reset_attempts']

    fieldsets = (
        ('Abuse Information', {
            'fields': ('phone', 'failed_attempts', 'blocked_until')
        }),
        ('Timestamps', {
            'fields': ('last_attempt',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('last_attempt',)

    def is_blocked_badge(self, obj):
        if obj.is_blocked():
            return format_html('<span style="color: white; background-color: #dc3545; padding: 3px 8px; border-radius: 4px; font-weight: bold;">🚫 BLOCKED</span>')
        return format_html('<span style="color: green; font-weight:bold;">✓ Safe</span>')
    is_blocked_badge.short_description = "Status"
    
    def blocked_until_date(self, obj):
        if obj.blocked_until:
            return localtime(obj.blocked_until).strftime('%d %b %Y, %H:%M:%S')
        return "-"
    blocked_until_date.short_description = "Blocked Until"

    def last_attempt_date(self, obj):
        if hasattr(obj, 'last_attempt') and obj.last_attempt:
            return localtime(obj.last_attempt).strftime('%d %b %Y, %H:%M:%S')
        return "N/A"
    last_attempt_date.short_description = "Last Attempt"
    last_attempt_date.admin_order_field = 'last_attempt'

    @admin.action(description='🔓 Unblock selected phone numbers')
    def unblock_numbers(self, request, queryset):
        updated = queryset.update(blocked_until=None, failed_attempts=0)
        self.message_user(request, f"Successfully unblocked {updated} phone numbers.")

    @admin.action(description='🔄 Reset failed attempts to 0')
    def reset_attempts(self, request, queryset):
        updated = queryset.update(failed_attempts=0)
        self.message_user(request, f"Failed attempts reset for {updated} numbers.")


# apps/notifications/admin.py
from django.contrib import admin
from .models import ManualPushNotification
from .services import NotificationService

@admin.register(ManualPushNotification)
class ManualPushNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'created_at', 'is_sent')
    list_filter = ('is_sent', 'topic', 'created_at')
    search_fields = ('title', 'message')
    readonly_fields = ('is_sent', 'created_at')

    def save_model(self, request, obj, form, change):
        # Naya object create ho raha hai ya purana edit ho raha hai?
        is_new = obj.pk is None 
        super().save_model(request, obj, form, change)
        
        # Agar ye naya message hai aur abhi tak bheja nahi gaya hai:
        if is_new and not obj.is_sent:
            # Extra data (agar admin me khali chhod diya toh default type dega)
            extra_data = obj.extra_data or {"type": "manual_push"}
            
            # Aapke existing Service ko call karke sabko Notification bhej rahe hain
            NotificationService.send_global_push(
                topic=obj.topic,
                title=obj.title,
                message=obj.message,
                extra_data=extra_data
            )
            
            # Update kar do ki message ja chuka hai taaki dubara send na ho
            obj.is_sent = True
            obj.save(update_fields=['is_sent'])