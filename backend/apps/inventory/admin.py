from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db import models
from .models import InventoryItem, InventoryTransaction


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        'sku',
        'product_name',
        'warehouse_name',
        'bin_location',
        'total_stock',
        'available_stock',
        'reserved_stock',
        'stock_status',
        'mode_badge',
        'updated_at_date'
    )
    list_filter = (
        'mode',
        'bin__rack__aisle__zone__warehouse',
        'updated_at'
    )
    search_fields = (
        'sku',
        'product_name',
        'bin__bin_code',
        'bin__rack__number'  # Fixed: changed from rack_number to number
    )
    # Optimized to prevent N+1 queries
    list_select_related = (
        'bin', 
        'bin__rack', 
        'bin__rack__aisle', 
        'bin__rack__aisle__zone', 
        'bin__rack__aisle__zone__warehouse'
    )
    raw_id_fields = ('bin',)
    list_per_page = 25
    list_editable = ('total_stock', 'reserved_stock')
    actions = ['mark_low_stock', 'clear_reservations', 'update_from_catalog']

    fieldsets = (
        ('Product Information', {
            'fields': ('bin', 'sku', 'product_name', 'price')
        }),
        ('Stock Levels', {
            'fields': ('total_stock', 'reserved_stock', 'mode', 'lead_time_hours')
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('updated_at',)

    def warehouse_name(self, obj):
        return obj.warehouse.name
    warehouse_name.short_description = "Warehouse"
    warehouse_name.admin_order_field = 'bin__rack__aisle__zone__warehouse__name'

    def bin_location(self, obj):
        # FIXED: uses .number for both Aisle and Rack based on your warehouse/models.py
        return f"{obj.bin.rack.aisle.zone.name} - A{obj.bin.rack.aisle.number} - R{obj.bin.rack.number} - B{obj.bin.bin_code}"
    bin_location.short_description = "Bin Location"

    def available_stock(self, obj):
        return obj.available_stock
    available_stock.short_description = "Available"
    available_stock.admin_order_field = 'total_stock'

    def stock_status(self, obj):
        available = obj.available_stock
        if available <= 0:
            return format_html('<span style="color: red; font-weight: bold;">OUT OF STOCK</span>')
        elif available <= 10:
            return format_html('<span style="color: orange; font-weight: bold;">LOW STOCK ({})</span>', available)
        else:
            return format_html('<span style="color: green;">IN STOCK ({})</span>', available)
    stock_status.short_description = "Status"

    def mode_badge(self, obj):
        colors = {
            'owned': '#28a745',
            'consignment': '#ffc107',
            'virtual': '#6c757d',
        }
        color = colors.get(obj.mode, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_mode_display()
        )
    mode_badge.short_description = "Mode"

    def updated_at_date(self, obj):
        return obj.updated_at.strftime('%d/%m/%Y %H:%M')
    updated_at_date.short_description = "Updated"
    updated_at_date.admin_order_field = 'updated_at'

    # Admin Actions
    @admin.action(description='Mark selected items as low stock (set reserved to total)')
    def mark_low_stock(self, request, queryset):
        updated = queryset.update(reserved_stock=models.F('total_stock'))
        self.message_user(request, f"{updated} items marked as low stock.")

    @admin.action(description='Clear all reservations for selected items')
    def clear_reservations(self, request, queryset):
        updated = queryset.update(reserved_stock=0)
        self.message_user(request, f"Reservations cleared for {updated} items.")

    @admin.action(description='Update product details from catalog')
    def update_from_catalog(self, request, queryset):
        from apps.catalog.models import Product
        updated = 0
        for item in queryset:
            product = Product.objects.filter(sku=item.sku).first()
            if product:
                item.product_name = product.name
                item.price = product.mrp
                item.save()
                updated += 1
        self.message_user(request, f"Updated {updated} items from catalog.")


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'inventory_item_info',
        'transaction_type_badge',
        'quantity_display',
        'reference',
        'warehouse_name',
        'created_at_date'
    )
    list_filter = (
        'transaction_type',
        'created_at',
        'inventory_item__bin__rack__aisle__zone__warehouse'
    )
    search_fields = (
        'inventory_item__sku',
        'inventory_item__product_name',
        'reference'
    )
    list_select_related = (
        'inventory_item',
        'inventory_item__bin',
        'inventory_item__bin__rack',
        'inventory_item__bin__rack__aisle',
        'inventory_item__bin__rack__aisle__zone',
        'inventory_item__bin__rack__aisle__zone__warehouse'
    )
    raw_id_fields = ('inventory_item',)
    list_per_page = 25

    readonly_fields = ('created_at',)

    def inventory_item_info(self, obj):
        return f"{obj.inventory_item.sku} - {obj.inventory_item.product_name}"
    inventory_item_info.short_description = "Item"
    inventory_item_info.admin_order_field = 'inventory_item__sku'

    def transaction_type_badge(self, obj):
        colors = {
            'add': '#28a745',
            'reserve': '#ffc107',
            'release': '#17a2b8',
            'commit': '#007bff',
            'adjust': '#dc3545',
        }
        color = colors.get(obj.transaction_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_transaction_type_display()
        )
    transaction_type_badge.short_description = "Type"

    def quantity_display(self, obj):
        if obj.quantity > 0:
            return format_html('<span style="color: green;">+{}</span>', obj.quantity)
        else:
            return format_html('<span style="color: red;">{}</span>', obj.quantity)
    quantity_display.short_description = "Quantity"
    quantity_display.admin_order_field = 'quantity'

    def warehouse_name(self, obj):
        return obj.inventory_item.warehouse.name
    warehouse_name.short_description = "Warehouse"
    warehouse_name.admin_order_field = 'inventory_item__bin__rack__aisle__zone__warehouse__name'

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %H:%M')
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'