from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime
from django.db import models
from django.urls import path            
from django.http import JsonResponse    
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin
from django.contrib.auth import get_user_model

from .models import InventoryItem, InventoryTransaction
from apps.catalog.models import Product 
from apps.warehouse.models import Bin

User = get_user_model()

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
        import_id_fields = ('sku', 'bin') # Update based on Batch identification
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


@admin.register(InventoryItem)
class InventoryItemAdmin(ImportExportModelAdmin):
    resource_class = InventoryItemResource
    
    class Media:
        js = ('inventory/js/sku_lookup.js',)

    list_display = (
        'sku', 'product_name', 'owner_status', 'cost_price', 'price', 
        'warehouse_name', 'bin_location', 'total_stock', 'available_stock',
        'stock_status', 'mode_badge', 'updated_at_date'
    )
    list_filter = (
        'mode', 'owner', 'updated_at'
    )
    search_fields = (
        'sku', 'product_name', 'owner__phone', 'bin__bin_code'
    )
    list_select_related = (
        'bin', 'owner', 'bin__rack', 'bin__rack__aisle', 
        'bin__rack__aisle__zone', 'bin__rack__aisle__zone__warehouse'
    )
    raw_id_fields = ('bin', 'owner')
    list_per_page = 25
    
    list_editable = ('total_stock', 'price', 'cost_price')
    actions = ['mark_low_stock', 'clear_reservations', 'update_from_catalog']

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
    # ENTERPRISE WAREHOUSE ISOLATION LOGIC
    # ==========================================
    def get_queryset(self, request):
        """Strictly isolate Inventory to the Admin's selected session Warehouse."""
        qs = super().get_queryset(request)
        selected_warehouse_id = request.session.get('selected_warehouse_id')
        if selected_warehouse_id:
            return qs.filter(bin__rack__aisle__zone__warehouse_id=selected_warehouse_id)
        # Fallback to none if they somehow bypass middleware
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Only allow selecting Bins that belong to the current Warehouse."""
        if db_field.name == "bin":
            selected_warehouse_id = request.session.get('selected_warehouse_id')
            if selected_warehouse_id:
                kwargs["queryset"] = Bin.objects.filter(rack__aisle__zone__warehouse_id=selected_warehouse_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    # ==========================================

    def owner_status(self, obj):
        if hasattr(obj, 'owner') and obj.owner:
            return format_html('<span style="color: blue; font-weight: bold;">Vendor: {}</span>', obj.owner.phone)
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
                return f"₹ {product.mrp}"
        return "Not Found in Catalog"
    product_mrp_display.short_description = "Product Base MRP"

    def warehouse_name(self, obj):
        return obj.bin.rack.aisle.zone.warehouse.name
    warehouse_name.short_description = "Warehouse"

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
            return format_html('<span style="color: green;">GOOD ({})</span>', available)
    stock_status.short_description = "Status"

    def mode_badge(self, obj):
        colors = {'owned': '#28a745', 'consignment': '#ffc107', 'virtual': '#6c757d'}
        color = colors.get(obj.mode, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>', color, obj.get_mode_display())
    mode_badge.short_description = "Mode"

    def updated_at_date(self, obj):
        if hasattr(obj, 'updated_at') and obj.updated_at:
            return localtime(obj.updated_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    updated_at_date.short_description = "Updated"


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(ImportExportModelAdmin):
    resource_class = InventoryTransactionResource
    list_display = (
        'inventory_item_info', 'transaction_type_badge', 'quantity_display', 
        'reference', 'warehouse_name', 'created_at_date'
    )
    list_filter = (
        'transaction_type', 'created_at'
    )
    search_fields = ('inventory_item__sku', 'inventory_item__product_name', 'reference')
    list_select_related = (
        'inventory_item', 'inventory_item__bin', 'inventory_item__bin__rack', 
        'inventory_item__bin__rack__aisle', 'inventory_item__bin__rack__aisle__zone', 
        'inventory_item__bin__rack__aisle__zone__warehouse'
    )
    raw_id_fields = ('inventory_item',)
    list_per_page = 25
    readonly_fields = ('created_at',)

    # ==========================================
    # ENTERPRISE WAREHOUSE ISOLATION LOGIC
    # ==========================================
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        selected_warehouse_id = request.session.get('selected_warehouse_id')
        if selected_warehouse_id:
            return qs.filter(inventory_item__bin__rack__aisle__zone__warehouse_id=selected_warehouse_id)
        return qs.none()
    # ==========================================

    def inventory_item_info(self, obj):
        return f"{obj.inventory_item.sku} - {obj.inventory_item.product_name}"
    inventory_item_info.short_description = "Item"

    def transaction_type_badge(self, obj):
        colors = {'add': '#28a745', 'reserve': '#ffc107', 'release': '#17a2b8', 'commit': '#007bff', 'adjust': '#dc3545'}
        color = colors.get(obj.transaction_type, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>', color, obj.get_transaction_type_display())
    transaction_type_badge.short_description = "Type"

    def quantity_display(self, obj):
        if obj.quantity > 0: return format_html('<span style="color: green;">+{}</span>', obj.quantity)
        else: return format_html('<span style="color: red;">{}</span>', obj.quantity)
    quantity_display.short_description = "Quantity"

    def warehouse_name(self, obj):
        return obj.inventory_item.bin.rack.aisle.zone.warehouse.name
    warehouse_name.short_description = "Warehouse"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"