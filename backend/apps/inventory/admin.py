from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime
from django.db.models import F
from django.urls import path            
from django.http import JsonResponse    

# Import Export Magic for Master Admin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from django.contrib.auth import get_user_model

from .models import InventoryItem, InventoryTransaction
from apps.catalog.models import Product 
from apps.warehouse.models import Bin

User = get_user_model()

# ==========================================
# 1. CSV IMPORT / EXPORT RESOURCES
# ==========================================
class InventoryItemResource(resources.ModelResource):
    bin = fields.Field(
        column_name='bin_code',
        attribute='bin',
        widget=ForeignKeyWidget(Bin, 'bin_code')
    )
    owner = fields.Field(
        column_name='owner_phone',
        attribute='owner',
        widget=ForeignKeyWidget(User, 'phone')
    )

    class Meta:
        model = InventoryItem
        import_id_fields = ('sku', 'bin')
        fields = (
            'id', 'bin', 'sku', 'product_name', 'price', 'owner',
            'cost_price', 'total_stock', 'reserved_stock', 'mode', 
            'lead_time_hours'
        )

    def before_import_row(self, row, **kwargs):
        """Unified import logic: auto-fills defaults to prevent DB crashes."""
        if not row.get('price'): row['price'] = 0
        if not row.get('cost_price'): row['cost_price'] = 0.0
        if not row.get('total_stock'): row['total_stock'] = 0
        if not row.get('reserved_stock'): row['reserved_stock'] = 0
        if not row.get('mode'): row['mode'] = 'owned'
        if not row.get('lead_time_hours'): row['lead_time_hours'] = 0

class InventoryTransactionResource(resources.ModelResource):
    inventory_item = fields.Field(
        column_name='inventory_batch_id',
        attribute='inventory_item',
        widget=ForeignKeyWidget(InventoryItem, 'id')
    )

    class Meta:
        model = InventoryTransaction
        import_id_fields = ('id',)
        fields = (
            'id', 'inventory_item', 'transaction_type', 'quantity', 
            'reference', 'created_at'
        )


