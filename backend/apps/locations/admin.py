from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

# Import Export Magic for Master Admin
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin

from .models import GeoLocation

User = get_user_model()

# ==========================================
# 1. CSV IMPORT / EXPORT RESOURCES
# ==========================================
class GeoLocationResource(resources.ModelResource):
    user_phone = fields.Field(
        column_name='User Phone',
        attribute='user',
        widget=widgets.ForeignKeyWidget(User, 'phone')
    )
    
    class Meta:
        model = GeoLocation
        fields = ('id', 'user_phone', 'label', 'address_text', 'latitude', 'longitude', 'is_active', 'created_at')
        export_order = ('id', 'user_phone', 'label', 'address_text', 'latitude', 'longitude', 'is_active', 'created_at')


# ==========================================
# 2. MASTER ADMIN VIEWS
# ==========================================
@admin.register(GeoLocation)
class GeoLocationAdmin(ImportExportModelAdmin):
    """UPGRADED: Global View for GeoLocations with Map Links"""
    resource_class = GeoLocationResource
    
    list_display = (
        'id',
        'user_phone',
        'label',
        'coordinates_link',
        'address_preview',
        'is_active_badge',
        'created_at_date'
    )
    list_display_links = ('id', 'user_phone')
    list_filter = (
        'is_active',
        'created_at'
    )
    search_fields = (
        'user__phone',
        'user__first_name',
        'label',
        'address_text'
    )
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 50
    
    # Advanced Admin Features
    date_hierarchy = 'created_at'
    actions = ['activate_locations', 'deactivate_locations']

    fieldsets = (
        ('Location Information', {
            'fields': ('user', 'label', 'address_text')
        }),
        ('Geographic Coordinates', {
            'fields': ('latitude', 'longitude')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at',)

    def user_phone(self, obj):
        if obj.user:
            return format_html('<b>{}</b>', obj.user.phone)
        return format_html('<span style="color: gray;">Anonymous</span>')
    user_phone.short_description = "User Phone"
    user_phone.admin_order_field = 'user__phone'

    def coordinates_link(self, obj):
        if obj.latitude and obj.longitude:
            url = f"http://maps.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html(
                '<a href="{}" target="_blank" style="color: #007bff; text-decoration: none; font-weight: bold; background: #e9ecef; padding: 2px 6px; border-radius: 4px;">📍 {}, {}</a>', 
                url, obj.latitude, obj.longitude
            )
        return "-"
    coordinates_link.short_description = "Coordinates (Map)"

    def address_preview(self, obj):
        if not obj.address_text: return "N/A"
        return obj.address_text[:40] + "..." if len(obj.address_text) > 40 else obj.address_text
    address_preview.short_description = "Address"

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Created On"
    created_at_date.admin_order_field = 'created_at'

    # --- BULK ACTIONS ---
    @admin.action(description='🟢 Activate selected locations')
    def activate_locations(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} locations successfully activated.")

    @admin.action(description='🔴 Deactivate selected locations')
    def deactivate_locations(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} locations deactivated.")