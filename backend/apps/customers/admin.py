# apps/customers/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import CustomerProfile, CustomerAddress, SupportTicket
from django.db import models
from django.urls import reverse


class CustomerAddressInline(admin.StackedInline):
    model = CustomerAddress
    extra = 0
    classes = ('collapse',) # By default band rahega, click karke open kar sakte hain
    fields = ('label', 'address_summary_view', 'city', 'pincode', 'is_default')
    readonly_fields = ('address_summary_view',)
    can_delete = False

    def address_summary_view(self, obj):
        return f"{obj.house_no}, {obj.apartment_name}, {obj.landmark} - {obj.google_address_text}"
    address_summary_view.short_description = "Full Address"



@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user_phone',
        'user_name',
        'total_orders',
        'total_spent',
        'support_tickets_count',
        'created_at_date'
    )
    list_filter = ('created_at',)
    search_fields = (
        'user__phone',
        'user__first_name',
        'user__last_name',
        'user__email'
    )
    list_select_related = ('user',)
    raw_id_fields = ('user',)
    list_per_page = 25

    # 👇 2. Inlines me Address ko add kar diya 
    inlines = [CustomerAddressInline]

    # 👇 3. Detail View (Profile form) me saari details dikhane ke liye Fieldsets update kiye
    fieldsets = (
        ('👤 Basic User Information', {
            'fields': ('user', 'user_name', 'user_phone', 'user_email')
        }),
        ('🛒 Order & Spends Summary', {
            'fields': ('total_orders', 'total_spent')
        }),
        ('🎧 Support Summary', {
            'fields': ('support_tickets_count',)
        }),
        ('⏱️ Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    # 👇 4. In fields ko readonly bana diya taaki admin yahan se siraf details dekh sake
    readonly_fields = (
        'created_at', 'user_name', 'user_phone', 'user_email',
        'total_orders', 'total_spent', 'support_tickets_count'
    )

    # --- CUSTOM METHODS ---

    def user_phone(self, obj):
        return obj.user.phone
    user_phone.short_description = "Phone"
    user_phone.admin_order_field = 'user__phone'

    def user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or "N/A"
    user_name.short_description = "Full Name"
    user_name.admin_order_field = 'user__first_name'

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Email ID"

    def total_orders(self, obj):
        count = obj.user.orders.count()
        # 👇 Clickable Link banaya hai - ispe click karte hi is customer ke saare orders open ho jayenge
        url = reverse('admin:orders_order_changelist') + f'?user__id__exact={obj.user.id}'
        return format_html('<a href="{}" style="font-weight: bold; color: #007bff;">{} Orders</a>', url, count)
    total_orders.short_description = "Total Orders"

    def total_spent(self, obj):
        total = obj.user.orders.filter(status='delivered').aggregate(
            total=models.Sum('total_amount')
        )['total'] or 0
        return format_html('<span style="color: green; font-weight: bold;">₹{:.2f}</span>', total)
    total_spent.short_description = "Total Spent (Delivered)"

    def support_tickets_count(self, obj):
        count = obj.user.supportticket_set.count()
        # 👇 Clickable Link banaya hai - ispe click karte hi is customer ki saari tickets open ho jayengi
        url = reverse('admin:customers_supportticket_changelist') + f'?user__id__exact={obj.user.id}'
        return format_html('<a href="{}" style="font-weight: bold; color: #dc3545;">{} Tickets</a>', url, count)
    support_tickets_count.short_description = "Support Tickets"

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %I:%M %p')
    created_at_date.short_description = "Joined Date"
    created_at_date.admin_order_field = 'created_at'

@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = (
        'customer_phone',
        'label_badge',
        'address_summary',
        'city_pincode',
        'is_default_badge',
        'is_deleted_badge',
        'created_at_date'
    )
    list_filter = (
        'label',
        'is_default',
        'is_deleted',
        'city',
        'created_at'
    )
    search_fields = (
        'customer__user__phone',
        'house_no',
        'apartment_name',
        'landmark',
        'city',
        'pincode',
        'google_address_text'
    )
    list_select_related = ('customer', 'customer__user')
    raw_id_fields = ('customer',)
    list_per_page = 25
    actions = ['mark_as_default', 'mark_as_deleted', 'restore_addresses']

    fieldsets = (
        ('Customer', {
            'fields': ('customer',)
        }),
        ('Address Details', {
            'fields': ('label', 'house_no', 'floor_no', 'apartment_name', 'landmark', 'city', 'pincode')
        }),
        ('Geographic Data', {
            'fields': ('latitude', 'longitude', 'google_address_text'),
            'classes': ('collapse',)
        }),
        ('Contact & Status', {
            'fields': ('receiver_name', 'receiver_phone', 'is_default', 'is_deleted')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at',)

    def customer_phone(self, obj):
        return obj.customer.user.phone
    customer_phone.short_description = "Customer"
    customer_phone.admin_order_field = 'customer__user__phone'

    def label_badge(self, obj):
        colors = {
            'HOME': '#28a745',
            'WORK': '#007bff',
            'OTHER': '#6c757d',
        }
        color = colors.get(obj.label, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_label_display()
        )
    label_badge.short_description = "Label"

    def address_summary(self, obj):
        return f"{obj.house_no}, {obj.apartment_name or 'N/A'}"
    address_summary.short_description = "Address"

    def city_pincode(self, obj):
        return f"{obj.city} - {obj.pincode}"
    city_pincode.short_description = "City/Pincode"

    def is_default_badge(self, obj):
        if obj.is_default:
            return format_html('<span style="color: green; font-weight: bold;">✓ Default</span>')
        return ""
    is_default_badge.short_description = "Default"

    def is_deleted_badge(self, obj):
        if obj.is_deleted:
            return format_html('<span style="color: red; font-weight: bold;">✗ Deleted</span>')
        return ""
    is_deleted_badge.short_description = "Status"

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %H:%M')
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # Admin Actions
    @admin.action(description='Mark selected addresses as default')
    def mark_as_default(self, request, queryset):
        # Clear other defaults for the same customer
        for address in queryset:
            CustomerAddress.objects.filter(
                customer=address.customer,
                is_default=True
            ).update(is_default=False)
        updated = queryset.update(is_default=True)
        self.message_user(request, f"{updated} addresses marked as default.")

    @admin.action(description='Mark selected addresses as deleted')
    def mark_as_deleted(self, request, queryset):
        updated = queryset.update(is_deleted=True)
        self.message_user(request, f"{updated} addresses marked as deleted.")

    @admin.action(description='Restore selected addresses')
    def restore_addresses(self, request, queryset):
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f"{updated} addresses restored.")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer_phone',
        'order_id',
        'issue_type_badge',
        'status_badge',
        'description_preview',
        'created_at_date'
    )
    list_filter = (
        'issue_type',
        'status',
        'created_at'
    )
    search_fields = (
        'id',
        'user__phone',
        'user__first_name',
        'order__id',
        'description'
    )
    list_select_related = ('user', 'order')
    raw_id_fields = ('user', 'order')
    list_per_page = 25
    actions = ['resolve_tickets', 'reject_tickets', 'reopen_tickets']

    fieldsets = (
        ('Ticket Information', {
            'fields': ('user', 'order', 'issue_type', 'description')
        }),
        ('Resolution', {
            'fields': ('status', 'admin_response')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at',)

    def customer_phone(self, obj):
        return obj.user.phone
    customer_phone.short_description = "Customer"
    customer_phone.admin_order_field = 'user__phone'

    def order_id(self, obj):
        return f"#{obj.order.id}"
    order_id.short_description = "Order ID"
    order_id.admin_order_field = 'order__id'

    def issue_type_badge(self, obj):
        colors = {
            'missing_item': '#dc3545',
            'damaged': '#fd7e14',
            'late': '#ffc107',
            'other': '#6c757d',
        }
        color = colors.get(obj.issue_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_issue_type_display()
        )
    issue_type_badge.short_description = "Issue"

    def status_badge(self, obj):
        colors = {
            'open': '#ffc107',
            'resolved': '#28a745',
            'rejected': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 0.8em;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    def description_preview(self, obj):
        return obj.description[:50] + "..." if len(obj.description) > 50 else obj.description
    description_preview.short_description = "Description"

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y %H:%M')
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # Admin Actions
    @admin.action(description='Resolve selected tickets')
    def resolve_tickets(self, request, queryset):
        updated = queryset.filter(status='open').update(status='resolved')
        self.message_user(request, f"{updated} tickets resolved.")

    @admin.action(description='Reject selected tickets')
    def reject_tickets(self, request, queryset):
        updated = queryset.filter(status='open').update(status='rejected')
        self.message_user(request, f"{updated} tickets rejected.")

    @admin.action(description='Reopen selected tickets')
    def reopen_tickets(self, request, queryset):
        updated = queryset.filter(status__in=['resolved', 'rejected']).update(status='open')
        self.message_user(request, f"{updated} tickets reopened.")