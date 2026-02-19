from django.contrib import admin
from .models import StoreSettings

@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = ['is_store_open', 'store_closed_message']
    
    # Ensure admin sirf edit kar paye, naya add na kar paye agar pehle se hai
    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)