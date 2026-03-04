from decimal import Decimal
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Sum, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import localtime

# Import Export Magic for Master Admin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

from .models import RiderProfile, RiderDocument, RiderPayout, RiderEarning
from apps.warehouse.models import Warehouse

User = get_user_model()

# ==========================================
# 1. CSV IMPORT / EXPORT RESOURCES
# ==========================================
class RiderProfileResource(resources.ModelResource):
    user = fields.Field(column_name='user_phone', attribute='user', widget=ForeignKeyWidget(User, 'phone'))
    current_warehouse = fields.Field(column_name='warehouse_code', attribute='current_warehouse', widget=ForeignKeyWidget(Warehouse, 'code'))

    class Meta:
        import_id_fields = ('id',)
        model = RiderProfile
        fields = ('id', 'user', 'is_active', 'is_available', 'current_warehouse', 'created_at')

class RiderDocumentResource(resources.ModelResource):
    rider = fields.Field(column_name='rider_phone', attribute='rider', widget=ForeignKeyWidget(RiderProfile, 'user__phone'))
    class Meta:
        model = RiderDocument
        fields = ('id', 'rider', 'doc_type', 'file_key', 'status', 'admin_notes', 'updated_at')

class RiderPayoutResource(resources.ModelResource):
    rider = fields.Field(column_name='rider_phone', attribute='rider', widget=ForeignKeyWidget(RiderProfile, 'user__phone'))
    class Meta:
        model = RiderPayout
        fields = ('id', 'rider', 'amount', 'status', 'transaction_ref', 'created_at', 'completed_at')

class RiderEarningResource(resources.ModelResource):
    rider = fields.Field(column_name='rider_phone', attribute='rider', widget=ForeignKeyWidget(RiderProfile, 'user__phone'))
    payout = fields.Field(column_name='payout_id', attribute='payout', widget=ForeignKeyWidget(RiderPayout, 'id'))
    class Meta:
        model = RiderEarning
        fields = ('id', 'rider', 'amount', 'reference', 'payout', 'created_at')


class RiderDocumentInline(admin.TabularInline):
    model = RiderDocument
    extra = 0
    readonly_fields = ('updated_at',)
    fields = ('doc_type', 'file_key', 'status', 'admin_notes')
    can_delete = False
    show_change_link = False


# ==========================================
# 2. MASTER ADMIN VIEWS (GLOBAL ACCESS)
# ==========================================

