# apps/customers/admin.py
from django.contrib import admin
from .models import CustomerProfile, CustomerAddress, SupportTicket

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    search_fields = ("user__phone", "user__email")
    autocomplete_fields = ["user"]

@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ("customer", "label", "is_default", "is_deleted", "created_at")
    list_filter = ("is_default", "is_deleted")
    search_fields = ("customer__user__phone", "address_line")

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "issue_type", "status", "created_at")
    list_filter = ("status", "issue_type")
    search_fields = ("user__phone", "order__id")
    autocomplete_fields = ["user", "order"]