from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Order, OrderItem
from .models import OrderConfiguration
from apps.catalog.models import Product
from apps.delivery.tasks import retry_auto_assign_rider

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # 3. 'product_image' ko readonly_fields aur fields mein add karein
    readonly_fields = ('product_image', 'sku', 'product_name', 'quantity', 'price', 'subtotal')
    can_delete = False
    fields = ('product_image', 'sku', 'product_name', 'quantity', 'price', 'subtotal')
    show_change_link = False

    # 4. Image dikhane ke liye custom function banayein
    def product_image(self, obj):
        if obj.sku:
            # SKU ke basis par Product find karein
            product = Product.objects.filter(sku=obj.sku).first()
            if product and product.image:
                # Agar product aur image mil jaye, toh HTML <img> tag return karein
                return format_html(
                    '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 4px; box-shadow: 0 0 2px rgba(0,0,0,0.3);" />', 
                    product.image
                )
        return "No Image"
    product_image.short_description = "Image" # Column ka naam

    def subtotal(self, obj):
        if obj.price is None or obj.quantity is None:
            return "₹0.00"
        return f"₹{obj.price * obj.quantity:.2f}"
    subtotal.short_description = "Subtotal"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
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
            # Yahan humne naya 'full_delivery_address' add kiya hai taaki saari details dikhein
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
        return obj.created_at.strftime('%d/%m/%Y %H:%M')
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # --- Delivery address helpers ---
    def delivery_name(self, obj):
        addr = obj.delivery_address_json or {}
        # Frontend se data 'receiver_name' field mein aata hai
        name = addr.get('receiver_name') or addr.get('name') or addr.get('full_name') or addr.get('contact_name')
        return name or "N/A"
    delivery_name.short_description = "Delivery Name"

    def delivery_phone(self, obj):
        addr = obj.delivery_address_json or {}
        # Frontend se data 'receiver_phone' field mein aata hai
        phone = addr.get('receiver_phone') or addr.get('phone') or addr.get('mobile') or addr.get('phone_number')
        return phone or "N/A"
    delivery_phone.short_description = "Delivery Phone"

    # NAYA FUNCTION: Frontend ka poora data neatly line-by-line dikhane ke liye
    def full_delivery_address(self, obj):
        addr = obj.delivery_address_json or {}
        if not addr:
            return "No Address Details Found"
            
        details = []
        if addr.get('house_no'): details.append(f"<b>House/Flat:</b> {addr.get('house_no')}")
        if addr.get('floor_no'): details.append(f"<b>Floor:</b> {addr.get('floor_no')}")
        if addr.get('apartment_name'): details.append(f"<b>Building:</b> {addr.get('apartment_name')}")
        if addr.get('landmark'): details.append(f"<b>Landmark:</b> {addr.get('landmark')}")
        
        city = addr.get('city', '')
        pin = addr.get('pincode', '')
        if city or pin:
            details.append(f"<b>Area:</b> {city} - {pin}")
            
        if addr.get('google_address_text'): 
            details.append(f"<b>Map Address:</b> {addr.get('google_address_text')}")
            
        if not details:
            return "Address format is empty"
            
        return format_html("<br>".join(details))
    full_delivery_address.short_description = "Complete Address Details"

    def Maps_link(self, obj):
        addr = obj.delivery_address_json or {}
        # Safely get latitude / longitude
        lat = addr.get('latitude') or addr.get('lat')
        lng = addr.get('longitude') or addr.get('lng')
        
        if lat is None or lng is None:
            return format_html('<span style="color:red;">Location Missing</span>')
            
        # Naya Standard Google Maps Directions URL (Route map open karne ke liye)
        url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
        
        # Ek clear button style UI 
        return format_html(
            '<a style="background-color: #28a745; color: white; padding: 6px 12px; border-radius: 4px; text-decoration: none; font-weight: bold; display: inline-block;" href="{}" target="_blank" rel="noopener noreferrer">📍 Get Directions</a>', 
            url
        )
    Maps_link.short_description = "Customer Map Location"

    # --- Admin Actions Updates ---

    def mark_as_confirmed(self, request, queryset):
        updated = queryset.filter(status='created').update(status='confirmed')
        self.message_user(request, f"{updated} orders marked as confirmed.")
    mark_as_confirmed.short_description = "Mark selected orders as Confirmed"

    def mark_as_picking(self, request, queryset):
        updated = queryset.filter(status__in=['created', 'confirmed']).update(status='picking')
        self.message_user(request, f"{updated} orders marked as picking.")
    mark_as_picking.short_description = "Mark selected orders as Picking"

    # 2. Logic Update: Update status AND Trigger Rider Search
    def mark_as_packed(self, request, queryset):
        # ऑर्डर्स की ID निकालें
        orders_to_update = list(queryset.filter(status__in=['created', 'confirmed', 'picking']).values_list('id', flat=True))
        
        if not orders_to_update:
            self.message_user(request, "No eligible orders found.")
            return

        # Status Update करें
        updated = queryset.filter(id__in=orders_to_update).update(status='packed')
        
        # हर ऑर्डर के लिए राइडर ढूंढना शुरू करें
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


@admin.register(OrderConfiguration)
class OrderConfigurationAdmin(admin.ModelAdmin):
    list_display = ['delivery_fee', 'free_delivery_threshold']