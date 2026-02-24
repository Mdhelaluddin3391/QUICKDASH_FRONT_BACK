from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from .models import Payment, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order_info',
        'customer_phone',
        'amount_display',
        'status_badge',
        'provider',
        'created_at_date'
    )
    list_filter = (
        'status',
        'provider',
        'created_at',
        'updated_at'
    )
    search_fields = (
        'id',
        'order__id',
        'order__user__phone',
        'provider_order_id',
        'provider_payment_id'
    )
    list_select_related = ('order', 'order__user')
    raw_id_fields = ('order',)
    list_per_page = 25
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
        return f"Order #{obj.order.id}"
    order_info.short_description = "Order"
    order_info.admin_order_field = 'order__id'

    def customer_phone(self, obj):
        return obj.order.user.phone
    customer_phone.short_description = "Customer"
    customer_phone.admin_order_field = 'order__user__phone'

    def amount_display(self, obj):
        return f"₹{obj.amount:.2f}"
    amount_display.short_description = "Amount"
    amount_display.admin_order_field = 'amount'

    def status_badge(self, obj):
        colors = {
            'created': '#ffc107',
            'paid': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # Admin Actions
    @admin.action(description='Mark selected payments as paid')
    def mark_as_paid(self, request, queryset):
        updated = queryset.filter(status='created').update(status='paid')
        self.message_user(request, f"{updated} payments marked as paid.")

    @admin.action(description='Mark selected payments as failed')
    def mark_as_failed(self, request, queryset):
        updated = queryset.filter(status='created').update(status='failed')
        self.message_user(request, f"{updated} payments marked as failed.")

    @admin.action(description='Retry failed payments (mark as created)')
    def retry_failed_payments(self, request, queryset):
        updated = queryset.filter(status='failed').update(status='created')
        self.message_user(request, f"{updated} failed payments marked for retry.")


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'payment_info',
        'customer_phone',
        'amount_display',
        'status_badge',
        'created_at_date'
    )
    list_filter = (
        'status',
        'created_at'
    )
    search_fields = (
        'id',
        'payment__id',
        'payment__order__user__phone',
        'provider_refund_id'
    )
    list_select_related = ('payment', 'payment__order', 'payment__order__user')
    raw_id_fields = ('payment',)
    list_per_page = 25
    actions = ['process_refunds', 'mark_as_processed', 'mark_as_failed']

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
        return f"Payment #{obj.payment.id}"
    payment_info.short_description = "Payment"
    payment_info.admin_order_field = 'payment__id'

    def customer_phone(self, obj):
        return obj.payment.order.user.phone
    customer_phone.short_description = "Customer"
    customer_phone.admin_order_field = 'payment__order__user__phone'

    def amount_display(self, obj):
        return f"₹{obj.amount:.2f}"
    amount_display.short_description = "Amount"
    amount_display.admin_order_field = 'amount'

    def status_badge(self, obj):
        colors = {
            'initiated': '#ffc107',
            'processed': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # Admin Actions
    @admin.action(description='Process selected refunds')
    def process_refunds(self, request, queryset):
        updated = queryset.filter(status='initiated').update(status='processed')
        self.message_user(request, f"{updated} refunds marked as processed.")

    @admin.action(description='Mark selected refunds as processed')
    def mark_as_processed(self, request, queryset):
        updated = queryset.filter(status='initiated').update(status='processed')
        self.message_user(request, f"{updated} refunds marked as processed.")

    @admin.action(description='Mark selected refunds as failed')
    def mark_as_failed(self, request, queryset):
        updated = queryset.filter(status__in=['initiated', 'processed']).update(status='failed')
        self.message_user(request, f"{updated} refunds marked as failed.")