@admin.register(RiderProfile)
class RiderProfileAdmin(ImportExportModelAdmin):
    """UPGRADED: Global View for All Riders. No Isolation."""
    resource_class = RiderProfileResource
    
    list_display = (
        'id', 'rider_name', 'phone', 'availability_status', 
        'wallet_balance', 'assigned_warehouse', 'kyc_status', 'created_at_date'
    )
    list_display_links = ('id', 'rider_name', 'phone')
    
    # Master Admin Global Filters
    list_filter = ('current_warehouse', 'is_active', 'is_available', 'created_at')
    search_fields = ('user__phone', 'user__first_name', 'user__last_name')
    list_select_related = ('user', 'current_warehouse')
    raw_id_fields = ('user', 'current_warehouse')
    inlines = [RiderDocumentInline]
    list_per_page = 50
    date_hierarchy = 'created_at'

    actions = ['activate_riders', 'deactivate_riders', 'mark_online', 'mark_offline']

    fieldsets = (
        ('Personal Information', {'fields': ('user', 'is_active')}),
        ('Operational Details', {'fields': ('is_available', 'current_warehouse')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        """Master Admin: Keep the wallet calculations but REMOVE the warehouse isolation!"""
        qs = super().get_queryset(request)

        earnings_sq = RiderEarning.objects.filter(rider=OuterRef('pk')).values('rider').annotate(total=Sum('amount')).values('total')
        payouts_sq = RiderPayout.objects.filter(rider=OuterRef('pk'), status='completed').values('rider').annotate(total=Sum('amount')).values('total')
        
        return qs.annotate(
            annotated_earnings=Coalesce(Subquery(earnings_sq), Decimal('0.00')),
            annotated_payouts=Coalesce(Subquery(payouts_sq), Decimal('0.00'))
        )

    def rider_name(self, obj): return f"{obj.user.first_name} {obj.user.last_name}".strip() or "N/A"
    rider_name.short_description = "Name"

    def phone(self, obj): return format_html('<b>{}</b>', obj.user.phone)
    phone.short_description = "Phone"
    phone.admin_order_field = 'user__phone'

    def availability_status(self, obj):
        if obj.is_available: return format_html('<span style="color: green; font-weight: bold;">● Online</span>')
        return format_html('<span style="color: red; font-weight: bold;">● Offline</span>')
    availability_status.short_description = "Status"
    availability_status.admin_order_field = 'is_available'

    def wallet_balance(self, obj):
        balance = (getattr(obj, 'annotated_earnings', Decimal('0.00'))) - (getattr(obj, 'annotated_payouts', Decimal('0.00')))
        return format_html('<span style="color: #007bff; font-weight: bold;">₹{:.2f}</span>', balance)
    wallet_balance.short_description = "Wallet Balance"

    def assigned_warehouse(self, obj): 
        return obj.current_warehouse.name if obj.current_warehouse else format_html('<span style="color: gray;">Unassigned</span>')
    assigned_warehouse.short_description = "Warehouse"
    assigned_warehouse.admin_order_field = 'current_warehouse__name'

    def kyc_status(self, obj):
        if obj.is_kyc_verified: return format_html('<span style="color: white; background-color: #28a745; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight:bold;">✓ Verified</span>')
        return format_html('<span style="color: white; background-color: #ffc107; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight:bold;">⚠ Pending</span>')
    kyc_status.short_description = "KYC"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: return localtime(obj.created_at).strftime('%d %b %Y')
        return "N/A"
    created_at_date.short_description = "Joined"
    created_at_date.admin_order_field = 'created_at'

    # --- BULK ACTIONS ---
    @admin.action(description="🟢 Activate selected riders")
    def activate_riders(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} riders activated.")

    @admin.action(description="🔴 Deactivate selected riders")
    def deactivate_riders(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} riders deactivated.")

    @admin.action(description="🏍️ Mark selected riders as Online")
    def mark_online(self, request, queryset):
        updated = queryset.update(is_available=True)
        self.message_user(request, f"{updated} riders marked as Online.")

    @admin.action(description="🛑 Mark selected riders as Offline")
    def mark_offline(self, request, queryset):
        updated = queryset.update(is_available=False)
        self.message_user(request, f"{updated} riders marked as Offline.")


@admin.register(RiderPayout)
class RiderPayoutAdmin(ImportExportModelAdmin):
    resource_class = RiderPayoutResource
    list_display = ('id', 'rider_info', 'amount_display', 'status_badge', 'transaction_ref', 'created_at_date', 'completed_at_date')
    
    # Global Filters
    list_filter = ('status', 'rider__current_warehouse', 'created_at', 'completed_at')
    search_fields = ('rider__user__phone', 'transaction_ref')
    list_select_related = ('rider', 'rider__user')
    raw_id_fields = ('rider',)
    list_per_page = 50
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'completed_at')

    actions = ['mark_completed', 'mark_failed']

    def rider_info(self, obj): return f"{obj.rider.user.phone}"
    rider_info.short_description = "Rider Phone"
    rider_info.admin_order_field = 'rider__user__phone'

    def amount_display(self, obj): return format_html('<b style="color: #28a745;">₹{:.2f}</b>', obj.amount)
    amount_display.short_description = "Payout Amount"
    amount_display.admin_order_field = 'amount'

    def status_badge(self, obj):
        colors = {'processing': '#ffc107', 'completed': '#28a745', 'failed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; font-weight:bold;">{}</span>', color, obj.get_status_display().upper())
    status_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: return localtime(obj.created_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    created_at_date.short_description = "Requested On"

    def completed_at_date(self, obj):
        if hasattr(obj, 'completed_at') and obj.completed_at: return localtime(obj.completed_at).strftime('%d %b %Y, %H:%M')
        return "-"
    completed_at_date.short_description = "Completed On"

    # --- BULK ACTIONS ---
    @admin.action(description="✅ Mark selected payouts as Completed")
    def mark_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f"{updated} payouts marked as completed.")

    @admin.action(description="❌ Mark selected payouts as Failed")
    def mark_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f"{updated} payouts marked as failed.")


@admin.register(RiderDocument)
class RiderDocumentAdmin(ImportExportModelAdmin):
    resource_class = RiderDocumentResource
    list_display = ('id', 'rider_phone', 'doc_type', 'status_badge', 'updated_at_date')
    
    # Global Filters
    list_filter = ('status', 'doc_type', 'rider__current_warehouse')
    search_fields = ('rider__user__phone',)
    list_select_related = ('rider', 'rider__user')
    raw_id_fields = ('rider',)
    list_per_page = 50
    
    actions = ['verify_documents', 'reject_documents']

    def rider_phone(self, obj): return obj.rider.user.phone
    rider_phone.short_description = "Rider Phone"
    rider_phone.admin_order_field = 'rider__user__phone'

    def status_badge(self, obj):
        colors = {'pending': '#ffc107', 'verified': '#28a745', 'rejected': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; font-weight:bold;">{}</span>', color, obj.get_status_display().upper())
    status_badge.short_description = "Status"

    def updated_at_date(self, obj):
        if hasattr(obj, 'updated_at') and obj.updated_at: return localtime(obj.updated_at).strftime('%d %b %Y, %H:%M')
        return "N/A"
    updated_at_date.short_description = "Last Updated"

    # --- BULK ACTIONS ---
    @admin.action(description="✅ Verify selected documents")
    def verify_documents(self, request, queryset):
        updated = queryset.update(status='verified')
        self.message_user(request, f"{updated} documents verified successfully.")

    @admin.action(description="❌ Reject selected documents")
    def reject_documents(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f"{updated} documents rejected.")


@admin.register(RiderEarning)
class RiderEarningAdmin(ImportExportModelAdmin):
    resource_class = RiderEarningResource
    list_display = ('id', 'rider_phone', 'amount_display', 'reference', 'payout_link', 'created_at_date')
    
    # Global Filters
    list_filter = ('rider__current_warehouse', 'created_at')
    search_fields = ('rider__user__phone', 'reference')
    list_select_related = ('rider', 'rider__user', 'payout')
    raw_id_fields = ('rider', 'payout', 'order')
    list_per_page = 50
    date_hierarchy = 'created_at'

    def rider_phone(self, obj): return obj.rider.user.phone
    rider_phone.short_description = "Rider Phone"
    rider_phone.admin_order_field = 'rider__user__phone'

    def amount_display(self, obj): return format_html('<span style="color: green; font-weight: bold;">+₹{:.2f}</span>', obj.amount)
    amount_display.short_description = "Amount Earned"
    amount_display.admin_order_field = 'amount'
    
    def payout_link(self, obj):
        if obj.payout:
            from django.urls import reverse
            url = reverse('admin:riders_riderpayout_change', args=[obj.payout.id])
            return format_html('<a href="{}" style="font-weight:bold; color:#007bff;">Payout #{}</a>', url, obj.payout.id)
        return format_html('<span style="color: gray;">Pending Settlement</span>')
    payout_link.short_description = "Settlement Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at: return localtime(obj.created_at).strftime('%d %b %Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Date"
    created_at_date.admin_order_field = 'created_at'