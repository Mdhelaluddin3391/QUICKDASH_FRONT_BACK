# apps/riders/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import RiderProfile, RiderEarning, RiderPayout, RiderDocument

class RiderDocumentInline(admin.TabularInline):
    model = RiderDocument
    extra = 0

@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "is_active",
        "is_available",
        "current_warehouse",
        "created_at",
    )
    list_filter = ("is_active", "is_available", "current_warehouse")
    search_fields = ("user__phone",)
    autocomplete_fields = ["user", "current_warehouse"]
    inlines = [RiderDocumentInline]

@admin.register(RiderEarning)
class RiderEarningAdmin(admin.ModelAdmin):
    list_display = ("rider", "amount", "reference", "payout", "created_at")
    list_filter = ("created_at",)
    search_fields = ("rider__user__phone", "reference")
    readonly_fields = ("rider", "amount", "reference", "created_at")

@admin.register(RiderPayout)
class RiderPayoutAdmin(admin.ModelAdmin):
    list_display = ("id", "rider", "amount", "status", "transaction_ref", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("rider__user__phone", "transaction_ref")
    readonly_fields = ("rider", "amount", "created_at", "completed_at")
    
    actions = ["mark_completed", "mark_failed"]

    @admin.action(description="Mark selected payouts as Completed")
    def mark_completed(self, request, queryset):
        queryset.update(status="completed", completed_at=timezone.now())

    @admin.action(description="Mark selected payouts as Failed")
    def mark_failed(self, request, queryset):
        queryset.update(status="failed")