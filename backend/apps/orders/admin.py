from django.contrib import admin
from django.contrib import messages # <--- ADDED FOR ADMIN MESSAGES
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

# IMPORT NEW MODEL
from .models import Order, OrderItem, OrderConfiguration, OrderItemFulfillment
from apps.catalog.models import Product
from apps.warehouse.models import Warehouse
from apps.delivery.tasks import retry_auto_assign_rider
from apps.customers.models import CustomerAddress 

User = get_user_model()


class OrderResource(resources.ModelResource):
    # Linking User by phone
    user = fields.Field(
        column_name='user_phone',
        attribute='user',
        widget=ForeignKeyWidget(User, 'phone')
    )
    # Linking Warehouse by name
    warehouse = fields.Field(
        column_name='warehouse_name',
        attribute='warehouse',
        widget=ForeignKeyWidget(Warehouse, 'name')
    )

    class Meta:
        model = Order
        fields = (
            'id', 
            'user', 
            'warehouse', 
            'status', 
            'delivery_type', 
            'payment_method', 
            'total_amount', 
            'delivery_address_json', 
            'created_at', 
            'updated_at'
        )
        export_order = fields


class OrderItemResource(resources.ModelResource):
    # Linking Order by id
    order = fields.Field(
        column_name='order_id',
        attribute='order',
        widget=ForeignKeyWidget(Order, 'id')
    )

    class Meta:
        model = OrderItem
        fields = ('id', 'order', 'sku', 'product_name', 'quantity', 'price')
        export_order = fields


