# apps/delivery/admin.py
from django.contrib import admin
from .models import Delivery

@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order", 
        "rider", 
        "status", 
        "job_status",
        "created_at"
    )
    list_filter = ("status", "job_status", "created_at")
    search_fields = ("order__id", "rider__user__phone", "otp")
    autocomplete_fields = ["order", "rider"]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order', 'rider__user')