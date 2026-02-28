from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin, ImportExportMixin
from .models import User, UserRole, Address

class CustomUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('phone', 'first_name', 'last_name', 'email')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_unusable_password()
        if commit:
            user.save()
        return user


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1
    can_delete = True
    fields = ('role',)
    show_change_link = False


class UserResource(resources.ModelResource):
    class Meta:
        model = User
        import_id_fields = ('phone',)  # Phone ko unique identifier banaya hai
        fields = ('id', 'phone', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'created_at')


class UserRoleResource(resources.ModelResource):
    # ForeignKey linking with phone
    user = fields.Field(
        column_name='user',
        attribute='user',
        widget=widgets.ForeignKeyWidget(User, 'phone')
    )

    class Meta:
        model = UserRole
        fields = ('id', 'user', 'role')


class AddressResource(resources.ModelResource):
    # ForeignKey linking with phone
    user = fields.Field(
        column_name='user',
        attribute='user',
        widget=widgets.ForeignKeyWidget(User, 'phone')
    )

    class Meta:
        model = Address
        fields = ('id', 'user', 'address_type', 'street_address', 'city', 'pincode', 'is_default', 'created_at')


@admin.register(User)
class CustomUserAdmin(ImportExportMixin, UserAdmin):
    resource_class = UserResource
    add_form = CustomUserCreationForm

    list_display = (
        'phone',
        'full_name',
        'user_roles_display',
        'is_active_badge',
        'created_at_date'
    )
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        'created_at'
    )
    search_fields = (
        'phone',
        'email',
        'first_name',
        'last_name'
    )
    list_select_related = ()
    ordering = ('-created_at',)
    list_per_page = 25
    actions = ['activate_users', 'deactivate_users', 'make_staff', 'remove_staff']
    inlines = [UserRoleInline]

    fieldsets = (
        ('Authentication Info', {
            'fields': ('phone',) 
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('last_login', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        ('Authentication Info', {
            'classes': ('wide',),
            'fields': ('phone',) 
        }),
        ('Personal Info', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Permissions', {
            'classes': ('wide',),
            'fields': ('is_active', 'is_staff', 'is_superuser')
        }),
    )

    readonly_fields = ('created_at', 'last_login')

    def full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name or "N/A"
    full_name.short_description = "Name"
    full_name.admin_order_field = 'first_name'

    def user_roles_display(self, obj):
        roles = obj.roles.all()
        if not roles:
            return format_html('<span style="color: orange;">No roles</span>')

        role_names = [role.get_role_display() for role in roles]
        role_text = ", ".join(role_names)

        if 'employee' in [r.role for r in roles]:
            return format_html('<span style="color: blue; font-weight: bold;">{}</span>', role_text)
        elif 'rider' in [r.role for r in roles]:
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', role_text)
        else:
            return format_html('<span style="color: gray;">{}</span>', role_text)
    user_roles_display.short_description = "Roles"

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
    created_at_date.short_description = "Joined"
    created_at_date.admin_order_field = 'created_at'

    @admin.action(description='Activate selected users')
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} users activated.")

    @admin.action(description='Deactivate selected users')
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} users deactivated.")

    @admin.action(description='Make selected users staff')
    def make_staff(self, request, queryset):
        updated = queryset.update(is_staff=True)
        self.message_user(request, f"{updated} users made staff.")

    @admin.action(description='Remove staff status from selected users')
    def remove_staff(self, request, queryset):
        updated = queryset.update(is_staff=False)
        self.message_user(request, f"{updated} users removed from staff.")


@admin.register(UserRole)
class UserRoleAdmin(ImportExportModelAdmin):
    resource_class = UserRoleResource
    list_display = ('user_phone', 'user_name', 'role_badge')
    list_filter = ('role',)
    search_fields = ('user__phone', 'user__first_name', 'user__last_name')
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 25

    def user_phone(self, obj):
        return obj.user.phone
    user_phone.short_description = "Phone"
    user_phone.admin_order_field = 'user__phone'

    def user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or "N/A"
    user_name.short_description = "Name"
    user_name.admin_order_field = 'user__first_name'

    def role_badge(self, obj):
        colors = {
            'customer': '#6c757d',
            'rider': '#28a745',
            'employee': '#007bff',
        }
        color = colors.get(obj.role, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_role_display()
        )
    role_badge.short_description = "Role"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Assigned"
    created_at_date.admin_order_field = 'created_at'


@admin.register(Address)
class AddressAdmin(ImportExportModelAdmin):
    resource_class = AddressResource
    list_display = ('user_phone', 'address_type', 'city', 'pincode', 'is_default_badge', 'created_at_date')
    list_filter = ('address_type', 'city', 'is_default', 'created_at')
    search_fields = ('user__phone', 'street_address', 'city', 'pincode')
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 25
    actions = ['mark_as_default', 'unmark_as_default']

    readonly_fields = ('created_at',)

    def user_phone(self, obj):
        return obj.user.phone
    user_phone.short_description = "User Phone"
    user_phone.admin_order_field = 'user__phone'

    def is_default_badge(self, obj):
        if obj.is_default:
            return format_html('<span style="color: green; font-weight: bold;">✓ Default</span>')
        else:
            return format_html('<span style="color: gray;">-</span>')
    is_default_badge.short_description = "Default"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    @admin.action(description='Mark selected addresses as default')
    def mark_as_default(self, request, queryset):
        updated = queryset.update(is_default=True)
        self.message_user(request, f"{updated} addresses marked as default.")

    @admin.action(description='Unmark selected addresses as default')
    def unmark_as_default(self, request, queryset):
        updated = queryset.update(is_default=False)
        self.message_user(request, f"{updated} addresses unmarked as default.")