class OrderConfigurationResource(resources.ModelResource):
    class Meta:
        model = OrderConfiguration
        fields = ('id', 'delivery_fee', 'free_delivery_threshold')
        export_order = fields


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # ADDED fulfillment_details HERE
    readonly_fields = ('product_image', 'sku', 'product_name', 'quantity', 'price', 'subtotal', 'fulfillment_details')
    can_delete = False
    
    # ---> UPDATED: Added 'status' and 'cancel_reason' to fields so admin can edit them
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

    # --- NEW METHOD: Shows Vendor details inline in Order Details ---
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
        'id',
        'customer_phone',
        'warehouse_name',
        'status_badge',
        'payment_method',
        'total_amount_display',
        'delivery_type',
        'delivery_name',
        'delivery_phone',
        'Maps_link',
        'created_at_date'
    )
    list_filter = (
        'status',
        'warehouse',
        'created_at',
        'payment_method',
        'delivery_type'
    )
    search_fields = (
        'id',
        'user__phone',
        'user__first_name',
        'user__last_name',
        'warehouse__name',
        'warehouse__code'
    )
    list_select_related = ('user', 'warehouse')
    raw_id_fields = ('user', 'warehouse')
    inlines = [OrderItemInline]
    list_per_page = 25
    actions = [
        'mark_as_confirmed',
        'mark_as_picking',
        'mark_as_packed',
        'mark_as_out_for_delivery',
        'mark_as_delivered',
        'cancel_orders'
    ]

    fieldsets = (
        ('Order Information', {
            'fields': ('id', 'user', 'warehouse')
        }),
        ('Order Details', {
            'fields': ('status', 'delivery_type', 'payment_method', 'total_amount')
        }),
        ('Delivery Address Details', {
            'fields': ('delivery_name', 'delivery_phone', 'full_delivery_address', 'Maps_link')
        }),
        ('Raw Delivery JSON (For Debugging)', {
            'fields': ('delivery_address_json',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('id', 'created_at', 'updated_at', 'total_amount', 'delivery_name', 'delivery_phone', 'full_delivery_address', 'Maps_link')

    # ---> NEW LOGIC FOR PARTIAL CANCEL + AUTO REFUND
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, OrderItem):
                if instance.pk:
                    old_instance = OrderItem.objects.get(pk=instance.pk)
                    old_status = getattr(old_instance, 'status', 'active')
                    new_status = getattr(instance, 'status', 'active')
                    
                    # Agar status abhi just cancel hua hai
                    if old_status != 'cancelled' and new_status == 'cancelled':
                        item_total = instance.price * instance.quantity
                        order = instance.order
                        order.total_amount -= item_total
                        order.save(update_fields=['total_amount'])
                        
                        if order.payment_method == 'online':
                            try:
                                # Payment integration calls
                                from apps.payments.models import Payment
                                from apps.payments.refund_services import RefundService
                                
                                # Order se linked paid payment dhundenge
                                payment = Payment.objects.filter(order=order, status='paid').first()
                                if payment:
                                    RefundService.initiate_partial_refund(payment, item_total)
                                    self.message_user(
                                        request, 
                                        f"Item '{instance.product_name}' cancelled. ₹{item_total} partial refund auto-initiated to bank!", 
                                        level=messages.SUCCESS
                                    )
                                else:
                                    self.message_user(
                                        request, 
                                        f"Item cancelled. Total deducted. But NO valid payment record found to auto-refund ₹{item_total}.", 
                                        level=messages.WARNING
                                    )
                            except Exception as e:
                                self.message_user(request, f"Item Cancelled. Auto-Refund failed: {str(e)}", level=messages.ERROR)
                        else:
                            self.message_user(
                                request, 
                                f"Item '{instance.product_name}' cancelled. COD Amount reduced by ₹{item_total}. New Total: ₹{order.total_amount}", 
                                level=messages.SUCCESS
                            )
            instance.save()
        formset.save_m2m()

    def customer_phone(self, obj):
        return obj.user.phone
    customer_phone.short_description = "Customer Phone"
    customer_phone.admin_order_field = 'user__phone'

    def warehouse_name(self, obj):
        return obj.warehouse.name if obj.warehouse else "N/A"
    warehouse_name.short_description = "Warehouse"
    warehouse_name.admin_order_field = 'warehouse__name'

    def status_badge(self, obj):
        colors = {
            'created': '#6c757d',
            'confirmed': '#007bff',
            'picking': '#ffc107',
            'packed': '#28a745',
            'out_for_delivery': '#17a2b8',
            'delivered': '#28a745',
            'cancelled': '#dc3545',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def total_amount_display(self, obj):
        return f"₹{obj.total_amount:.2f}"
    total_amount_display.short_description = "Total Amount"
    total_amount_display.admin_order_field = 'total_amount'

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    def delivery_name(self, obj):
        addr = obj.delivery_address_json or {}
        name = addr.get('receiver_name') or addr.get('name')
        
        if not name and addr.get('id'):
            try:
                real_addr = CustomerAddress.objects.get(id=addr.get('id'))
                name = real_addr.receiver_name
            except Exception:
                pass
                
        if not name and obj.user:
            name = f"{obj.user.first_name} {obj.user.last_name}".strip()
            
        return name or "N/A"
    delivery_name.short_description = "Delivery Name"

    def delivery_phone(self, obj):
        addr = obj.delivery_address_json or {}
        phone = addr.get('receiver_phone') or addr.get('phone')
        
        if not phone and addr.get('id'):
            try:
                real_addr = CustomerAddress.objects.get(id=addr.get('id'))
                phone = real_addr.receiver_phone
            except Exception:
                pass
                
        if not phone and obj.user:
            phone = getattr(obj.user, 'phone', None)
            
        return phone or "N/A"
    delivery_phone.short_description = "Delivery Phone"

    def full_delivery_address(self, obj):
        addr_json = obj.delivery_address_json or {}
        if not addr_json:
            return "No Address Details Found"
            
        details = []
        
        real_addr = None
        if addr_json.get('id'):
            try:
                real_addr = CustomerAddress.objects.get(id=addr_json.get('id'))
            except Exception:
                pass

        if real_addr:
            if real_addr.house_no: details.append(f"<b>House/Flat:</b> {real_addr.house_no}")
            if real_addr.floor_no: details.append(f"<b>Floor:</b> {real_addr.floor_no}")
            if real_addr.apartment_name: details.append(f"<b>Building:</b> {real_addr.apartment_name}")
            if real_addr.landmark: details.append(f"<b>Landmark:</b> {real_addr.landmark}")
            
            city = real_addr.city or addr_json.get('city', '')
            if city or real_addr.pincode:
                details.append(f"<b>Area:</b> {city} - {real_addr.pincode}")
                
            if real_addr.google_address_text: 
                details.append(f"<b>Map Address:</b> {real_addr.google_address_text}")
        else:
            if addr_json.get('full_address'): 
                details.append(f"<b>Full Address:</b> {addr_json.get('full_address')}")
            if addr_json.get('city'):
                details.append(f"<b>City:</b> {addr_json.get('city')}")
            
        if not details:
            return str(addr_json) 
            
        return format_html("<br>".join(details))
    full_delivery_address.short_description = "Complete Address Details"

    def Maps_link(self, obj):
        addr = obj.delivery_address_json or {}
        lat = addr.get('latitude') or addr.get('lat')
        lng = addr.get('longitude') or addr.get('lng')
        
        if lat is None or lng is None:
            return format_html('<span style="color:red;">Location Missing</span>')
            
        url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
        return format_html(
            '<a style="background-color: #28a745; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block;" href="{}" target="_blank" rel="noopener noreferrer">📍 Get Directions</a>', 
            url
        )
    Maps_link.short_description = "Customer Map Location"


    def mark_as_confirmed(self, request, queryset):
        updated = queryset.filter(status='created').update(status='confirmed')
        self.message_user(request, f"{updated} orders marked as confirmed.")
    mark_as_confirmed.short_description = "Mark selected orders as Confirmed"

    def mark_as_picking(self, request, queryset):
        updated = queryset.filter(status__in=['created', 'confirmed']).update(status='picking')
        self.message_user(request, f"{updated} orders marked as picking.")
    mark_as_picking.short_description = "Mark selected orders as Picking"

    def mark_as_packed(self, request, queryset):
        orders_to_update = list(queryset.filter(status__in=['created', 'confirmed', 'picking']).values_list('id', flat=True))
        
        if not orders_to_update:
            self.message_user(request, "No eligible orders found.")
            return

        updated = queryset.filter(id__in=orders_to_update).update(status='packed')
        
        for order_id in orders_to_update:
            retry_auto_assign_rider.delay(order_id)

        self.message_user(request, f"{updated} orders marked as packed. Auto-assigning riders...")
    
    mark_as_packed.short_description = "Mark selected orders as Packed"

    def mark_as_out_for_delivery(self, request, queryset):
        updated = queryset.filter(status__in=['created', 'confirmed', 'picking', 'packed']).update(status='out_for_delivery')
        self.message_user(request, f"{updated} orders marked as out for delivery.")
    mark_as_out_for_delivery.short_description = "Mark selected orders as Out for Delivery"

    def mark_as_delivered(self, request, queryset):
        updated = queryset.filter(status__in=['created', 'confirmed', 'picking', 'packed', 'out_for_delivery']).update(status='delivered')
        self.message_user(request, f"{updated} orders marked as delivered.")
    mark_as_delivered.short_description = "Mark selected orders as Delivered"

    def cancel_orders(self, request, queryset):
        updated = queryset.exclude(status__in=['delivered', 'cancelled']).update(status='cancelled')
        self.message_user(request, f"{updated} orders cancelled.")
    cancel_orders.short_description = "Cancel selected orders"


@admin.register(OrderItemFulfillment)
class OrderItemFulfillmentAdmin(admin.ModelAdmin):
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
    list_filter = ['delivery_fee', 'free_delivery_threshold']
    search_fields = ['delivery_fee', 'free_delivery_threshold']
    list_per_page = 25
    readonly_fields = ['delivery_fee', 'free_delivery_threshold']