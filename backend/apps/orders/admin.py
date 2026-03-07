from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime
from django.db.models import Q, F

# Master Admin Export Feature
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin

from .models import Order, OrderItem, OrderConfiguration, OrderItemFulfillment, OrderAbuseLog
from apps.catalog.models import Product
from apps.warehouse.models import Warehouse

User = get_user_model()

# ==========================================
# 1. CSV EXPORT RESOURCE
# ==========================================
class OrderResource(resources.ModelResource):
    customer_phone = fields.Field(column_name='Customer Phone', attribute='user', widget=widgets.ForeignKeyWidget(User, 'phone'))
    fulfillment_wh = fields.Field(column_name='Fulfillment WH', attribute='fulfillment_warehouse', widget=widgets.ForeignKeyWidget(Warehouse, 'name'))
    
    class Meta:
        model = Order
        fields = ('id', 'customer_phone', 'status', 'delivery_type', 'payment_method', 'total_amount', 'fulfillment_wh', 'created_at')
        export_order = ('id', 'created_at', 'customer_phone', 'status', 'total_amount', 'payment_method', 'delivery_type', 'fulfillment_wh')


# ==========================================
# 2. MASTER ADMIN VIEWS
# ==========================================

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_image', 'sku', 'product_name', 'quantity', 'price', 'subtotal', 'fulfillment_details')
    can_delete = False
    fields = ('product_image', 'sku', 'product_name', 'quantity', 'price', 'subtotal', 'fulfillment_details', 'status', 'cancel_reason')
    show_change_link = False

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('fulfillments__inventory_batch__owner')

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
        fulfillments = obj.fulfillments.all()
        if not fulfillments: return format_html('<span style="color:red;">Pending/No Batch</span>')
        
        details = []
        for f in fulfillments:
            # Safely check for owner and then phone
            owner_obj = getattr(f.inventory_batch, 'owner', None)
            owner = getattr(owner_obj, 'phone', 'Company') if owner_obj else "Company"
            details.append(f"<b>{f.quantity_allocated}x</b> (Batch {f.inventory_batch.id} - {owner})")
        return format_html("<br>".join(details))
    fulfillment_details.short_description = "Stock Source"


