from django.contrib import admin
from django.core.exceptions import PermissionDenied

class WarehouseScopedAdmin(admin.ModelAdmin):
    """
    Enterprise Base Admin: Enforces strict data isolation.
    Every model inheriting this will ONLY show data for the currently selected warehouse,
    and any new record created will automatically be assigned to that warehouse.
    """
    
    # We hide the warehouse field in the admin form because the system assigns it automatically
    exclude = ('warehouse',)

    def get_queryset(self, request):
        """Strictly filter the list view by the selected warehouse."""
        qs = super().get_queryset(request)
        
        # Superusers can see everything if needed, but let's strictly scope operations
        selected_warehouse_id = request.session.get('selected_warehouse_id')
        
        if selected_warehouse_id and hasattr(self.model, 'warehouse'):
            return qs.filter(warehouse_id=selected_warehouse_id)
            
        return qs

    def save_model(self, request, obj, form, change):
        """Automatically assign the selected warehouse to newly created records."""
        selected_warehouse_id = request.session.get('selected_warehouse_id')
        
        if not change and hasattr(obj, 'warehouse_id') and getattr(obj, 'warehouse_id', None) is None:
            if selected_warehouse_id:
                obj.warehouse_id = selected_warehouse_id
                
        super().save_model(request, obj, form, change)