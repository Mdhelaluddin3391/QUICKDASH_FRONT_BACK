# apps/orders/admin.py
from django.contrib import admin
from django.contrib import messages
from .models import Order, OrderItem, OrderAbuseLog, Cart, CartItem
from .services import OrderSimulationService

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("sku", "product_name", "price", "quantity")
    can_delete = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "warehouse",
        "status",
        "delivery_type",
        "total_amount",
        "created_at",
    )
    list_filter = ("status", "delivery_type", "warehouse", "created_at")
    search_fields = ("id", "user__phone")
    inlines = [OrderItemInline]
    
    readonly_fields = ("total_amount", "created_at", "updated_at", "delivery_address_json")
    actions = ["sim_advance_to_packed", "sim_advance_to_out_for_delivery", "sim_advance_to_delivered"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'warehouse')

    @admin.action(description="[SIM] Advance to Packed")
    def sim_advance_to_packed(self, request, queryset):
        for order in queryset:
            try:
                OrderSimulationService.advance_to_packed(order)
                self.message_user(request, f"Order {order.id} marked Packed", messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Failed Order {order.id}: {str(e)}", messages.ERROR)

    @admin.action(description="[SIM] Advance to Out for Delivery")
    def sim_advance_to_out_for_delivery(self, request, queryset):
        for order in queryset:
            try:
                OrderSimulationService.advance_to_out_for_delivery(order)
                self.message_user(request, f"Order {order.id} Out for Delivery", messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Failed Order {order.id}: {str(e)}", messages.ERROR)

    @admin.action(description="[SIM] Advance to Delivered")
    def sim_advance_to_delivered(self, request, queryset):
        for order in queryset:
            try:
                OrderSimulationService.advance_to_delivered(order)
                self.message_user(request, f"Order {order.id} Delivered", messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Failed Order {order.id}: {str(e)}", messages.ERROR)

@admin.register(OrderAbuseLog)
class OrderAbuseLogAdmin(admin.ModelAdmin):
    list_display = ("user", "cancelled_orders", "blocked_until", "updated_at")
    readonly_fields = ("user", "cancelled_orders")

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")