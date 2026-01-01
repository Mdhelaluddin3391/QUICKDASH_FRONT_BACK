# apps/inventory/admin.py
from django.contrib import admin
from .models import InventoryItem, InventoryTransaction
from apps.audit.services import AuditService

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "product_name",
        "warehouse_code", # Custom method
        "total_stock",
        "reserved_stock",
        "available_stock",
        "price"
    )
    search_fields = ("sku", "product_name")
    list_filter = ("mode", "bin__rack__aisle__zone__warehouse")
    autocomplete_fields = ["bin"]
    
    def warehouse_code(self, obj):
        return obj.warehouse.code
    warehouse_code.short_description = "Warehouse"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "bin__rack__aisle__zone__warehouse"
        )

    # Audit Admin actions
    def save_model(self, request, obj, form, change):
        if change:
            old_obj = InventoryItem.objects.get(pk=obj.pk)
            changes = {}
            if old_obj.total_stock != obj.total_stock:
                changes['total_stock'] = {'old': old_obj.total_stock, 'new': obj.total_stock}
            
            if changes:
                AuditService.log(
                    action="admin_inventory_update",
                    reference_id=str(obj.id),
                    user=request.user,
                    metadata={
                        "sku": obj.sku,
                        "changes": changes,
                        "reason": "Manual Admin Update"
                    }
                )
        super().save_model(request, obj, form, change)

@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "inventory_item",
        "transaction_type",
        "quantity",
        "reference",
        "created_at",
    )
    list_filter = ("transaction_type", "created_at")
    search_fields = ("inventory_item__sku", "reference")
    readonly_fields = ("inventory_item", "transaction_type", "quantity", "reference", "created_at")
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("inventory_item")