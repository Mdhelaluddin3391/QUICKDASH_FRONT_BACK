# apps/payments/admin.py
from django.contrib import admin
from .models import Payment, Refund

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "amount",
        "status",
        "provider",
        "created_at",
    )
    list_filter = ("status", "provider", "created_at")
    search_fields = ("order__id", "provider_order_id", "provider_payment_id")
    readonly_fields = ("amount", "order", "created_at")

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("id", "payment", "amount", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("payment__provider_payment_id", "provider_refund_id")
    readonly_fields = ("amount", "payment", "created_at")