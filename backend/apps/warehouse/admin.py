# apps/warehouse/admin.py
from django.contrib import admin
from .models import Warehouse, PickingTask, PackingTask, StorageZone, Aisle, Rack, Bin

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "warehouse_type", "city", "is_active")
    list_filter = ("warehouse_type", "city", "is_active")
    search_fields = ("name", "code")

@admin.register(PickingTask)
class PickingTaskAdmin(admin.ModelAdmin):
    list_display = ("order", "item_sku", "status", "picker", "picked_at")
    list_filter = ("status", "picked_at")
    search_fields = ("order__id", "item_sku", "picker__phone")
    autocomplete_fields = ["order", "picker", "target_bin"]
    
    actions = ["reset_to_pending"]

    @admin.action(description="Reset task to pending")
    def reset_to_pending(self, request, queryset):
        queryset.update(status="pending", picker=None)

@admin.register(PackingTask)
class PackingTaskAdmin(admin.ModelAdmin):
    list_display = ("order", "is_completed", "packer", "created_at")
    list_filter = ("is_completed",)
    autocomplete_fields = ["order", "packer"]

# Physical Layout
admin.site.register(StorageZone)
admin.site.register(Aisle)
admin.site.register(Rack)
@admin.register(Bin)
class BinAdmin(admin.ModelAdmin):
    list_display = ("bin_code", "rack", "capacity_units")
    search_fields = ("bin_code",)