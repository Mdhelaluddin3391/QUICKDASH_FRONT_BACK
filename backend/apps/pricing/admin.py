from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

# Import Export Magic for Master Admin
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin

from .models import SurgeRule
from apps.warehouse.models import Warehouse

# ==========================================
# 1. CSV EXPORT / IMPORT RESOURCES
# ==========================================
class SurgeRuleResource(resources.ModelResource):
    warehouse_code = fields.Field(
        column_name='Warehouse Code',
        attribute='warehouse',
        widget=widgets.ForeignKeyWidget(Warehouse, 'code')
    )
    
    class Meta:
        model = SurgeRule
        fields = ('id', 'warehouse_code', 'max_multiplier', 'base_factor', 'created_at')


# ==========================================
# 2. MASTER ADMIN VIEWS (GLOBAL ACCESS)
# ==========================================
@admin.register(SurgeRule)
class SurgeRuleAdmin(ImportExportModelAdmin):
    """UPGRADED: Global View for All Surge Rules - No Isolation!"""
    resource_class = SurgeRuleResource
    
    list_display = (
        'id',
        'warehouse_info',
        'max_multiplier',  # Direct original field use kiya
        'base_factor',     # Direct original field use kiya
        'current_surge_status',
        'created_at_date'
    )
    list_display_links = ('id', 'warehouse_info')
    
    list_filter = ('created_at', 'warehouse')
    search_fields = (
        'warehouse__name',
        'warehouse__code',
        'warehouse__city'
    )
    list_select_related = ('warehouse',)
    raw_id_fields = ('warehouse',)
    list_per_page = 50
    
    # Ab yeh perfectly kaam karega!
    list_editable = ('max_multiplier', 'base_factor') 
    
    actions = ['reset_to_default']

    fieldsets = (
        ('Warehouse Targeting', {
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

    def current_surge_status(self, obj):
        return format_html('<span style="color: white; background-color: #28a745; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.8em;">Normal (1.0x)</span>')
    current_surge_status.short_description = "Live Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    @admin.action(description='🔄 Reset selected surge rules to Default (2.0x / 0.1)')
    def reset_to_default(self, request, queryset):
        updated = queryset.update(max_multiplier=2.0, base_factor=0.1)
        self.message_user(request, f"Successfully reset {updated} warehouse surge rules to default.")