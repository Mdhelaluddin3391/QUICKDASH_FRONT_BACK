from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

from .models import Payment, Refund
from apps.orders.models import Order

class PaymentResource(resources.ModelResource):
    order = fields.Field(column_name='order_id', attribute='order', widget=ForeignKeyWidget(Order, 'id'))
    class Meta:
        model = Payment
        import_id_fields = ('id',)
        fields = ('id', 'order', 'provider', 'provider_order_id', 'provider_payment_id', 'amount', 'status', 'created_at', 'updated_at')

class RefundResource(resources.ModelResource):
    payment = fields.Field(column_name='payment_id', attribute='payment', widget=ForeignKeyWidget(Payment, 'id'))
    class Meta:
        model = Refund
        import_id_fields = ('id',) 
        fields = ('id', 'payment', 'provider_refund_id', 'amount', 'status', 'created_at')

# ==========================================
# ENTERPRISE PAYMENT ADMINS (STRICT ISOLATION)
# ==========================================

@admin.register(Payment)
class PaymentAdmin(ImportExportModelAdmin):
    resource_class = PaymentResource
    list_display = ('id', 'order_info', 'customer_phone', 'amount_display', 'status_badge', 'provider', 'created_at_date')
    list_filter = ('status', 'provider', 'created_at')
    search_fields = ('id', 'order__id', 'order__user__phone', 'provider_order_id', 'provider_payment_id')
    list_select_related = ('order', 'order__user')
    raw_id_fields = ('order',)
    list_per_page = 25
    actions = ['mark_as_paid', 'mark_as_failed', 'retry_failed_payments']

    fieldsets = (
        ('Payment Information', {'fields': ('order', 'provider', 'amount', 'status')}),
        ('Provider Details', {'fields': ('provider_order_id', 'provider_payment_id'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(order__fulfillment_warehouse_id=wh_id)
        return qs.none()

    def order_info(self, obj): return f"Order #{obj.order.id}"
    order_info.short_description = "Order"

    def customer_phone(self, obj): return obj.order.user.phone
    customer_phone.short_description = "Customer"

    def amount_display(self, obj): return f"₹{obj.amount:.2f}"
    amount_display.short_description = "Amount"

    def status_badge(self, obj):
        colors = {'created': '#ffc107', 'paid': '#28a745', 'failed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"


@admin.register(Refund)
class RefundAdmin(ImportExportModelAdmin):
    resource_class = RefundResource
    list_display = ('id', 'payment_info', 'customer_phone', 'amount_display', 'status_badge', 'created_at_date')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'payment__id', 'payment__order__user__phone', 'provider_refund_id')
    list_select_related = ('payment', 'payment__order', 'payment__order__user')
    raw_id_fields = ('payment',)
    list_per_page = 25

    fieldsets = (
        ('Refund Information', {'fields': ('payment', 'amount', 'status')}),
        ('Provider Details', {'fields': ('provider_refund_id',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(payment__order__fulfillment_warehouse_id=wh_id)
        return qs.none()

    def payment_info(self, obj): return f"Payment #{obj.payment.id}"
    payment_info.short_description = "Payment"

    def customer_phone(self, obj): return obj.payment.order.user.phone
    customer_phone.short_description = "Customer"

    def amount_display(self, obj): return f"₹{obj.amount:.2f}"
    amount_display.short_description = "Amount"

    def status_badge(self, obj):
        colors = {'initiated': '#ffc107', 'processed': '#28a745', 'failed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"