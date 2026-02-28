from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from django.db.models import Q 

from .models import Order, OrderItem, OrderConfiguration, OrderItemFulfillment
from apps.catalog.models import Product
from apps.warehouse.models import Warehouse
from apps.delivery.tasks import retry_auto_assign_rider
from apps.customers.models import CustomerAddress 
from apps.inventory.models import InventoryItem

User = get_user_model()


class OrderResource(resources.ModelResource):
    user = fields.Field(
        column_name='user_phone',
        attribute='user',
        widget=ForeignKeyWidget(User, 'phone')
    )
    fulfillment_warehouse = fields.Field(
        column_name='fulfillment_warehouse_name',
        attribute='fulfillment_warehouse',
        widget=ForeignKeyWidget(Warehouse, 'name')
    )
    last_mile_warehouse = fields.Field(
        column_name='last_mile_warehouse_name',
        attribute='last_mile_warehouse',
        widget=ForeignKeyWidget(Warehouse, 'name')
    )

    class Meta:
        model = Order
        fields = (
            'id', 'user', 'fulfillment_warehouse', 'last_mile_warehouse', 
            'status', 'delivery_type', 'payment_method', 'total_amount', 
            'delivery_address_json', 'created_at', 'updated_at'
        )
        export_order = fields


class OrderItemResource(resources.ModelResource):
    order = fields.Field(
        column_name='order_id',
        attribute='order',
        widget=ForeignKeyWidget(Order, 'id')
    )

    class Meta:
        model = OrderItem
        # FIX: Added 'status' and 'cancel_reason' to match the updated models.py
        fields = ('id', 'order', 'sku', 'product_name', 'quantity', 'price', 'status', 'cancel_reason')
        export_order = fields


# NEW: Added Resource for OrderItemFulfillment for Full Backup
class OrderItemFulfillmentResource(resources.ModelResource):
    order_item = fields.Field(
        column_name='order_item_id',
        attribute='order_item',
        widget=ForeignKeyWidget(OrderItem, 'id')
    )
    inventory_batch = fields.Field(
        column_name='inventory_batch_id',
        attribute='inventory_batch',
        widget=ForeignKeyWidget(InventoryItem, 'id')
    )

    class Meta:
        model = OrderItemFulfillment
        fields = ('id', 'order_item', 'inventory_batch', 'quantity_allocated', 'vendor_payable_amount', 'created_at')
        export_order = fields


class OrderConfigurationResource(resources.ModelResource):
    class Meta:
        model = OrderConfiguration
        fields = ('id', 'delivery_fee', 'free_delivery_threshold')
        export_order = fields


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_image', 'sku', 'product_name', 'quantity', 'price', 'subtotal', 'fulfillment_details')
    can_delete = False
    fields = ('product_image', 'sku', 'product_name', 'quantity', 'price', 'subtotal', 'fulfillment_details', 'status', 'cancel_reason')
    show_change_link = False

    def product_image(self, obj):
        if obj.sku:
            product = Product.objects.filter(sku=obj.sku).first()
            if product and product.image:
                return format_html('<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px; box-shadow: 0 0 2px rgba(0,0,0,0.3);" />', product.image)
        return "No Image"
    product_image.short_description = "Image" 

    def subtotal(self, obj):
        if obj.price is None or obj.quantity is None: return "₹0.00"
        return f"₹{obj.price * obj.quantity:.2f}"
    subtotal.short_description = "Subtotal"

    def fulfillment_details(self, obj):
        if not obj.pk: return "-"
        fulfillments = obj.fulfillments.select_related('inventory_batch', 'inventory_batch__owner').all()
        if not fulfillments: return format_html('<span style="color:red;">Pending/No Batch</span>')
        
        details = []
        for f in fulfillments:
            owner = f.inventory_batch.owner.phone if f.inventory_batch.owner else "Company"
            details.append(f"<b>{f.quantity_allocated}x</b> (Batch {f.inventory_batch.id} - {owner})")
        return format_html("<br>".join(details))
    fulfillment_details.short_description = "Stock Source"


