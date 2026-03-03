import requests
from django.contrib import admin
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.db.models import F, Value, CharField, Case, When
from django.db.models.functions import Concat

from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from .models import Product, Category, Brand, Banner, FlashSale

class ProductImageInline(admin.TabularInline):
    model = None  
    extra = 1
    readonly_fields = ('uploaded_at',)
    fields = ('image', 'is_primary', 'alt_text')

    def has_add_permission(self, request, obj=None):
        return False 

    def has_delete_permission(self, request, obj=None):
        return False

class CategoryResource(resources.ModelResource):
    parent = fields.Field(
        column_name='parent',
        attribute='parent',
        widget=widgets.ForeignKeyWidget(Category, 'slug')
    )

    class Meta:
        model = Category
        import_id_fields = ('slug',) 
        fields = ('id', 'name', 'slug', 'parent', 'icon', 'is_active')

class BrandResource(resources.ModelResource):
    class Meta:
        model = Brand
        import_id_fields = ('slug',) 
        fields = ('id', 'name', 'slug', 'logo', 'is_active')

class ProductResource(resources.ModelResource):
    category = fields.Field(
        column_name='category',
        attribute='category',
        widget=widgets.ForeignKeyWidget(Category, 'slug')
    )
    brand = fields.Field(
        column_name='brand',
        attribute='brand',
        widget=widgets.ForeignKeyWidget(Brand, 'slug')
    )

    class Meta:
        model = Product
        import_id_fields = ('sku',) 
        fields = ('id', 'name', 'sku', 'description', 'unit', 'mrp', 'image', 'is_active', 'category', 'brand')

    def before_import_row(self, row, **kwargs):
        """
        SMART IMPORT LOGIC: Naya system jo missing data ko API se fetch karega 
        aur Brand/Category ko auto-create karega bina code tode.
        """
        sku_val = str(row.get('sku', '')).strip()
        name_val = str(row.get('name', '')).strip()
        brand_name = str(row.get('brand', '')).strip()
        category_name = str(row.get('category', '')).strip()

        # 1. API Fallback for missing names
        if sku_val and not name_val:
            try:
                resp = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{sku_val}.json", timeout=3)
                data = resp.json()
                if data.get('status') == 1:
                    product_data = data.get('product', {})
                    name_val = product_data.get('product_name', '')
                    if not row.get('image'): row['image'] = product_data.get('image_front_url', '')
                    if not row.get('description'): row['description'] = product_data.get('ingredients_text', '')
                    if not brand_name and product_data.get('brands'):
                        brand_name = product_data.get('brands').split(',')[0].strip()
                    if not category_name and product_data.get('categories'):
                        category_name = product_data.get('categories').split(',')[0].strip()
            except Exception:
                pass 

        row['name'] = name_val if name_val else f"Unknown Product (SKU: {sku_val})"
        category_name = category_name if category_name else "Uncategorized"

        # 2. Auto-Create Category dynamically
        cat_slug = category_name.lower().strip().replace(" ", "-")
        Category.objects.get_or_create(slug=cat_slug, defaults={'name': category_name, 'is_active': True})
        row['category'] = cat_slug 

        # 3. Auto-Create Brand dynamically
        if brand_name:
            brand_slug = brand_name.lower().strip().replace(" ", "-")
            Brand.objects.get_or_create(slug=brand_slug, defaults={'name': brand_name, 'is_active': True})
            row['brand'] = brand_slug
        else:
            row['brand'] = None
        
        # Ensure numerical safety
        if not row.get('mrp'): row['mrp'] = 0.00
        if not row.get('unit'): row['unit'] = '1 Unit'


class BannerResource(resources.ModelResource):
    class Meta:
        model = Banner
        import_id_fields = ('title',)
        fields = ('id', 'title', 'image', 'target_url', 'position', 'bg_gradient', 'is_active')

