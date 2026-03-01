from decimal import Decimal
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Sum, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from import_export.admin import ImportExportModelAdmin

from .models import RiderProfile, RiderDocument, RiderPayout, RiderEarning
from apps.warehouse.models import Warehouse

User = get_user_model()

class RiderProfileResource(resources.ModelResource):
    user = fields.Field(
        column_name='user_phone',
        attribute='user',
        widget=ForeignKeyWidget(User, 'phone')
    )
    current_warehouse = fields.Field(
        column_name='warehouse_name',
        attribute='current_warehouse',
        widget=ForeignKeyWidget(Warehouse, 'name')
    )

    class Meta:
        model = RiderProfile
        fields = ('id', 'user', 'is_active', 'is_available', 'current_warehouse', 'created_at')
        export_order = fields

class RiderDocumentResource(resources.ModelResource):
    rider = fields.Field(
        column_name='rider_phone',
        attribute='rider',
        widget=ForeignKeyWidget(RiderProfile, 'user__phone')
    )

    class Meta:
        model = RiderDocument
        fields = ('id', 'rider', 'doc_type', 'file_key', 'status', 'admin_notes', 'updated_at')
        export_order = fields

class RiderPayoutResource(resources.ModelResource):
    rider = fields.Field(
        column_name='rider_phone',
        attribute='rider',
        widget=ForeignKeyWidget(RiderProfile, 'user__phone')
    )

    class Meta:
        model = RiderPayout
        fields = ('id', 'rider', 'amount', 'status', 'transaction_ref', 'created_at', 'completed_at')
        export_order = fields

class RiderEarningResource(resources.ModelResource):
    rider = fields.Field(
        column_name='rider_phone',
        attribute='rider',
        widget=ForeignKeyWidget(RiderProfile, 'user__phone')
    )
    payout = fields.Field(
        column_name='payout_id',
        attribute='payout',
        widget=ForeignKeyWidget(RiderPayout, 'id')
    )

    class Meta:
        model = RiderEarning
        fields = ('id', 'rider', 'amount', 'reference', 'payout', 'created_at')
        export_order = fields

class RiderDocumentInline(admin.TabularInline):
    model = RiderDocument
    extra = 0
    readonly_fields = ('updated_at',)
    fields = ('doc_type', 'file_key', 'status', 'admin_notes')
    can_delete = False
    show_change_link = False