@admin.register(Order)
class OrderAdmin(ImportExportModelAdmin):
    """UPGRADED: Global Master Admin View, No Restrictions"""
    resource_class = OrderResource
    
    list_display = (
        'id', 'customer_phone', 'fulfillment_warehouse', 'transit_route', 
        'status_badge', 'payment_method', 'total_amount_display', 
        'delivery_type', 'Maps_link', 'created_at_date'
    )
    list_display_links = ('id', 'customer_phone')
    list_filter = ('status', 'created_at', 'payment_method', 'delivery_type', 'fulfillment_warehouse')
    search_fields = (
        'id', 'user__phone', 'user__first_name', 'user__last_name'
    )
    list_select_related = ('user', 'fulfillment_warehouse', 'last_mile_warehouse')
    raw_id_fields = ('user', 'fulfillment_warehouse', 'last_mile_warehouse')
    inlines = [OrderItemInline]
    list_per_page = 50
    
    # Master Admin Calendar Filter
    date_hierarchy = 'created_at'

    # Working Bulk Actions
    actions = [
        'mark_as_confirmed', 'mark_as_picking', 'mark_as_packed',
        'mark_as_out_for_delivery', 'mark_as_delivered', 'mark_as_cancelled'
    ]

    fieldsets = (
        ('Order Information', {'fields': ('id', 'user', 'fulfillment_warehouse', 'last_mile_warehouse')}),
        ('Order Details', {'fields': ('status', 'delivery_type', 'payment_method', 'total_amount')}),
        ('Delivery Address Details', {'fields': ('delivery_name', 'delivery_phone', 'full_delivery_address', 'Maps_link')}),
        ('Raw Delivery JSON', {'fields': ('delivery_address_json',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    readonly_fields = ('id', 'created_at', 'updated_at', 'total_amount', 'delivery_name', 'delivery_phone', 'full_delivery_address', 'Maps_link')

    def transit_route(self, obj):
        if obj.fulfillment_warehouse and obj.last_mile_warehouse:
            if obj.fulfillment_warehouse != obj.last_mile_warehouse:
                return format_html('<span style="color: #17a2b8; font-weight: bold; font-size: 0.9em;">🚚 {} ➔ {}</span>', obj.fulfillment_warehouse.name, obj.last_mile_warehouse.name)
        return format_html('<span style="color: #28a745; font-weight: bold; font-size: 0.9em;">📍 Direct Delivery</span>')
    transit_route.short_description = "Transit Route"

    def customer_phone(self, obj):
        return obj.user.phone if obj.user else "N/A"
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
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em; white-space: nowrap; font-weight: bold;">{}</span>', color, obj.get_status_display().upper())
    status_badge.short_description = "Status"

    def total_amount_display(self, obj):
        amount = obj.total_amount if obj.total_amount is not None else 0
        # Pehle amount ko 2 decimal places me format kar lein
        formatted_amount = f"{float(amount):.2f}"
        
        # Phir us formatted string ko format_html me pass karein (bina {:.2f} ke)
        return format_html('<span style="color: green; font-weight: bold;">₹{}</span>', formatted_amount)
    
    total_amount_display.short_description = "Amount"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Created At"

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
        details = []

        # 1. Customer Name Fetch karna
        name = addr_json.get('receiver_name') or addr_json.get('name')
        if not name and obj.user: 
            name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        if not name:
            name = "Customer" # Agar koi name nahi mila toh default "Customer" dikhayega
            
        details.append(f"👤 <b>Name:</b> {name}")

        # 2. Customer Phone Fetch karna
        phone = addr_json.get('receiver_phone') or addr_json.get('phone')
        if not phone and obj.user: 
            phone = getattr(obj.user, 'phone', None)
            
        if phone:
            details.append(f"📞 <b>Phone:</b> {phone}")

        # 3. Address aur City
        if addr_json.get('full_address'): 
            details.append(f"🏠 <b>Address:</b> {addr_json.get('full_address')}")
        if addr_json.get('city'): 
            details.append(f"🏙️ <b>City:</b> {addr_json.get('city')}")

        if not details: 
            return "No Details Found"
            
        return format_html("<br>".join(details))
        
    full_delivery_address.short_description = "Customer & Address Details"

    def Maps_link(self, obj):
        addr = obj.delivery_address_json or {}
        lat, lng = addr.get('latitude') or addr.get('lat'), addr.get('longitude') or addr.get('lng')
        if lat is None or lng is None: return format_html('<span style="color:gray;">N/A</span>')
        url = f"http://maps.google.com/maps?q=loc:{lat},{lng}"
        return format_html('<a style="background-color: #007bff; color: white; padding: 4px 8px; border-radius: 4px; text-decoration: none; font-size:11px; font-weight: bold;" href="{}" target="_blank">📍 MAP</a>', url)
    Maps_link.short_description = "Directions"

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
                        order.total_amount = F('total_amount') - item_total
                        order.save(update_fields=['total_amount'])
                        order.refresh_from_db()
                        
                        if order.payment_method == 'RAZORPAY':
                            try:
                                from apps.payments.models import Payment
                                from apps.payments.refund_services import RefundService
                                payment = Payment.objects.filter(order=order, status='paid').first()
                                if payment:
                                    RefundService.initiate_partial_refund(payment, item_total)
                                    self.message_user(request, f"Item '{instance.product_name}' cancelled. ₹{item_total} auto-refunded!", level=messages.SUCCESS)
                                else:
                                    self.message_user(request, f"NO valid payment record found to auto-refund ₹{item_total}.", level=messages.WARNING)
                            except Exception as e:
                                self.message_user(request, f"Auto-Refund failed: {str(e)}", level=messages.ERROR)
                        else:
                            self.message_user(request, f"Item cancelled. COD Amount reduced. New Total: ₹{order.total_amount}", level=messages.SUCCESS)
            instance.save()
        formset.save_m2m()

    # --- FULLY WORKING BULK ACTIONS ---
    @admin.action(description="🔵 Mark as Confirmed")
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f"{updated} Orders marked as Confirmed.")

    @admin.action(description="🟡 Mark as Picking")
    def mark_as_picking(self, request, queryset):
        updated = queryset.update(status='picking')
        self.message_user(request, f"{updated} Orders marked as Picking.")

    @admin.action(description="📦 Mark as Packed")
    def mark_as_packed(self, request, queryset):
        updated = queryset.update(status='packed')
        self.message_user(request, f"{updated} Orders marked as Packed.")

    @admin.action(description="🚚 Mark as Out For Delivery")
    def mark_as_out_for_delivery(self, request, queryset):
        updated = queryset.update(status='out_for_delivery')
        self.message_user(request, f"{updated} Orders marked as Out For Delivery.")

    @admin.action(description="✅ Mark as Delivered")
    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status='delivered')
        self.message_user(request, f"{updated} Orders successfully Delivered!")

    @admin.action(description="❌ Mark as Cancelled")
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f"{updated} Orders Cancelled.", level=messages.WARNING)


@admin.register(OrderItemFulfillment)
class OrderItemFulfillmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_id_link', 'sku_link', 'batch_id', 'vendor_phone', 'quantity_allocated', 'vendor_payable_amount', 'created_at')
    list_filter = ('created_at',)
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
        owner_obj = getattr(obj.inventory_batch, 'owner', None)
        if owner_obj:
            phone = getattr(owner_obj, 'phone', 'Vendor')
            return format_html('<span style="color: blue; font-weight: bold;">{}</span>', phone)
        return format_html('<span style="color: green; font-weight: bold;">Company</span>')
    vendor_phone.short_description = "Vendor"


@admin.register(OrderAbuseLog)
class OrderAbuseLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'cancelled_orders', 'blocked_until', 'is_blocked_status', 'updated_at')
    search_fields = ('user__phone',)
    list_filter = ('updated_at',)
    raw_id_fields = ('user',)

    def is_blocked_status(self, obj):
        if obj.is_blocked():
            return format_html('<span style="color:red; font-weight:bold;">🚫 Blocked</span>')
        return format_html('<span style="color:green;">✓ Safe</span>')
    is_blocked_status.short_description = "Status"


@admin.register(OrderConfiguration)
class OrderConfigurationAdmin(admin.ModelAdmin):
    list_display = ['delivery_fee', 'free_delivery_threshold']
    list_per_page = 25
    
    def has_add_permission(self, request):
        # Configuration file ek hi honi chahiye (Singleton)
        if OrderConfiguration.objects.exists():
            return False
        return super().has_add_permission(request)