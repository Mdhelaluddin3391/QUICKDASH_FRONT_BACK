# apps/audit/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'action_badge',
        'reference_id',
        'user_info',
        'metadata_preview',
        'created_at_date'
    )
    list_filter = (
        'action',
        'created_at'
    )
    search_fields = (
        'reference_id',
        'user__phone',
        'user__first_name',
        'metadata'
    )
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 25

    fieldsets = (
        ('Audit Information', {
            'fields': ('action', 'reference_id', 'user')
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('action', 'reference_id', 'user', 'metadata', 'created_at')

    def action_badge(self, obj):
        # Color coding based on action type
        action_colors = {
            'order_created': '#28a745',
            'order_cancelled': '#dc3545',
            'payment_success': '#007bff',
            'payment_failed': '#fd7e14',
            'refund_initiated': '#ffc107',
            'refund_completed': '#28a745',
            'delivery_completed': '#17a2b8',
            'delivery_failed': '#dc3545',
            'manual_assignment': '#6f42c1',
            'admin_inventory_update': '#20c997',
            'gst_invoice_generated': '#e83e8c',
            'refund_failed': '#dc3545',
        }
        color = action_colors.get(obj.action, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_badge.short_description = "Action"

    def user_info(self, obj):
        if obj.user:
            return obj.user.phone
        return "System"
    user_info.short_description = "User"
    user_info.admin_order_field = 'user__phone'

    def metadata_preview(self, obj):
        if obj.metadata:
            # Show a preview of the metadata
            preview = str(obj.metadata)
            return preview[:50] + "..." if len(preview) > 50 else preview
        return "N/A"
    metadata_preview.short_description = "Metadata"

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %H:%M:%S')
    created_at_date.short_description = "Timestamp"
    created_at_date.admin_order_field = 'created_at'

    # Completely Read-Only - No modifications allowed
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # Override get_actions to remove bulk actions
    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions