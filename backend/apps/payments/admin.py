from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

# Import Export Magic for Master Admin
from import_export import resources, fields, widgets
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

from .models import Payment, Refund
from apps.orders.models import Order
from django.contrib.auth import get_user_model

User = get_user_model()

# ==========================================
# 1. CSV EXPORT RESOURCES
# ==========================================
class PaymentResource(resources.ModelResource):
    order_id = fields.Field(column_name='Order ID', attribute='order', widget=ForeignKeyWidget(Order, 'id'))
    customer_phone = fields.Field(column_name='Customer Phone', attribute='order__user', widget=ForeignKeyWidget(User, 'phone'))
    
    class Meta:
        model = Payment
        import_id_fields = ('id',)
        fields = ('id', 'order_id', 'customer_phone', 'provider', 'provider_order_id', 'provider_payment_id', 'amount', 'status', 'created_at', 'updated_at')
        export_order = ('id', 'order_id', 'customer_phone', 'amount', 'status', 'provider', 'created_at')

class RefundResource(resources.ModelResource):
    payment_id = fields.Field(column_name='Payment ID', attribute='payment', widget=ForeignKeyWidget(Payment, 'id'))
    order_id = fields.Field(column_name='Order ID', attribute='payment__order', widget=ForeignKeyWidget(Order, 'id'))
    
    class Meta:
        model = Refund
        import_id_fields = ('id',) 
        fields = ('id', 'payment_id', 'order_id', 'provider_refund_id', 'amount', 'status', 'created_at')


# ==========================================
# 2. MASTER ADMIN VIEWS (GLOBAL ACCESS)
# ==========================================

@admin.register(Payment)
class PaymentAdmin(ImportExportModelAdmin):
    """UPGRADED: Global View for All Payments. No Isolation."""
    resource_class = PaymentResource
    
    list_display = (
        'id', 'order_info', 'customer_phone', 'amount_display', 
        'status_badge', 'provider', 'created_at_date'
    )
    list_display_links = ('id', 'order_info')
    
    # Global Filters
    list_filter = ('status', 'provider', 'order__fulfillment_warehouse', 'created_at')
    search_fields = ('id', 'order__id', 'order__user__phone', 'provider_order_id', 'provider_payment_id')
    list_select_related = ('order', 'order__user', 'order__fulfillment_warehouse')
    raw_id_fields = ('order',)
    list_per_page = 50
    date_hierarchy = 'created_at'

    # Fixed Bulk Actions
    actions = ['mark_as_paid', 'mark_as_failed', 'retry_failed_payments']

    fieldsets = (
        ('Payment Information', {
            'fields': ('order', 'provider', 'amount', 'status')
        }),
        ('Provider Details', {
            'fields': ('provider_order_id', 'provider_payment_id'), 
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'), 
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')

    def order_info(self, obj): 
        return f"#{obj.order.id}"
    order_info.short_description = "Order ID"
    order_info.admin_order_field = 'order__id'

    def customer_phone(self, obj): 
        if obj.order and obj.order.user:
            return format_html('<b>{}</b>', obj.order.user.phone)
        return "N/A"
    customer_phone.short_description = "Customer"
    customer_phone.admin_order_field = 'order__user__phone'

    def amount_display(self, obj): 
        return format_html('<span style="color: green; font-weight: bold;">₹{:.2f}</span>', obj.amount)
    amount_display.short_description = "Amount"
    amount_display.admin_order_field = 'amount'

    def status_badge(self, obj):
        colors = {'created': '#ffc107', 'paid': '#28a745', 'failed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">{}</span>', color, obj.get_status_display().upper())
    status_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: 
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Initiated On"
    created_at_date.admin_order_field = 'created_at'

    # ==========================================
    # WORKING BULK ACTIONS
    # ==========================================
    @admin.action(description="✅ Mark selected payments as Paid")
    def mark_as_paid(self, request, queryset):
        updated = queryset.update(status='paid')
        self.message_user(request, f"{updated} payments successfully marked as Paid.")

    @admin.action(description="❌ Mark selected payments as Failed")
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f"{updated} payments marked as Failed.")

    @admin.action(description="🔄 Retry failed payments (Reset to Created)")
    def retry_failed_payments(self, request, queryset):
        updated = queryset.filter(status='failed').update(status='created')
        self.message_user(request, f"{updated} failed payments reset to Created status.")


@admin.register(Refund)
class RefundAdmin(ImportExportModelAdmin):
    """UPGRADED: Global View for All Refunds"""
    resource_class = RefundResource
    
    list_display = (
        'id', 'payment_info', 'customer_phone', 'amount_display', 
        'status_badge', 'created_at_date'
    )
    list_display_links = ('id', 'payment_info')
    
    list_filter = ('status', 'payment__order__fulfillment_warehouse', 'created_at')
    search_fields = ('id', 'payment__id', 'payment__order__user__phone', 'provider_refund_id')
    list_select_related = ('payment', 'payment__order', 'payment__order__user')
    raw_id_fields = ('payment',)
    list_per_page = 50
    date_hierarchy = 'created_at'

    # Brand new bulk actions for Refunds
    actions = ['mark_processed', 'mark_failed']

    fieldsets = (
        ('Refund Information', {
            'fields': ('payment', 'amount', 'status')
        }),
        ('Provider Details', {
            'fields': ('provider_refund_id',), 
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',), 
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at',)

    def payment_info(self, obj): 
        return f"Pay #{obj.payment.id}"
    payment_info.short_description = "Payment ID"

    def customer_phone(self, obj): 
        if obj.payment and obj.payment.order and obj.payment.order.user:
            return format_html('<b>{}</b>', obj.payment.order.user.phone)
        return "N/A"
    customer_phone.short_description = "Customer"
    customer_phone.admin_order_field = 'payment__order__user__phone'

    def amount_display(self, obj): 
        return format_html('<span style="color: #dc3545; font-weight: bold;">₹{:.2f}</span>', obj.amount)
    amount_display.short_description = "Refund Amount"
    amount_display.admin_order_field = 'amount'

    def status_badge(self, obj):
        colors = {'initiated': '#ffc107', 'processed': '#28a745', 'failed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">{}</span>', color, obj.get_status_display().upper())
    status_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: 
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # ==========================================
    # WORKING BULK ACTIONS FOR REFUNDS
    # ==========================================
    @admin.action(description="✅ Mark selected refunds as Processed")
    def mark_processed(self, request, queryset):
        updated = queryset.update(status='processed')
        self.message_user(request, f"{updated} refunds successfully marked as Processed.")

    @admin.action(description="❌ Mark selected refunds as Failed")
    def mark_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f"{updated} refunds marked as Failed.")