from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime
from leaflet.admin import LeafletGeoAdmin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Warehouse, PickingTask, PackingTask, StorageZone, Aisle, Rack, Bin


class WarehouseResource(resources.ModelResource):
    class Meta:
        model = Warehouse


class PickingTaskResource(resources.ModelResource):
    class Meta:
        model = PickingTask


class PackingTaskResource(resources.ModelResource):
    class Meta:
        model = PackingTask


class StorageZoneResource(resources.ModelResource):
    class Meta:
        model = StorageZone


class AisleResource(resources.ModelResource):
    class Meta:
        model = Aisle


class RackResource(resources.ModelResource):
    class Meta:
        model = Rack


class BinResource(resources.ModelResource):
    class Meta:
        model = Bin


@admin.register(Warehouse)
class WarehouseAdmin(ImportExportModelAdmin, LeafletGeoAdmin):
    resource_class = WarehouseResource
    list_display = (
        'name',
        'code',
        'warehouse_type_display',
        'city',
        'is_active_badge',
        'created_at_date'
    )
    list_filter = (
        'warehouse_type',
        'city',
        'state',
        'is_active',
        'created_at'
    )
    search_fields = (
        'name',
        'code',
        'city',
        'state'
    )
    list_per_page = 25
    actions = ['activate_warehouses', 'deactivate_warehouses']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'warehouse_type', 'is_active')
        }),
        ('Location Details', {
            'fields': ('city', 'state')
        }),
        ('Geographic Data', {
            'fields': ('location', 'delivery_zone'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at',)

    settings_overrides = {
        'DEFAULT_CENTER': (20.5937, 78.9629), 
        'DEFAULT_ZOOM': 5,
    }

    def warehouse_type_display(self, obj):
        type_colors = {
            'dark_store': '#28a745',   
            'mega': '#007bff',         
        }
        color = type_colors.get(obj.warehouse_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_warehouse_type_display()
        )
    warehouse_type_display.short_description = "Type"

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    @admin.action(description='Activate selected warehouses')
    def activate_warehouses(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} warehouses activated.")

    @admin.action(description='Deactivate selected warehouses')
    def deactivate_warehouses(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} warehouses deactivated.")


@admin.register(PickingTask)
class PickingTaskAdmin(ImportExportModelAdmin):
    resource_class = PickingTaskResource
    list_display = ("order_id", "item_sku", "status_badge", "picker_info", "picked_at", "target_bin")
    list_filter = ("status", "picked_at")
    search_fields = ("order__id", "item_sku", "picker__user__phone", "picker__user__first_name")
    list_select_related = ('order', 'picker__user', 'target_bin')
    raw_id_fields = ["order", "picker", "target_bin"]
    list_per_page = 25
    actions = ["reset_to_pending", "mark_as_completed"]

    readonly_fields = ('picked_at',)

    def order_id(self, obj):
        return f"#{obj.order.id}"
    order_id.short_description = "Order ID"
    order_id.admin_order_field = 'order__id'

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'in_progress': '#007bff',
            'completed': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def picker_info(self, obj):
        if obj.picker:
            return f"{obj.picker.user.phone}"
        return "Unassigned"
    picker_info.short_description = "Picker"
    picker_info.admin_order_field = 'picker__user__phone'

    @admin.action(description="Reset selected tasks to pending")
    def reset_to_pending(self, request, queryset):
        updated = queryset.update(status="pending", picker=None, picked_at=None)
        self.message_user(request, f"{updated} tasks reset to pending.")

    @admin.action(description="Mark selected tasks as completed")
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status__in=['pending', 'in_progress']).update(
            status="completed",
            picked_at=timezone.now()
        )
        self.message_user(request, f"{updated} tasks marked as completed.")


@admin.register(PackingTask)
class PackingTaskAdmin(ImportExportModelAdmin):
    resource_class = PackingTaskResource
    list_display = ("order_id", "is_completed_badge", "packer_info", "created_at_date")
    list_filter = ("is_completed", "created_at")
    search_fields = ("order__id", "packer__user__phone", "packer__user__first_name")
    list_select_related = ('order', 'packer__user')
    raw_id_fields = ["order", "packer"]
    list_per_page = 25
    actions = ["mark_completed", "mark_incomplete"]

    readonly_fields = ('created_at',)

    def order_id(self, obj):
        return f"#{obj.order.id}"
    order_id.short_description = "Order ID"
    order_id.admin_order_field = 'order__id'

    def is_completed_badge(self, obj):
        if obj.is_completed:
            return format_html('<span style="color: green; font-weight: bold;">✓ Completed</span>')
        else:
            return format_html('<span style="color: orange; font-weight: bold;">⏳ Pending</span>')
    is_completed_badge.short_description = "Status"

    def packer_info(self, obj):
        if obj.packer:
            return f"{obj.packer.user.phone}"
        return "Unassigned"
    packer_info.short_description = "Packer"
    packer_info.admin_order_field = 'packer__user__phone'

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    @admin.action(description="Mark selected packing tasks as completed")
    def mark_completed(self, request, queryset):
        updated = queryset.update(is_completed=True)
        self.message_user(request, f"{updated} packing tasks marked as completed.")

    @admin.action(description="Mark selected packing tasks as incomplete")
    def mark_incomplete(self, request, queryset):
        updated = queryset.update(is_completed=False)
        self.message_user(request, f"{updated} packing tasks marked as incomplete.")


@admin.register(StorageZone)
class StorageZoneAdmin(ImportExportModelAdmin):
    resource_class = StorageZoneResource
    list_display = ('warehouse_code', 'name')
    list_filter = ('warehouse',)
    search_fields = ('warehouse__name', 'warehouse__code', 'name')
    list_select_related = ('warehouse',)

    def warehouse_code(self, obj):
        return obj.warehouse.code
    warehouse_code.short_description = "Warehouse"
    warehouse_code.admin_order_field = 'warehouse__code'


@admin.register(Aisle)
class AisleAdmin(ImportExportModelAdmin):
    resource_class = AisleResource


@admin.register(Rack)
class RackAdmin(ImportExportModelAdmin):
    resource_class = RackResource


@admin.register(Bin)
class BinAdmin(ImportExportModelAdmin):
    resource_class = BinResource
    list_display = ('bin_code', 'rack', 'capacity_units')
    list_filter = ('rack__aisle__zone__warehouse',)
    search_fields = ('bin_code',)
    list_select_related = ('rack__aisle__zone__warehouse',)

    def rack_info(self, obj):
        return f"{obj.rack.aisle.zone.warehouse.code} - {obj.rack.aisle.zone.name} - A{obj.rack.aisle.aisle_number} - R{obj.rack.rack_number}"
    rack_info.short_description = "Location"