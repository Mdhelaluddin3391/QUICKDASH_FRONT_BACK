from django.contrib import admin
from .models import StoreSettings


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ['is_store_open', 'store_closed_message']
    
    # Optional: You can add fieldsets here if your StoreSettings model grows in the future
    fieldsets = (
        ('General Status', {
            'fields': ('is_store_open', 'store_closed_message')
        }),
    )
    
    def has_add_permission(self, request):
        """
        Enterprise Safety: Enforces the Singleton pattern. 
        If a Store Settings record already exists, the 'Add' button will be hidden.
        """
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)