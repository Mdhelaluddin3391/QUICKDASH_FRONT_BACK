from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from apps.riders.models import Rider
from .models import Delivery
from apps.orders.models import Order
from apps.riders.models import Rider


class DeliveryResource(resources.ModelResource):
    # Linking order by id
    order = fields.Field(
        column_name='order_id',
        attribute='order',
        widget=ForeignKeyWidget(Order, 'id')
    )
    
    # Linking rider by user's phone number
    rider = fields.Field(
        column_name='rider_phone',
        attribute='rider',
        widget=ForeignKeyWidget(Rider, 'user__phone')
    )

    class Meta:
        model = Delivery
        fields = (
            'id', 
            'order', 
            'rider', 
            'status', 
            'job_status', 
            'otp', 
            'proof_image', 
            'dispatch_location', 
            'created_at', 
            'updated_at'
        )
        export_order = fields


@admin.register(Delivery)
class DeliveryAdmin(ImportExportModelAdmin):
    resource_class = DeliveryResource
    
    list_display = (
        'order_id_display',
        'rider_info',
        'status_badge',
        'job_status_badge',
        'delivery_type',
        'created_at_date'
    )
    list_filter = (
        'status',
        'job_status',
        'created_at',
        'updated_at'
    )
    search_fields = (
        'order__id',
        'rider__user__phone',
        'rider__user__first_name',
        'dispatch_location'
    )
    list_select_related = ('order', 'rider', 'rider__user')
    raw_id_fields = ('order', 'rider')
    list_per_page = 25
    actions = [
        'assign_rider',
        'mark_picked_up',
        'mark_out_for_delivery',
        'mark_delivered',
        'mark_failed',
        'reset_to_searching'
    ]

    fieldsets = (
        ('Order & Rider', {
            'fields': ('order', 'rider', 'job_status')
        }),
        ('Delivery Details', {
            'fields': ('status', 'otp', 'proof_image', 'dispatch_location')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'otp')

    def order_id_display(self, obj):
        return f"#{obj.order.id}"
    order_id_display.short_description = "Order ID"
    order_id_display.admin_order_field = 'order__id'

    def rider_info(self, obj):
        if obj.rider:
            return f"{obj.rider.user.phone}"
        return "Unassigned"
    rider_info.short_description = "Rider"
    rider_info.admin_order_field = 'rider__user__phone'

    def status_badge(self, obj):
        colors = {
            'assigned': '#007bff',
            'picked_up': '#ffc107',
            'out_for_delivery': '#17a2b8',
            'delivered': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_status_display()
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
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_job_status_display()
        )
    job_status_badge.short_description = "Job Status"

    def delivery_type(self, obj):
        return obj.order.get_delivery_type_display()
    delivery_type.short_description = "Type"
    delivery_type.admin_order_field = 'order__delivery_type'

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %H:%M')
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    @admin.action(description='Assign rider (mark job as assigned)')
    def assign_rider(self, request, queryset):
        updated = queryset.filter(rider__isnull=False, job_status='searching').update(job_status='assigned')
        self.message_user(request, f"{updated} deliveries marked as assigned.")

    @admin.action(description='Mark selected deliveries as picked up')
    def mark_picked_up(self, request, queryset):
        updated = queryset.filter(status='assigned').update(status='picked_up')
        self.message_user(request, f"{updated} deliveries marked as picked up.")

    @admin.action(description='Mark selected deliveries as out for delivery')
    def mark_out_for_delivery(self, request, queryset):
        updated = queryset.filter(status__in=['assigned', 'picked_up']).update(status='out_for_delivery')
        self.message_user(request, f"{updated} deliveries marked as out for delivery.")

    @admin.action(description='Mark selected deliveries as delivered')
    def mark_delivered(self, request, queryset):
        updated = queryset.filter(status__in=['assigned', 'picked_up', 'out_for_delivery']).update(status='delivered')
        self.message_user(request, f"{updated} deliveries marked as delivered.")

    @admin.action(description='Mark selected deliveries as failed')
    def mark_failed(self, request, queryset):
        updated = queryset.exclude(status='delivered').update(status='failed')
        self.message_user(request, f"{updated} deliveries marked as failed.")

    @admin.action(description='Reset selected deliveries to searching')
    def reset_to_searching(self, request, queryset):
        updated = queryset.update(job_status='searching', rider=None)
        self.message_user(request, f"{updated} deliveries reset to searching.")