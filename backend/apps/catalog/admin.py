from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from .models import Product, Category, Brand, Banner, FlashSale


class ProductImageInline(admin.TabularInline):
    model = None  # Placeholder - ProductImage model may not exist yet
    extra = 1
    readonly_fields = ('uploaded_at',)
    fields = ('image', 'is_primary', 'alt_text')

    def has_add_permission(self, request, obj=None):
        return False  # Disable until ProductImage model is created

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'sku',
        'category_name',
        'mrp',
        'stock_status',
        'is_active',
        'created_at_date'
    )
    list_filter = (
        'is_active',
        'category',
        'brand',
        'created_at'
    )
    search_fields = (
        'name',
        'sku',
        'description',
        'category__name',
        'brand__name'
    )
    list_select_related = ('category', 'brand')
    raw_id_fields = ('category', 'brand')
    list_editable = ('mrp', 'is_active')
    list_per_page = 25
    actions = ['activate_products', 'deactivate_products', 'mark_featured', 'unmark_featured']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'sku', 'description', 'unit')
        }),
        ('Categorization', {
            'fields': ('category', 'brand')
        }),
        ('Pricing & Inventory', {
            'fields': ('mrp', 'is_active')
        }),
        ('Media', {
            'fields': ('image',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at',)

    def category_name(self, obj):
        return obj.category.name
    category_name.short_description = "Category"
    category_name.admin_order_field = 'category__name'

    def mrp_display(self, obj):
        return f"₹{obj.mrp:.2f}"
    mrp_display.short_description = "MRP"
    mrp_display.admin_order_field = 'mrp'

    def stock_status(self, obj):
        # Calculate total stock from inventory
        from apps.inventory.models import InventoryItem
        total_stock = InventoryItem.objects.filter(sku=obj.sku).aggregate(
            total=Sum('total_stock')
        )['total'] or 0
        if total_stock > 10:
            return format_html('<span style="color: green;">{} in stock</span>', total_stock)
        elif total_stock > 0:
            return format_html('<span style="color: orange;">{} low stock</span>', total_stock)
        else:
            return format_html('<span style="color: red;">Out of stock</span>')
    stock_status.short_description = "Stock Status"

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y')
    created_at_date.short_description = "Created"
    created_at_date.admin_order_field = 'created_at'

    # Admin Actions
    @admin.action(description='Activate selected products')
    def activate_products(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} products activated.")

    @admin.action(description='Deactivate selected products')
    def deactivate_products(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} products deactivated.")

    @admin.action(description='Mark selected products as featured')
    def mark_featured(self, request, queryset):
        # Assuming is_featured field exists
        if hasattr(Product, 'is_featured'):
            updated = queryset.update(is_featured=True)
            self.message_user(request, f"{updated} products marked as featured.")
        else:
            self.message_user(request, "is_featured field not available.")

    @admin.action(description='Unmark selected products as featured')
    def unmark_featured(self, request, queryset):
        if hasattr(Product, 'is_featured'):
            updated = queryset.update(is_featured=False)
            self.message_user(request, f"{updated} products unmarked as featured.")
        else:
            self.message_user(request, "is_featured field not available.")

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_name', 'is_active', 'product_count')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'parent__name')
    list_select_related = ('parent',)
    raw_id_fields = ('parent',)
    list_editable = ('is_active',)
    list_per_page = 25
    actions = ['activate_categories', 'deactivate_categories']

    # FIX: Added 'slug' to fields below
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'parent') 
        }),
        ('Media', {
            'fields': ('icon',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    prepopulated_fields = {'slug': ('name',)}

    def parent_name(self, obj):
        return obj.parent.name if obj.parent else "Root"
    parent_name.short_description = "Parent"
    parent_name.admin_order_field = 'parent__name'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = "Products"

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y') if hasattr(obj, 'created_at') else "N/A"
    created_at_date.short_description = "Created"

    @admin.action(description='Activate selected categories')
    def activate_categories(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} categories activated.")

    @admin.action(description='Deactivate selected categories')
    def deactivate_categories(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} categories deactivated.")

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'product_count')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_editable = ('is_active',)
    list_per_page = 25
    actions = ['activate_brands', 'deactivate_brands']

    # FIX: Added 'slug' to fields below
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug')
        }),
        ('Media', {
            'fields': ('logo',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    prepopulated_fields = {'slug': ('name',)}

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = "Products"

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y') if hasattr(obj, 'created_at') else "N/A"
    created_at_date.short_description = "Created"

    @admin.action(description='Activate selected brands')
    def activate_brands(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} brands activated.")

    @admin.action(description='Deactivate selected brands')
    def deactivate_brands(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} brands deactivated.")

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'is_active')
    list_filter = ('position', 'is_active')
    search_fields = ('title', 'target_url')
    list_editable = ('is_active',)
    list_per_page = 25

    fieldsets = (
        ('Content', {
            'fields': ('title', 'image', 'target_url')
        }),
        ('Display Settings', {
            'fields': ('position', 'bg_gradient', 'is_active')
        }),
    )

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"

    def created_at_date(self, obj):
        return obj.created_at.strftime('%d/%m/%Y') if hasattr(obj, 'created_at') else "N/A"
    created_at_date.short_description = "Created"


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'discount_percentage_display', 'end_time', 'is_active')
    list_filter = ('is_active', 'end_time')
    search_fields = ('product__name', 'product__sku')
    list_select_related = ('product',)
    raw_id_fields = ('product',)
    list_editable = ('is_active',)
    list_per_page = 25

    fieldsets = (
        ('Sale Details', {
            'fields': ('product', 'discount_percentage', 'end_time', 'is_active')
        }),
    )

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = "Product"
    product_name.admin_order_field = 'product__name'

    def discount_percentage_display(self, obj):
        return f"{obj.discount_percentage}% OFF"
    discount_percentage_display.short_description = "Discount"

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">✗ Inactive</span>')
    is_active_badge.short_description = "Status"