# ==========================================
# 2. MASTER ADMIN VIEWS
# ==========================================
@admin.register(InventoryItem)
class InventoryItemAdmin(ImportExportModelAdmin):
    """UPGRADED: Full Access to Master Admin, No Warehouse Scoping"""
    resource_class = InventoryItemResource
    
    class Media:
        js = ('inventory/js/sku_lookup.js',)

    list_display = (
        'id', 'sku', 'product_name', 'warehouse_name', 'bin_location', 
        'owner_status', 'cost_price', 'price', 
        'total_stock', 'available_stock',
        'stock_status', 'mode_badge', 'updated_at_date'
    )
    list_display_links = ('id', 'sku', 'product_name')
    
    # Global Warehouse Filter Added
    list_filter = (
        'bin__rack__aisle__zone__warehouse', 'mode', 'owner', 'updated_at'
    )
    search_fields = (
        'sku', 'product_name', 'owner__phone', 'bin__bin_code'
    )
    list_select_related = (
        'bin', 'owner', 'bin__rack', 'bin__rack__aisle', 
        'bin__rack__aisle__zone', 'bin__rack__aisle__zone__warehouse'
    )
    raw_id_fields = ('bin', 'owner')
    list_per_page = 50
    
    # Quick Edits for fast management
    list_editable = ('total_stock', 'price', 'cost_price')
    
    # Fully working actions
    actions = ['clear_reservations', 'update_from_catalog', 'add_emergency_stock']

    fieldsets = (
        ('Product Information', {
            'fields': ('bin', 'sku', 'product_name', 'product_mrp_display', 'price')
        }),
        ('Ownership & Costing', {
            'fields': ('owner', 'cost_price', 'mode')
        }),
        ('Stock Levels', {
            'fields': ('total_stock', 'reserved_stock', 'lead_time_hours')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'product_mrp_display')

    # ==========================================
    # DISPLAY METHODS
    # ==========================================
    def owner_status(self, obj):
        if hasattr(obj, 'owner') and obj.owner:
            return format_html('<span style="color: blue; font-weight: bold;">{}</span>', obj.owner.phone)
        return format_html('<span style="color: green; font-weight: bold;">Company</span>')
    owner_status.short_description = "Owner"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('lookup-product-data/', self.admin_site.admin_view(self.lookup_product_data), name='inventory-product-lookup'),
        ]
        return my_urls + urls

    def lookup_product_data(self, request):
        sku = request.GET.get('sku')
        data = {'found': False}
        if sku:
            product = Product.objects.filter(sku__iexact=sku).first()
            if product:
                data = {
                    'found': True,
                    'name': product.name,
                    'price': str(product.mrp) 
                }
        return JsonResponse(data)

    def product_mrp_display(self, obj):
        if obj and obj.sku:
            product = Product.objects.filter(sku__iexact=obj.sku).first()
            if product:
                return format_html('<b style="color:blue;">₹ {}</b>', product.mrp)
        return "Not in Catalog"
    product_mrp_display.short_description = "Catalog MRP"

    def warehouse_name(self, obj):
        return obj.bin.rack.aisle.zone.warehouse.name
    warehouse_name.short_description = "Warehouse"
    warehouse_name.admin_order_field = 'bin__rack__aisle__zone__warehouse__name'

    def bin_location(self, obj):
        return f"{obj.bin.rack.aisle.zone.name} - B{obj.bin.bin_code}"
    bin_location.short_description = "Bin Location"

    def available_stock(self, obj):
        return obj.available_stock
    available_stock.short_description = "Available"

    def stock_status(self, obj):
        available = obj.available_stock
        if available <= 0:
            return format_html('<span style="color: red; font-weight: bold;">OUT OF STOCK</span>')
        elif available <= 10:
            return format_html('<span style="color: orange; font-weight: bold;">LOW ({})</span>', available)
        else:
            return format_html('<span style="color: green; font-weight: bold;">GOOD</span>')
    stock_status.short_description = "Status"

    def mode_badge(self, obj):
        colors = {'owned': '#28a745', 'consignment': '#ffc107', 'virtual': '#6c757d'}
        color = colors.get(obj.mode, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; font-weight: bold;">{}</span>', color, obj.get_mode_display().upper())
    mode_badge.short_description = "Mode"

    def updated_at_date(self, obj):
        if hasattr(obj, 'updated_at') and obj.updated_at:
            return localtime(obj.updated_at).strftime('%d %b, %H:%M')
        return "N/A"
    updated_at_date.short_description = "Last Updated"

    # ==========================================
    # WORKING BULK ACTIONS
    # ==========================================
    @admin.action(description="🧹 Clear Reserved Stock (Reset to 0)")
    def clear_reservations(self, request, queryset):
        updated = queryset.update(reserved_stock=0)
        self.message_user(request, f"Successfully cleared reservations for {updated} inventory batches.")

    @admin.action(description="🔄 Sync Name & Price from Catalog")
    def update_from_catalog(self, request, queryset):
        count = 0
        for item in queryset:
            product = Product.objects.filter(sku__iexact=item.sku).first()
            if product:
                item.product_name = product.name
                item.price = product.mrp
                item.save(update_fields=['product_name', 'price'])
                count += 1
        self.message_user(request, f"Successfully synced {count} inventory items with Master Catalog.", level=messages.SUCCESS)

    @admin.action(description="📦 EMERGENCY: Add 50 Stock to Selected")
    def add_emergency_stock(self, request, queryset):
        queryset.update(total_stock=F('total_stock') + 50)
        self.message_user(request, "Added 50 emergency stock to selected items.", level=messages.WARNING)


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(ImportExportModelAdmin):
    """UPGRADED: Global View for Inventory Logs"""
    resource_class = InventoryTransactionResource
    
    list_display = (
        'id', 'inventory_item_info', 'transaction_type_badge', 'quantity_display', 
        'reference', 'warehouse_name', 'created_at_date'
    )
    list_display_links = ('id', 'inventory_item_info')
    list_filter = (
        'inventory_item__bin__rack__aisle__zone__warehouse', 'transaction_type', 'created_at'
    )
    search_fields = ('inventory_item__sku', 'inventory_item__product_name', 'reference')
    list_select_related = (
        'inventory_item', 'inventory_item__bin', 'inventory_item__bin__rack', 
        'inventory_item__bin__rack__aisle', 'inventory_item__bin__rack__aisle__zone', 
        'inventory_item__bin__rack__aisle__zone__warehouse'
    )
    raw_id_fields = ('inventory_item', 'order')
    list_per_page = 50
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    # Strict Data Integrity: Admin can view logs, but shouldn't modify past records
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def inventory_item_info(self, obj):
        return f"{obj.inventory_item.sku} - {obj.inventory_item.product_name}"
    inventory_item_info.short_description = "Item"

    def transaction_type_badge(self, obj):
        colors = {'add': '#28a745', 'reserve': '#ffc107', 'release': '#17a2b8', 'commit': '#007bff', 'adjust': '#dc3545'}
        color = colors.get(obj.transaction_type, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; font-weight: bold;">{}</span>', color, obj.get_transaction_type_display().upper())
    transaction_type_badge.short_description = "Type"

    def quantity_display(self, obj):
        if obj.quantity > 0: return format_html('<span style="color: green; font-weight: bold;">+{}</span>', obj.quantity)
        else: return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.quantity)
    quantity_display.short_description = "Qty Change"

    def warehouse_name(self, obj):
        return obj.inventory_item.bin.rack.aisle.zone.warehouse.name
    warehouse_name.short_description = "Warehouse"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d %b, %H:%M:%S')
        return "N/A"
    created_at_date.short_description = "Timestamp"