@admin.register(Order)
class OrderAdmin(ImportExportModelAdmin):
    resource_class = OrderResource
    list_display = (
        'id', 'customer_phone', 'fulfillment_warehouse', 'transit_route', 
        'status_badge', 'payment_method', 'total_amount_display', 
        'delivery_type', 'delivery_name', 'delivery_phone', 'Maps_link', 'created_at_date'
    )
    list_filter = ('status', 'fulfillment_warehouse', 'last_mile_warehouse', 'created_at', 'payment_method', 'delivery_type')
    search_fields = (
        'id', 'user__phone', 'user__first_name', 'user__last_name',
        'fulfillment_warehouse__name', 'fulfillment_warehouse__code', 'last_mile_warehouse__name'
    )
    list_select_related = ('user', 'fulfillment_warehouse', 'last_mile_warehouse')
    raw_id_fields = ('user', 'fulfillment_warehouse', 'last_mile_warehouse')
    inlines = [OrderItemInline]
    list_per_page = 25
    actions = [
        'mark_as_confirmed', 'mark_as_picking', 'mark_as_packed',
        'mark_as_out_for_delivery', 'mark_as_delivered', 'cancel_orders'
    ]

    fieldsets = (
        ('Order Information', {'fields': ('id', 'user', 'fulfillment_warehouse', 'last_mile_warehouse')}),
        ('Order Details', {'fields': ('status', 'delivery_type', 'payment_method', 'total_amount')}),
        ('Delivery Address Details', {'fields': ('delivery_name', 'delivery_phone', 'full_delivery_address', 'Maps_link')}),
        ('Raw Delivery JSON', {'fields': ('delivery_address_json',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    readonly_fields = ('id', 'created_at', 'updated_at', 'total_amount', 'delivery_name', 'delivery_phone', 'full_delivery_address', 'Maps_link')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'warehouse') and request.user.warehouse:
            user_wh = request.user.warehouse
            return qs.filter(Q(fulfillment_warehouse=user_wh) | Q(last_mile_warehouse=user_wh))
        return qs

    def transit_route(self, obj):
        if obj.fulfillment_warehouse and obj.last_mile_warehouse:
            if obj.fulfillment_warehouse != obj.last_mile_warehouse:
                return format_html('<span style="color: #17a2b8; font-weight: bold; font-size: 0.9em;">🚚 {} ➔ {}</span>', obj.fulfillment_warehouse.name, obj.last_mile_warehouse.name)
        return format_html('<span style="color: #28a745; font-weight: bold; font-size: 0.9em;">📍 Direct Delivery</span>')
    transit_route.short_description = "Transit Route"

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, OrderItem):
                if instance.pk:
                    old_instance = OrderItem.objects.get(pk=instance.pk)
                    old_status = getattr(old_instance, 'status', 'active')
                    new_status = getattr(instance, 'status', 'active')
                    
                    if old_status != 'cancelled' and new_status == 'cancelled':
                        item_total = instance.price * instance.quantity
                        order = instance.order
                        order.total_amount -= item_total
                        order.save(update_fields=['total_amount'])
                        
                        if order.payment_method == 'online':
                            try:
                                from apps.payments.models import Payment
                                from apps.payments.refund_services import RefundService
                                payment = Payment.objects.filter(order=order, status='paid').first()
                                if payment:
                                    RefundService.initiate_partial_refund(payment, item_total)
                                    self.message_user(request, f"Item '{instance.product_name}' cancelled. ₹{item_total} partial refund auto-initiated to bank!", level=messages.SUCCESS)
                                else:
                                    self.message_user(request, f"Item cancelled. Total deducted. But NO valid payment record found to auto-refund ₹{item_total}.", level=messages.WARNING)
                            except Exception as e:
                                self.message_user(request, f"Item Cancelled. Auto-Refund failed: {str(e)}", level=messages.ERROR)
                        else:
                            self.message_user(request, f"Item '{instance.product_name}' cancelled. COD Amount reduced by ₹{item_total}. New Total: ₹{order.total_amount}", level=messages.SUCCESS)
            instance.save()
        formset.save_m2m()

    def customer_phone(self, obj):
        return obj.user.phone
    customer_phone.short_description = "Customer Phone"
    customer_phone.admin_order_field = 'user__phone'

    def status_badge(self, obj):
        colors = {
            'created': '#6c757d', 'confirmed': '#007bff', 'picking': '#ffc107',
            'packed_at_hub': '#fd7e14', 'in_transit_to_local': '#6f42c1', 'received_at_local': '#20c997',
            'packed': '#28a745', 'out_for_delivery': '#17a2b8', 'delivered': '#28a745',
            'cancelled': '#dc3545', 'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; white-space: nowrap;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def total_amount_display(self, obj):
        return f"₹{obj.total_amount:.2f}"
    total_amount_display.short_description = "Total Amount"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"

    def delivery_name(self, obj):
        addr = obj.delivery_address_json or {}
        name = addr.get('receiver_name') or addr.get('name')
        if not name and obj.user: name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name or "N/A"
    delivery_name.short_description = "Delivery Name"

    def delivery_phone(self, obj):
        addr = obj.delivery_address_json or {}
        phone = addr.get('receiver_phone') or addr.get('phone')
        if not phone and obj.user: phone = getattr(obj.user, 'phone', None)
        return phone or "N/A"
    delivery_phone.short_description = "Delivery Phone"

    def full_delivery_address(self, obj):
        addr_json = obj.delivery_address_json or {}
        if not addr_json: return "No Address Details Found"
        details = []
        if addr_json.get('full_address'): details.append(f"<b>Full Address:</b> {addr_json.get('full_address')}")
        if addr_json.get('city'): details.append(f"<b>City:</b> {addr_json.get('city')}")
        return format_html("<br>".join(details)) if details else str(addr_json)
    full_delivery_address.short_description = "Address Details"

    def Maps_link(self, obj):
        addr = obj.delivery_address_json or {}
        lat, lng = addr.get('latitude') or addr.get('lat'), addr.get('longitude') or addr.get('lng')
        if lat is None or lng is None: return format_html('<span style="color:red;">Location Missing</span>')
        url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
        return format_html('<a style="background-color: #28a745; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block;" href="{}" target="_blank">📍 Directions</a>', url)
    Maps_link.short_description = "Map"


# FIX: Added ImportExportModelAdmin to allow backup of fulfillments too
@admin.register(OrderItemFulfillment)
class OrderItemFulfillmentAdmin(ImportExportModelAdmin):
    resource_class = OrderItemFulfillmentResource
    list_display = ('id', 'order_id_link', 'sku_link', 'batch_id', 'vendor_phone', 'quantity_allocated', 'vendor_payable_amount', 'created_at')
    list_filter = ('inventory_batch__owner', 'created_at')
    search_fields = ('order_item__order__id', 'inventory_batch__owner__phone', 'order_item__sku')
    list_select_related = ('order_item', 'order_item__order', 'inventory_batch', 'inventory_batch__owner')
    readonly_fields = ('order_item', 'inventory_batch', 'quantity_allocated', 'vendor_payable_amount')
    list_per_page = 50

    def order_id_link(self, obj):
        return f"Order #{obj.order_item.order.id}"
    order_id_link.short_description = "Order ID"

    def sku_link(self, obj):
        return obj.order_item.sku
    sku_link.short_description = "SKU"

    def batch_id(self, obj):
        return f"Batch #{obj.inventory_batch.id}"
    batch_id.short_description = "Batch ID"

    def vendor_phone(self, obj):
        if obj.inventory_batch.owner:
            return format_html('<span style="color: blue; font-weight: bold;">{}</span>', obj.inventory_batch.owner.phone)
        return format_html('<span style="color: green; font-weight: bold;">Company</span>')
    vendor_phone.short_description = "Vendor"


@admin.register(OrderConfiguration)
class OrderConfigurationAdmin(ImportExportModelAdmin):
    resource_class = OrderConfigurationResource
    list_display = ['delivery_fee', 'free_delivery_threshold']
    list_per_page = 25