@admin.register(RiderProfile)
class RiderProfileAdmin(ImportExportModelAdmin):
    resource_class = RiderProfileResource
    list_display = ('rider_name', 'phone', 'availability_status', 'wallet_balance', 'assigned_warehouse', 'kyc_status', 'created_at_date')
    list_filter = ('is_active', 'is_available', 'current_warehouse', 'created_at')
    search_fields = ('user__phone', 'user__first_name', 'user__last_name')
    list_select_related = ('user', 'current_warehouse')
    raw_id_fields = ('user', 'current_warehouse')
    inlines = [RiderDocumentInline]
    list_per_page = 25
    actions = ['approve_riders', 'suspend_riders', 'mark_available', 'mark_unavailable']

    fieldsets = (
        ('Personal Information', {'fields': ('user', 'is_active')}),
        ('Operational Details', {'fields': ('is_available', 'current_warehouse')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        earnings_sq = RiderEarning.objects.filter(
            rider=OuterRef('pk')
        ).values('rider').annotate(total=Sum('amount')).values('total')
        
        payouts_sq = RiderPayout.objects.filter(
            rider=OuterRef('pk'), status='completed'
        ).values('rider').annotate(total=Sum('amount')).values('total')
        
        return qs.annotate(
            annotated_earnings=Coalesce(Subquery(earnings_sq), Decimal('0.00')),
            annotated_payouts=Coalesce(Subquery(payouts_sq), Decimal('0.00'))
        )

    def rider_name(self, obj):
        name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return name or "N/A"
    rider_name.short_description = "Name"
    rider_name.admin_order_field = 'user__first_name'

    def phone(self, obj):
        return obj.user.phone
    phone.short_description = "Phone"
    phone.admin_order_field = 'user__phone'

    def availability_status(self, obj):
        if obj.is_available:
            return format_html('<span style="color: green; font-weight: bold;">● Online</span>')
        return format_html('<span style="color: red; font-weight: bold;">● Offline</span>')
    availability_status.short_description = "Status"

    def wallet_balance(self, obj):
        total_earnings = getattr(obj, 'annotated_earnings', 0) or 0
        total_payouts = getattr(obj, 'annotated_payouts', 0) or 0
        balance = total_earnings - total_payouts
        return f"₹{balance:.2f}"
    wallet_balance.short_description = "Wallet Balance"

    def assigned_warehouse(self, obj):
        return obj.current_warehouse.name if obj.current_warehouse else "Unassigned"
    assigned_warehouse.short_description = "Assigned Warehouse"
    assigned_warehouse.admin_order_field = 'current_warehouse__name'

    def kyc_status(self, obj):
        if obj.is_kyc_verified:
            return format_html('<span style="color: green;">✓ Verified</span>')
        return format_html('<span style="color: orange;">⚠ Pending</span>')
    kyc_status.short_description = "KYC Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y')
        return "N/A"
    created_at_date.short_description = "Joined"

@admin.register(RiderPayout)
class RiderPayoutAdmin(ImportExportModelAdmin):
    resource_class = RiderPayoutResource
    list_display = ('rider_info', 'amount_display', 'status_badge', 'created_at_date', 'completed_at')
    list_filter = ('status', 'created_at', 'completed_at')
    search_fields = ('rider__user__phone', 'rider__user__first_name', 'transaction_ref')
    list_select_related = ('rider', 'rider__user')
    raw_id_fields = ('rider',)
    list_per_page = 25

    readonly_fields = ('created_at', 'completed_at')

    def rider_info(self, obj):
        return f"{obj.rider.user.phone} ({obj.rider.user.first_name})"
    rider_info.short_description = "Rider"

    def amount_display(self, obj):
        return f"₹{obj.amount:.2f}"
    amount_display.short_description = "Amount"

    def status_badge(self, obj):
        colors = {'processing': '#ffc107', 'completed': '#28a745', 'failed': '#dc3545'}
        color = colors.get(obj.status, '#6c757d')
        return format_html('<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{}</span>', color, obj.get_status_display())
    status_badge.short_description = "Status"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Created"

@admin.register(RiderDocument)
class RiderDocumentAdmin(ImportExportModelAdmin):
    resource_class = RiderDocumentResource
    list_display = ('id', 'rider_phone', 'doc_type', 'status', 'updated_at')
    list_filter = ('status', 'doc_type')
    search_fields = ('rider__user__phone',)
    list_select_related = ('rider', 'rider__user')
    raw_id_fields = ('rider',)
    list_per_page = 25

    def rider_phone(self, obj):
        return obj.rider.user.phone
    rider_phone.short_description = "Rider Phone"

@admin.register(RiderEarning)
class RiderEarningAdmin(ImportExportModelAdmin):
    resource_class = RiderEarningResource
    list_display = ('id', 'rider_phone', 'amount_display', 'reference', 'created_at_date')
    list_filter = ('created_at',)
    search_fields = ('rider__user__phone', 'reference')
    list_select_related = ('rider', 'rider__user', 'payout')
    raw_id_fields = ('rider', 'payout')
    list_per_page = 25

    def rider_phone(self, obj):
        return obj.rider.user.phone
    rider_phone.short_description = "Rider Phone"

    def amount_display(self, obj):
        return format_html('<span style="color: green; font-weight: bold;">+₹{:.2f}</span>', obj.amount)
    amount_display.short_description = "Amount Earned"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return obj.created_at.strftime('%d/%m/%Y %H:%M')
        return "N/A"
    created_at_date.short_description = "Date"