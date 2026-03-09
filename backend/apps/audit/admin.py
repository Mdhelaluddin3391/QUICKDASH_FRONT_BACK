from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

# Master Admin Export Feature
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin

from .models import AuditLog

User = get_user_model()

# ==========================================
# 1. CSV EXPORT RESOURCE
# ==========================================
class AuditLogResource(resources.ModelResource):
    user_phone = fields.Field(column_name='User Phone', attribute='user', widget=widgets.ForeignKeyWidget(User, 'phone'))
    
    class Meta:
        model = AuditLog
        fields = ('id', 'action', 'reference_id', 'user_phone', 'metadata', 'created_at')
        export_order = ('id', 'created_at', 'action', 'reference_id', 'user_phone', 'metadata')


# ==========================================
# 2. MASTER ADMIN VIEW (Secure & Read-Only)
# ==========================================
@admin.register(AuditLog)
class AuditLogAdmin(ImportExportModelAdmin):
    resource_class = AuditLogResource
    
    list_display = (
        'id',
        'action_badge',
        'reference_id',
        'user_info',
        'metadata_preview',
        'created_at_date'
    )
    list_display_links = ('id', 'reference_id')
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
    list_per_page = 50
    
    # Master Admin Advance Filters
    date_hierarchy = 'created_at'  # Top pe calendar filter aayega date wise dekhne ke liye
    ordering = ('-created_at',)

    fieldsets = (
        ('Audit Information', {
            'fields': ('action', 'reference_id', 'user')
        }),
        ('Additional Data', {
            'fields': ('metadata',),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
        }),
    )

    readonly_fields = ('action', 'reference_id', 'user', 'metadata', 'created_at')

    def action_badge(self, obj):
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
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display().upper()
        )
    action_badge.short_description = "Action"

    def user_info(self, obj):
        if obj.user:
            return format_html('<b>{}</b>', obj.user.phone)
        return format_html('<span style="color: red; font-weight:bold;">System Generated</span>')
    user_info.short_description = "Triggered By"
    user_info.admin_order_field = 'user__phone'

    def metadata_preview(self, obj):
        if obj.metadata:
            preview = str(obj.metadata)
            return preview[:60] + "..." if len(preview) > 60 else preview
        return format_html('<span style="color: gray;">N/A</span>')
    metadata_preview.short_description = "Metadata Summary"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M:%S')
        return "N/A"
    created_at_date.short_description = "Timestamp"
    created_at_date.admin_order_field = 'created_at'

    # ==========================================
    # ENTERPRISE SECURITY: Strictly Read-Only 
    # ==========================================
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions