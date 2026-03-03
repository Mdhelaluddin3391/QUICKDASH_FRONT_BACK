from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime
from leaflet.admin import LeafletGeoAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

from .models import Warehouse, PickingTask, PackingTask, StorageZone, Aisle, Rack, Bin
from apps.orders.models import Order
from apps.inventory.models import InventoryItem


class WarehouseResource(resources.ModelResource):
    class Meta:
        model = Warehouse
        import_id_fields = ('id',)
        fields = ('id', 'name', 'code', 'warehouse_type', 'city', 'state', 'location', 'delivery_zone', 'is_active', 'created_at')

class PickingTaskResource(resources.ModelResource):
    order = fields.Field(column_name='order_id', attribute='order', widget=ForeignKeyWidget(Order, 'id'))
    target_inventory_batch = fields.Field(column_name='target_batch_id', attribute='target_inventory_batch', widget=ForeignKeyWidget(InventoryItem, 'id'))
    
    class Meta:
        model = PickingTask
        fields = ('id', 'order', 'item_sku', 'quantity_to_pick', 'picker', 'target_inventory_batch', 'status', 'picked_at')

class PackingTaskResource(resources.ModelResource):
    order = fields.Field(column_name='order_id', attribute='order', widget=ForeignKeyWidget(Order, 'id'))
    
    class Meta:
        model = PackingTask
        fields = ('id', 'order', 'packer', 'is_completed', 'created_at')

class StorageZoneResource(resources.ModelResource):
    warehouse = fields.Field(column_name='warehouse_name', attribute='warehouse', widget=ForeignKeyWidget(Warehouse, 'code'))
    class Meta:
        model = StorageZone
        fields = ('id', 'warehouse', 'name')

class AisleResource(resources.ModelResource):
    zone = fields.Field(column_name='zone_name', attribute='zone', widget=ForeignKeyWidget(StorageZone, 'name'))
    class Meta:
        model = Aisle
        fields = ('id', 'zone', 'number')

class RackResource(resources.ModelResource):
    aisle = fields.Field(column_name='aisle_id', attribute='aisle', widget=ForeignKeyWidget(Aisle, 'id'))
    class Meta:
        model = Rack
        fields = ('id', 'aisle', 'number')

class BinResource(resources.ModelResource):
    rack = fields.Field(column_name='rack_id', attribute='rack', widget=ForeignKeyWidget(Rack, 'id'))
    class Meta:
        model = Bin
        fields = ('id', 'rack', 'bin_code', 'capacity_units')


# ==========================================
# ENTERPRISE WAREHOUSE ADMINS (STRICT ISOLATION)
# ==========================================

@admin.register(Warehouse)
class WarehouseAdmin(ImportExportModelAdmin, LeafletGeoAdmin):
    resource_class = WarehouseResource
    list_display = ('name', 'code', 'warehouse_type_display', 'city', 'is_active_badge', 'created_at_date')
    list_filter = ('warehouse_type', 'city', 'state', 'is_active')
    search_fields = ('name', 'code', 'city', 'state')
    list_per_page = 25
    actions = ['activate_warehouses', 'deactivate_warehouses']

    fieldsets = (
        ('Basic Information', {'fields': ('name', 'code', 'warehouse_type', 'is_active')}),
        ('Location Details', {'fields': ('city', 'state')}),
        ('Geographic Data', {'fields': ('location', 'delivery_zone'), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at',)
    settings_overrides = {'DEFAULT_CENTER': (20.5937, 78.9629), 'DEFAULT_ZOOM': 5}

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(id=wh_id)
        return qs.none()

    def warehouse_type_display(self, obj):
        type_colors = {'dark_store': '#28a745', 'mega': '#007bff'}
        color = type_colors.get(obj.warehouse_type, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>', color, obj.get_warehouse_type_display())
    warehouse_type_display.short_description = "Type"

    def is_active_badge(self, obj):
        if obj.is_active: return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"


@admin.register(StorageZone)
class StorageZoneAdmin(ImportExportModelAdmin):
    resource_class = StorageZoneResource
    list_display = ('name', 'warehouse_code')
    search_fields = ('name',)
    list_select_related = ('warehouse',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(warehouse_id=wh_id)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        wh_id = request.session.get('selected_warehouse_id')
        if db_field.name == "warehouse" and wh_id:
            kwargs["queryset"] = Warehouse.objects.filter(id=wh_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def warehouse_code(self, obj): return obj.warehouse.code
    warehouse_code.short_description = "Warehouse"


@admin.register(Aisle)
class AisleAdmin(ImportExportModelAdmin):
    resource_class = AisleResource
    list_display = ('number', 'zone_name', 'warehouse_info')
    list_select_related = ('zone', 'zone__warehouse')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(zone__warehouse_id=wh_id)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        wh_id = request.session.get('selected_warehouse_id')
        if db_field.name == "zone" and wh_id:
            kwargs["queryset"] = StorageZone.objects.filter(warehouse_id=wh_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def zone_name(self, obj): return obj.zone.name
    zone_name.short_description = "Zone"
    
    def warehouse_info(self, obj): return obj.zone.warehouse.code
    warehouse_info.short_description = "Warehouse"


@admin.register(Rack)
class RackAdmin(ImportExportModelAdmin):
    resource_class = RackResource
    list_display = ('number', 'aisle_info', 'warehouse_info')
    list_select_related = ('aisle', 'aisle__zone', 'aisle__zone__warehouse')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(aisle__zone__warehouse_id=wh_id)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        wh_id = request.session.get('selected_warehouse_id')
        if db_field.name == "aisle" and wh_id:
            kwargs["queryset"] = Aisle.objects.filter(zone__warehouse_id=wh_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def aisle_info(self, obj): return f"{obj.aisle.zone.name} - Aisle {obj.aisle.number}"
    aisle_info.short_description = "Aisle/Zone"
    
    def warehouse_info(self, obj): return obj.aisle.zone.warehouse.code
    warehouse_info.short_description = "Warehouse"


@admin.register(Bin)
class BinAdmin(ImportExportModelAdmin):
    resource_class = BinResource
    list_display = ('bin_code', 'capacity_units', 'rack_info')
    search_fields = ('bin_code',)
    list_select_related = ('rack', 'rack__aisle', 'rack__aisle__zone', 'rack__aisle__zone__warehouse')
    list_editable = ('capacity_units',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(rack__aisle__zone__warehouse_id=wh_id)
        return qs.none()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        wh_id = request.session.get('selected_warehouse_id')
        if db_field.name == "rack" and wh_id:
            kwargs["queryset"] = Rack.objects.filter(aisle__zone__warehouse_id=wh_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def rack_info(self, obj):
        return f"{obj.rack.aisle.zone.name} - A{obj.rack.aisle.number} - R{obj.rack.number}"
    rack_info.short_description = "Location"


@admin.register(PickingTask)
class PickingTaskAdmin(ImportExportModelAdmin):
    resource_class = PickingTaskResource
    list_display = ("order_id", "item_sku", "quantity_to_pick", "status_badge", "picker_info", "picked_at", "target_inventory_batch")
    list_filter = ("status", "picked_at")
    search_fields = ("order__id", "item_sku", "picker__phone")
    list_select_related = ('order', 'picker', 'target_inventory_batch')
    raw_id_fields = ["order", "picker", "target_inventory_batch"]
    list_per_page = 25
    actions = ["reset_to_pending", "mark_as_completed"]
    readonly_fields = ('picked_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(order__fulfillment_warehouse_id=wh_id)
        return qs.none()

    def order_id(self, obj): return f"#{obj.order.id}"
    order_id.short_description = "Order ID"

    def status_badge(self, obj):
        colors = {'pending': '#ffc107', 'in_progress': '#007bff', 'picked': '#28a745', 'failed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def picker_info(self, obj):
        return f"{obj.picker.user.phone}" if obj.picker else "Unassigned"
    picker_info.short_description = "Picker"

    @admin.action(description="Reset selected tasks to pending")
    def reset_to_pending(self, request, queryset):
        queryset.update(status="pending", picker=None, picked_at=None)

    @admin.action(description="Mark selected tasks as completed")
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status__in=['pending', 'in_progress']).update(status="picked", picked_at=timezone.now())


@admin.register(PackingTask)
class PackingTaskAdmin(ImportExportModelAdmin):
    resource_class = PackingTaskResource
    list_display = ("order_id", "is_completed_badge", "packer_info", "created_at_date")
    list_filter = ("is_completed", "created_at")
    search_fields = ("order__id", "packer__phone")
    list_select_related = ('order', 'packer')
    raw_id_fields = ["order", "packer"]
    list_per_page = 25

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        wh_id = request.session.get('selected_warehouse_id')
        if wh_id: return qs.filter(order__fulfillment_warehouse_id=wh_id)
        return qs.none()

    def order_id(self, obj): return f"#{obj.order.id}"
    order_id.short_description = "Order ID"

    def is_completed_badge(self, obj):
        if obj.is_completed: return format_html('<span style="color: green; font-weight: bold;">✓ Completed</span>')
        return format_html('<span style="color: orange; font-weight: bold;">⏳ Pending</span>')
    is_completed_badge.short_description = "Status"

    def packer_info(self, obj):
        return f"{obj.packer.user.phone}" if obj.packer else "Unassigned"
    packer_info.short_description = "Packer"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"