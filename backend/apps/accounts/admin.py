from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from .models import User, UserRole, Address, UserDevice
# Import Export Magic for Master Admin
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin

from .models import User, UserRole, Address

# ==========================================
# 1. CSV IMPORT / EXPORT RESOURCES
# ==========================================

class UserResource(resources.ModelResource):
    class Meta:
        model = User
        import_id_fields = ('phone',)
        fields = ('id', 'phone', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'created_at')

class AddressResource(resources.ModelResource):
    user_phone = fields.Field(column_name='user_phone', attribute='user', widget=widgets.ForeignKeyWidget(User, 'phone'))
    class Meta:
        model = Address
        fields = ('id', 'user_phone', 'address_type', 'street_address', 'city', 'pincode', 'is_default', 'created_at')


# ==========================================
# 2. MASTER ADMIN VIEWS
# ==========================================

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


@admin.register(User)
class CustomUserAdmin(ImportExportModelAdmin, UserAdmin):
    resource_class = UserResource
    add_form = CustomUserCreationForm

    list_display = (
        'id', 'phone', 'full_name', 'user_roles_display', 'is_active_badge', 'created_at_date'
    )
    list_display_links = ('id', 'phone')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'roles__role')
    search_fields = ('phone', 'email', 'first_name', 'last_name')
    
    ordering = ('-created_at',)
    list_per_page = 50
    
    # Master Admin Actions
    actions = [
        'activate_users', 'deactivate_users', 
        'make_staff', 'remove_staff',
        'assign_rider_role', 'assign_employee_role'
    ]
    inlines = [UserRoleInline]

    fieldsets = (
        ('Authentication Info', {'fields': ('phone', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'created_at'), 'classes': ('collapse',)}),
    )

    readonly_fields = ('created_at', 'last_login')

    def full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name or format_html('<span style="color:gray;">N/A</span>')
    full_name.short_description = "Name"
    full_name.admin_order_field = 'first_name'

    def user_roles_display(self, obj):
        roles = obj.roles.all()
        if not roles:
            return format_html('<span style="color: orange;">Customer</span>') # Default

        role_names = [role.get_role_display() for role in roles]
        role_text = ", ".join(role_names)

        if 'employee' in [r.role for r in roles]:
            return format_html('<span style="color: blue; font-weight: bold;">{}</span>', role_text)
        elif 'rider' in [r.role for r in roles]:
            return format_html('<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 4px; font-size:11px;">{}</span>', role_text)
        return format_html('<span style="color: gray;">{}</span>', role_text)
    user_roles_display.short_description = "Roles"

    def is_active_badge(self, obj):
        if obj.is_active: return format_html('<span style="color: green; font-weight: bold;">● Active</span>')
        return format_html('<span style="color: red; font-weight: bold;">● Inactive</span>')
    is_active_badge.short_description = "Status"

    def created_at_date(self, obj):
        if obj.created_at: return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Joined"
    created_at_date.admin_order_field = 'created_at'

    # --- BULK ACTIONS ---
    @admin.action(description='🟢 Activate selected users')
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='🔴 Deactivate selected users')
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description='⭐ Make selected users Admin Staff')
    def make_staff(self, request, queryset):
        queryset.update(is_staff=True)

    @admin.action(description='❌ Remove Admin Staff status')
    def remove_staff(self, request, queryset):
        queryset.update(is_staff=False, is_superuser=False)

    @admin.action(description='🏍️ Assign RIDER role to selected users')
    def assign_rider_role(self, request, queryset):
        count = 0
        for user in queryset:
            role, created = UserRole.objects.get_or_create(user=user, role='rider')
            if created: count += 1
        self.message_user(request, f"Successfully assigned Rider role to {count} users.")

    @admin.action(description='💼 Assign EMPLOYEE role to selected users')
    def assign_employee_role(self, request, queryset):
        count = 0
        for user in queryset:
            role, created = UserRole.objects.get_or_create(user=user, role='employee')
            if created: count += 1
        self.message_user(request, f"Successfully assigned Employee role to {count} users.")


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_phone', 'user_name', 'role_badge', 'created_at_date')
    list_filter = ('role',)
    search_fields = ('user__phone', 'user__first_name', 'user__last_name')
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 50

    def user_phone(self, obj): return obj.user.phone
    user_phone.short_description = "Phone"

    def user_name(self, obj): return f"{obj.user.first_name} {obj.user.last_name}".strip() or "N/A"
    user_name.short_description = "Name"

    def role_badge(self, obj):
        colors = {'customer': '#6c757d', 'rider': '#28a745', 'employee': '#007bff'}
        color = colors.get(obj.role, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">{}</span>', color, obj.get_role_display().upper())
    role_badge.short_description = "Assigned Role"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: return localtime(obj.created_at).strftime('%d %b %Y')
        return "-"
    created_at_date.short_description = "Assigned On"


@admin.register(Address)
class AddressAdmin(ImportExportModelAdmin):
    resource_class = AddressResource
    list_display = ('id', 'user_phone', 'address_type', 'city', 'pincode', 'is_default_badge')
    list_filter = ('address_type', 'city', 'is_default')
    search_fields = ('user__phone', 'street_address', 'city', 'pincode')
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 50
    actions = ['mark_as_default', 'unmark_as_default']

    readonly_fields = ('created_at',)

    def user_phone(self, obj): return obj.user.phone
    user_phone.short_description = "User Phone"

    def is_default_badge(self, obj):
        if obj.is_default: return format_html('<span style="color: green; font-weight: bold;">⭐ Default</span>')
        return format_html('<span style="color: gray;">-</span>')
    is_default_badge.short_description = "Primary?"

    @admin.action(description='⭐ Mark selected as Default Address')
    def mark_as_default(self, request, queryset):
        queryset.update(is_default=True)

    @admin.action(description='❌ Remove Default Status')
    def unmark_as_default(self, request, queryset):
        queryset.update(is_default=False)

# ==========================================
# 3. USER DEVICE (FCM TOKENS) ADMIN
# ==========================================

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_phone', 'device_type', 'fcm_token_preview', 'created_at_date')
    list_filter = ('device_type', 'created_at')
    search_fields = ('user__phone', 'fcm_token', 'device_type')
    raw_id_fields = ('user',)
    list_select_related = ('user',)
    readonly_fields = ('created_at',)
    list_per_page = 50

    def user_phone(self, obj):
        return obj.user.phone
    user_phone.short_description = "User Phone"
    user_phone.admin_order_field = "user__phone"

    def fcm_token_preview(self, obj):
        # Token bohot lamba hota hai, isliye sirf shuruwat ka hissa dikhayenge
        if obj.fcm_token and len(obj.fcm_token) > 30:
            return f"{obj.fcm_token[:30]}..."
        return obj.fcm_token
    fcm_token_preview.short_description = "FCM Token"

    def created_at_date(self, obj):
        if obj.created_at:
            return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Registered On"
    created_at_date.admin_order_field = "created_at"