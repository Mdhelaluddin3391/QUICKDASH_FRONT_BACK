# apps/audit/admin.py
from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "reference_id", "user", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("reference_id", "user__phone")
    
    # Completely Read-Only
    def has_add_permission(self, request):
        return False
        
    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False