class FlashSaleResource(resources.ModelResource):
    product = fields.Field(
        column_name='product',
        attribute='product',
        widget=widgets.ForeignKeyWidget(Product, 'sku')
    )

    class Meta:
        model = FlashSale
        import_id_fields = ('product',) 
        fields = ('id', 'product', 'discount_percentage', 'end_time', 'is_active')

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    resource_class = ProductResource
    
    # Optional: Keep custom templates only if needed for extra buttons, otherwise native is fine
    # change_list_template = "admin/catalog/product/change_list.html"

    list_display = (
        'name', 'sku', 'image_preview', 'category',
        'mrp', 'is_active', 'created_at_date'
    )
    list_filter = ('is_active', 'category', 'brand')
    search_fields = ('name', 'sku', 'description', 'category__name', 'brand__name')
    list_select_related = ('category', 'brand')
    raw_id_fields = ('brand',)
    
    list_editable = ('mrp', 'is_active')
    list_per_page = 25
    actions = ['activate_products', 'deactivate_products']
    
    ordering = ['name']

    # UPGRADED: Professional Section-Based Form Layout
    fieldsets = (
        ('Basic Details', {
            'fields': ('name', 'sku', 'description', 'unit', 'is_active')
        }),
        ('Categorization', {
            'fields': ('category', 'brand')
        }),
        ('Pricing', {
            'fields': ('mrp',)
        }),
        ('Media & Display', {
            'fields': ('image', 'image_preview'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'image_preview')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs["queryset"] = Category.objects.annotate(
                full_display_name=Case(
                    When(parent__isnull=False, then=Concat('parent__name', Value(' > '), 'name')),
                    default=F('name'),
                    output_field=CharField()
                )
            ).order_by('full_display_name')
        elif db_field.name == "brand":
            kwargs["queryset"] = Brand.objects.order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px; border-radius: 5px; object-fit: cover;" />', obj.image)
        return format_html('<span style="color: gray;">No Image</span>')
    image_preview.short_description = "Preview"

    def created_at_date(self, obj):
        if hasattr(obj, 'created_at') and obj.created_at:
            return localtime(obj.created_at).strftime('%d/%m/%Y')
        return "N/A"
    created_at_date.short_description = "Created"


@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    resource_class = CategoryResource
    list_display = ('name', 'icon_preview', 'parent_name', 'view_subcategories', 'sort_order', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'parent__name')
    list_select_related = ('parent',)
    raw_id_fields = ('parent',)
    list_editable = ('is_active', 'sort_order') 
    list_per_page = 100 
    
    ordering = ['sort_order', 'name']

    fieldsets = (
        ('Basic Information', {'fields': ('name', 'slug', 'parent')}),
        ('Media', {'fields': ('icon', 'icon_preview'), 'classes': ('collapse',)}),
        ('Status', {'fields': ('is_active',)}),
    )

    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('icon_preview',)

    def view_subcategories(self, obj):
        count = obj.subcategories.count()
        if count > 0:
            url = f"?parent__id__exact={obj.id}"
            return format_html('<a class="button" href="{}" style="padding: 3px 10px; background: #417690; color: white; border-radius: 4px;">📂 View {} Subcategories</a>', url, count)
        return format_html('<span style="color: gray;">-</span>')
    view_subcategories.short_description = "Subcategories"

    def icon_preview(self, obj):
        if obj.icon:
            return format_html('<img src="{}" style="max-height: 40px; max-width: 40px; border-radius: 5px; object-fit: cover;" />', obj.icon)
        return "-"
    icon_preview.short_description = "Icon"

    def parent_name(self, obj):
        return obj.parent.name if obj.parent else "Root"
    parent_name.short_description = "Parent"


@admin.register(Brand)
class BrandAdmin(ImportExportModelAdmin):
    resource_class = BrandResource
    list_display = ('name', 'logo_preview', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_editable = ('is_active',) 
    list_per_page = 100 
    ordering = ['name']

    fieldsets = (
        ('Basic Information', {'fields': ('name', 'slug')}),
        ('Media', {'fields': ('logo', 'logo_preview'), 'classes': ('collapse',)}),
        ('Status', {'fields': ('is_active',)}),
    )

    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('logo_preview',)

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 40px; max-width: 40px; border-radius: 5px; object-fit: cover;" />', obj.logo)
        return "-"
    logo_preview.short_description = "Logo"


@admin.register(Banner)
class BannerAdmin(ImportExportModelAdmin):
    resource_class = BannerResource
    list_display = ('title', 'image_preview', 'position', 'is_active')
    list_filter = ('position', 'is_active')
    search_fields = ('title', 'target_url')
    list_editable = ('is_active',)
    list_per_page = 25

    fieldsets = (
        ('Content', {'fields': ('title', 'image', 'image_preview', 'target_url')}),
        ('Display Settings', {'fields': ('position', 'bg_gradient', 'is_active')}),
    )
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 60px; max-width: 120px; border-radius: 5px; object-fit: cover;" />', obj.image)
        return "-"
    image_preview.short_description = "Preview"

@admin.register(FlashSale)
class FlashSaleAdmin(ImportExportModelAdmin):
    resource_class = FlashSaleResource
    list_display = ('product_name', 'discount_percentage_display', 'end_time', 'is_active')
    list_filter = ('is_active', 'end_time')
    search_fields = ('product__name', 'product__sku')
    list_select_related = ('product',)
    raw_id_fields = ('product',)
    list_editable = ('is_active',)
    list_per_page = 25

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = "Product"

    def discount_percentage_display(self, obj):
        return f"{obj.discount_percentage}% OFF"
    discount_percentage_display.short_description = "Discount"