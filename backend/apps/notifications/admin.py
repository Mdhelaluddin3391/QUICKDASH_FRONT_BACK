# apps/notifications/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from .models import PhoneOTP, Notification, OTPAbuseLog


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = (
        'phone',
        'otp_masked',
        'is_verified_badge',
        'attempts',
        'is_expired_badge',
        'created_at_date'
    )
    list_filter = (
        'is_verified',
        'created_at'
    )
    search_fields = ('phone',)
    list_per_page = 25
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
        return "●●●●●●"  # Mask the OTP for security
    otp_masked.short_description = "OTP"

    def is_verified_badge(self, obj):
        if obj.is_verified:
            return format_html('<span style="color: green; font-weight: bold;">✓ Verified</span>')
        else:
            return format_html('<span style="color: orange;">⏳ Pending</span>')
    is_verified_badge.short_description = "Status"

    def is_expired_badge(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red; font-weight: bold;">✗ Expired</span>')
        else:
            return format_html('<span style="color: green;">✓ Active</span>')
    is_expired_badge.short_description = "Expiry"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # Admin Actions
    @admin.action(description='Mark selected OTPs as verified')
    def mark_verified(self, request, queryset):
        updated = queryset.filter(is_verified=False).update(is_verified=True)
        self.message_user(request, f"{updated} OTPs marked as verified.")

    @admin.action(description='Reset attempts for selected OTPs')
    def reset_attempts(self, request, queryset):
        updated = queryset.update(attempts=0)
        self.message_user(request, f"Attempts reset for {updated} OTPs.")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'user_phone',
        'type_badge',
        'title',
        'message_preview',
        'created_at_date'
    )
    list_filter = (
        'type',
        'created_at'
    )
    search_fields = (
        'user__phone',
        'user__first_name',
        'title',
        'message'
    )
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 25

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
        return obj.user.phone
    user_phone.short_description = "User"
    user_phone.admin_order_field = 'user__phone'

    def type_badge(self, obj):
        colors = {
            'sms': '#007bff',
            'push': '#28a745',
        }
        color = colors.get(obj.type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_type_display()
        )
    type_badge.short_description = "Type"

    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_preview.short_description = "Message"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Sent"
    created_at_date.admin_order_field = 'created_at'


@admin.register(OTPAbuseLog)
class OTPAbuseLogAdmin(admin.ModelAdmin):
    list_display = (
        'phone',
        'failed_attempts',
        'is_blocked_badge',
        'blocked_until',
        'last_attempt_date'
    )
    list_filter = (
        'failed_attempts',
        'blocked_until',
        'last_attempt'
    )
    search_fields = ('phone',)
    list_per_page = 25
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
            return format_html('<span style="color: red; font-weight: bold;">🚫 BLOCKED</span>')
        else:
            return format_html('<span style="color: green;">✓ Active</span>')
    is_blocked_badge.short_description = "Status"

    def last_attempt_date(self, obj):
        if hasattr(obj, 'last_attempt') and obj.last_attempt:
            return localtime(obj.last_attempt).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    last_attempt_date.short_description = "Last Attempt"
    last_attempt_date.admin_order_field = 'last_attempt'

    # Admin Actions
    @admin.action(description='Unblock selected phone numbers')
    def unblock_numbers(self, request, queryset):
        updated = queryset.update(blocked_until=None, failed_attempts=0)
        self.message_user(request, f"{updated} phone numbers unblocked.")

    @admin.action(description='Reset failed attempts for selected numbers')
    def reset_attempts(self, request, queryset):
        updated = queryset.update(failed_attempts=0)
        self.message_user(request, f"Failed attempts reset for {updated} numbers.")