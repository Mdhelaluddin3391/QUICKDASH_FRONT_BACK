from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime

# Import Export Magic for Master Admin
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin

from .models import Delivery
from apps.orders.models import Order
from apps.riders.models import RiderProfile

# ==========================================
# 1. CSV EXPORT RESOURCE
# ==========================================
class DeliveryResource(resources.ModelResource):
    order_id = fields.Field(column_name='Order ID', attribute='order', widget=widgets.ForeignKeyWidget(Order, 'id'))
    rider_phone = fields.Field(column_name='Rider Phone', attribute='rider', widget=widgets.ForeignKeyWidget(RiderProfile, 'user__phone'))
    
    class Meta:
        model = Delivery
        fields = ('id', 'order_id', 'rider_phone', 'status', 'job_status', 'otp', 'dispatch_location', 'created_at', 'updated_at')
        export_order = ('id', 'order_id', 'rider_phone', 'status', 'job_status', 'created_at')


# ==========================================
# 2. MASTER ADMIN VIEWS (GLOBAL ACCESS)
# ==========================================
@admin.register(Delivery)
class DeliveryAdmin(ImportExportModelAdmin):
    """UPGRADED: Global View for All Deliveries - No Restrictions!"""
    resource_class = DeliveryResource

    list_display = (
        'id',
        'order_id_display',
        'warehouse_info',
        'rider_info',
        'status_badge',
        'job_status_badge',
        'delivery_type',
        'created_at_date'
    )
    list_display_links = ('id', 'order_id_display')
    
    # Global Filters for Enterprise Management
    list_filter = (
        'status',
        'job_status',
        'order__fulfillment_warehouse', # Global Warehouse Filter
        'created_at',
    )
    search_fields = (
        'order__id',
        'rider__user__phone',
        'rider__user__first_name',
        'dispatch_location'
    )
    list_select_related = ('order', 'order__fulfillment_warehouse', 'rider', 'rider__user')
    raw_id_fields = ('order', 'rider')
    list_per_page = 50
    date_hierarchy = 'created_at'

    actions = [
        'assign_rider',
        'mark_picked_up',
        'mark_out_for_delivery',
        'mark_delivered',
        'mark_failed',
        'reset_to_searching'
    ]

    fieldsets = (
        ('Order & Rider Assignment', {
            'fields': ('order', 'rider', 'job_status')
        }),
        ('Delivery Execution Details', {
            'fields': ('status', 'otp', 'proof_image', 'dispatch_location')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'otp')

    def order_id_display(self, obj):
        return f"#{obj.order.id}" if obj.order else "N/A"
    order_id_display.short_description = "Order ID"
    order_id_display.admin_order_field = 'order__id'

    def warehouse_info(self, obj):
        if obj.order and obj.order.fulfillment_warehouse:
            return obj.order.fulfillment_warehouse.name
        return "-"
    warehouse_info.short_description = "Origin Hub"

    def rider_info(self, obj):
        if obj.rider and obj.rider.user:
            return format_html('<b style="color:blue;">{}</b>', obj.rider.user.phone)
        return format_html('<span style="color:red; font-weight:bold;">Unassigned</span>')
    rider_info.short_description = "Assigned Rider"
    rider_info.admin_order_field = 'rider__user__phone'

    def status_badge(self, obj):
        colors = {
            'assigned': '#007bff',
            'picked_up': '#fd7e14',
            'out_for_delivery': '#17a2b8',
            'delivered': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight:bold; white-space:nowrap;">{}</span>',
            color,
            obj.get_status_display().upper()
        )
    status_badge.short_description = "Delivery Status"

    def job_status_badge(self, obj):
        colors = {
            'searching': '#ffc107',
            'assigned': '#28a745',
            'manual_intervention': '#dc3545',
        }
        color = colors.get(obj.job_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; font-weight:bold;">{}</span>',
            color,
            obj.get_job_status_display()
        )
    job_status_badge.short_description = "Job Tracker"

    def delivery_type(self, obj):
        if obj.order:
            return obj.order.get_delivery_type_display()
        return "-"
    delivery_type.short_description = "Type"
    delivery_type.admin_order_field = 'order__delivery_type'

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # ==========================================
    # WORKING BULK ACTIONS
    # ==========================================
    @admin.action(description='🔄 Assign rider (mark job as assigned)')
    def assign_rider(self, request, queryset):
        updated = queryset.filter(rider__isnull=False, job_status='searching').update(job_status='assigned')
        self.message_user(request, f"{updated} deliveries successfully marked as assigned.")

    @admin.action(description='📦 Mark selected deliveries as picked up')
    def mark_picked_up(self, request, queryset):
        updated = queryset.filter(status='assigned').update(status='picked_up')
        self.message_user(request, f"{updated} deliveries marked as picked up.")

    @admin.action(description='🚚 Mark selected deliveries as out for delivery')
    def mark_out_for_delivery(self, request, queryset):
        updated = queryset.filter(status__in=['assigned', 'picked_up']).update(status='out_for_delivery')
        self.message_user(request, f"{updated} deliveries marked as out for delivery.")

    @admin.action(description='✅ Mark selected deliveries as delivered')
    def mark_delivered(self, request, queryset):
        updated = queryset.filter(status__in=['assigned', 'picked_up', 'out_for_delivery']).update(status='delivered')
        self.message_user(request, f"{updated} deliveries marked as delivered.")

    @admin.action(description='❌ Mark selected deliveries as failed')
    def mark_failed(self, request, queryset):
        from django.contrib import messages
        updated = queryset.exclude(status='delivered').update(status='failed')
        self.message_user(request, f"{updated} deliveries marked as failed.", level=messages.WARNING)

    @admin.action(description='⚠️ Reset selected deliveries to searching')
    def reset_to_searching(self, request, queryset):
        updated = queryset.update(job_status='searching', rider=None)
        self.message_user(request, f"{updated} deliveries reset to searching.")