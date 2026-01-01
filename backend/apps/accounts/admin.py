# apps/accounts/admin.py
from django.contrib import admin
from .models import User, UserRole

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone", "email", "first_name", "last_name", "is_staff", "is_active", "created_at")
    list_filter = ("is_staff", "is_active", "created_at")
    search_fields = ("phone", "email", "first_name")
    ordering = ("-created_at",)

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__phone", "user__email")
    autocomplete_fields = ["user"]