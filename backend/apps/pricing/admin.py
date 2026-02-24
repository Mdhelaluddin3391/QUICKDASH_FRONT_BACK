# apps/pricing/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from .models import SurgeRule


@admin.register(SurgeRule)
class SurgeRuleAdmin(admin.ModelAdmin):
    list_display = (
        'warehouse_info',
        'max_multiplier_display',
        'base_factor_display',
        'current_surge_status',
        'created_at_date'
    )
    list_filter = ('created_at',)
    search_fields = (
        'warehouse__name',
        'warehouse__code',
        'warehouse__city'
    )
    list_select_related = ('warehouse',)
    raw_id_fields = ('warehouse',)
    list_per_page = 25

    fieldsets = (
        ('Warehouse', {
            'fields': ('warehouse',)
        }),
        ('Surge Configuration', {
            'fields': ('max_multiplier', 'base_factor')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at',)

    def warehouse_info(self, obj):
        return f"{obj.warehouse.name} ({obj.warehouse.code})"
    warehouse_info.short_description = "Warehouse"
    warehouse_info.admin_order_field = 'warehouse__name'

    def max_multiplier_display(self, obj):
        return f"{obj.max_multiplier}x"
    max_multiplier_display.short_description = "Max Multiplier"
    max_multiplier_display.admin_order_field = 'max_multiplier'

    def base_factor_display(self, obj):
        return f"{obj.base_factor:.2f}"
    base_factor_display.short_description = "Base Factor"
    base_factor_display.admin_order_field = 'base_factor'

    def current_surge_status(self, obj):
        # This is a placeholder - in a real implementation, you'd calculate
        # current surge based on demand, time, etc.
        return format_html('<span style="color: green;">Normal (1.0x)</span>')
    current_surge_status.short_description = "Current Surge"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'