from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

from .models import GeoLocation

User = get_user_model()

class GeoLocationResource(resources.ModelResource):
    # Linking user by phone number
    user = fields.Field(
        column_name='user_phone',
        attribute='user',
        widget=ForeignKeyWidget(User, 'phone')
    )

    class Meta:
        model = GeoLocation
        fields = (
            'id', 
            'user', 
            'label', 
            'address_text', 
            'latitude', 
            'longitude', 
            'is_active', 
            'created_at'
        )
        export_order = fields


@admin.register(GeoLocation)
class GeoLocationAdmin(ImportExportModelAdmin):
    resource_class = GeoLocationResource
    
    list_display = (
        'id',
        'user_phone',
        'label',
        'coordinates',
        'address_preview',
        'is_active_badge',
        'created_at_date'
    )
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
    list_per_page = 25
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
        return obj.user.phone if obj.user else "Anonymous"
    user_phone.short_description = "User"
    user_phone.admin_order_field = 'user__phone'

    def coordinates(self, obj):
        return f"{obj.latitude}, {obj.longitude}"
    coordinates.short_description = "Coordinates"

    def address_preview(self, obj):
        return obj.address_text[:50] + "..." if len(obj.address_text) > 50 else obj.address_text
    address_preview.short_description = "Address"

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    @admin.action(description='Activate selected locations')
    def activate_locations(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} locations activated.")

    @admin.action(description='Deactivate selected locations')
    def deactivate_locations(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} locations deactivated.")