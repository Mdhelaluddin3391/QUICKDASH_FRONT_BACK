# apps/locations/admin.py
from django.contrib import admin
from .models import GeoLocation

@admin.register(GeoLocation)
class GeoLocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "label",
        "latitude",
        "longitude",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("address_text", "user__phone")