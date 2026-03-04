import requests
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import F, Value, CharField, Case, When
from django.db.models.functions import Concat

from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from .models import Product, Category, Brand, Banner, FlashSale

# ==========================================
# 1. CSV IMPORT / EXPORT RESOURCES
# ==========================================

class CategoryResource(resources.ModelResource):
    parent = fields.Field(column_name='parent', attribute='parent', widget=widgets.ForeignKeyWidget(Category, 'slug'))
    class Meta:
        model = Category
        import_id_fields = ('slug',) 
        fields = ('id', 'name', 'slug', 'parent', 'icon', 'is_active', 'sort_order')

class BrandResource(resources.ModelResource):
    class Meta:
        model = Brand
        import_id_fields = ('slug',) 
        fields = ('id', 'name', 'slug', 'logo', 'is_active')

class ProductResource(resources.ModelResource):
    category = fields.Field(column_name='category', attribute='category', widget=widgets.ForeignKeyWidget(Category, 'slug'))
    brand = fields.Field(column_name='brand', attribute='brand', widget=widgets.ForeignKeyWidget(Brand, 'slug'))

    class Meta:
        model = Product
        import_id_fields = ('sku',) 
        fields = (
            'id', 'name', 'sku', 'description', 'unit', 'mrp', 'image', 'is_active', 'category', 'brand',
            'dietary_preference', 'allergens', 'shelf_life', 'nutri_score', 'eco_score', 'search_tags',
            'weight_in_grams', 'packaging_type', 'is_returnable', 'max_order_quantity', 'hsn_code', 'tax_rate'
        )

    def before_import_row(self, row, **kwargs):
        """
        UPGRADED OPEN FOOD FACTS API LOGIC
        CSV mein agar sirf SKU ho, toh baaki saari details API se automatically aa jayengi!
        """
        # 1. ID Clash Protection
        if 'id' in row:
            del row['id']
            
        sku_val = str(row.get('sku', '')).strip()
        name_val = str(row.get('name', '')).strip()
        brand_name = str(row.get('brand', '')).strip()
        category_name = str(row.get('category', '')).strip()

        # Initialize product_data safely so it's always available for Unit fallback
        product_data = {}

        if sku_val:
            try:
                headers = {'User-Agent': 'QuickDashMasterAdmin/2.0'}
                resp = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{sku_val}.json", headers=headers, timeout=5)
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('status') == 1:
                        product_data = data.get('product', {})
                        
                        # 1. Basic Details
                        if not name_val: row['name'] = product_data.get('product_name', '')
                        if not row.get('image'): row['image'] = product_data.get('image_front_url', '')
                        if not row.get('description'): row['description'] = product_data.get('ingredients_text', '')
                        
                        # 2. Auto Categories & Brands
                        if not brand_name and product_data.get('brands'): 
                            brand_name = str(product_data.get('brands')).split(',')[0].strip()
                        if not category_name and product_data.get('categories'): 
                            category_name = str(product_data.get('categories')).split(',')[0].strip()
                        
                        # 3. Health & Packaging (DATABASE CRASH-PROOF FIX APPLIED)
                        if not row.get('allergens'): 
                            row['allergens'] = str(product_data.get('allergens_from_ingredients', '')).replace('en:', '')
                            
                        if not row.get('nutri_score'): 
                            row['nutri_score'] = str(product_data.get('nutriscore_grade', '')).upper()[:5]  # Limits to 5 chars max
                            
                        if not row.get('eco_score'): 
                            row['eco_score'] = str(product_data.get('ecoscore_grade', '')).upper()[:5]      # Limits to 5 chars max
                            
                        if not row.get('packaging_type'): 
                            row['packaging_type'] = str(product_data.get('packaging', ''))
                        
                        # 4. Dietary Check (Veg/Vegan)
                        if not row.get('dietary_preference') or row.get('dietary_preference') == 'NONE':
                            tags = product_data.get('ingredients_analysis_tags', [])
                            if isinstance(tags, list):
                                if 'en:vegan' in tags: row['dietary_preference'] = 'VEGAN'
                                elif 'en:vegetarian' in tags: row['dietary_preference'] = 'VEG'
                                elif 'en:non-vegetarian' in tags: row['dietary_preference'] = 'NON_VEG'

            except Exception as e:
                pass # API fail hone par import nahi rukega, CSV wala data save ho jayega

        # Set Fallbacks
        row['name'] = row.get('name') or name_val or f"Unknown Product (SKU: {sku_val})"
        category_name = category_name or "Uncategorized"

        # Create Category dynamically
        cat_slug = category_name.lower().strip().replace(" ", "-")
        Category.objects.get_or_create(slug=cat_slug, defaults={'name': category_name, 'is_active': True})
        row['category'] = cat_slug 

        # Create Brand dynamically
        if brand_name:
            brand_slug = brand_name.lower().strip().replace(" ", "-")
            Brand.objects.get_or_create(slug=brand_slug, defaults={'name': brand_name, 'is_active': True})
            row['brand'] = brand_slug
        else:
            row['brand'] = None
        
        # 5. Prevent empty MRP crash
        if not row.get('mrp'): 
            row['mrp'] = 0.00
            
        # 6. Auto-fetch Unit safely
        if not row.get('unit'): 
            api_quantity = str(product_data.get('quantity', '')).strip()
            if api_quantity:
                row['unit'] = api_quantity
            else:
                row['unit'] = '1 Unit'


# ==========================================
# 2. MASTER ADMIN VIEWS (Standard Django)
# ==========================================

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    resource_class = ProductResource
    
    # Pure Master Admin View - No Dark Store limitations
    list_display = ('id', 'image_preview', 'name', 'sku', 'mrp', 'dietary_badge', 'category', 'brand', 'is_active')
    list_display_links = ('id', 'name')
    list_filter = ('is_active', 'dietary_preference', 'is_returnable', 'category', 'brand')
    search_fields = ('name', 'sku', 'description', 'search_tags')
    
    # Fast Performance Features
    list_select_related = ('category', 'brand')
    raw_id_fields = ('brand', 'category') 
    
    list_editable = ('mrp', 'is_active')
    list_per_page = 50
    ordering = ['-created_at']
    actions = ['make_active', 'make_inactive']

    fieldsets = (
        ('Basic Details', {'fields': (('name', 'sku'), 'description', ('unit', 'is_active'))}),
        ('Categorization & Search', {'fields': (('category', 'brand'), 'search_tags')}),
        ('Pricing & Tax', {'fields': (('mrp', 'tax_rate'), 'hsn_code')}),
        ('Health & Packaging', {'fields': (('dietary_preference', 'allergens'), ('nutri_score', 'eco_score'), 'shelf_life', 'packaging_type')}),
        ('Logistics', {'fields': (('weight_in_grams', 'max_order_quantity'), 'is_returnable')}),
        ('Media', {'fields': ('image', 'image_preview')}),
    )

    readonly_fields = ('created_at', 'image_preview')

    def dietary_badge(self, obj):
        colors = {'VEG': 'green', 'NON_VEG': 'red', 'VEGAN': '#28a745', 'EGG': '#ffc107', 'NONE': 'gray'}
        color = colors.get(obj.dietary_preference, 'gray')
        return format_html('<span style="color: {}; font-weight: bold;">● {}</span>', color, obj.get_dietary_preference_display())
    dietary_badge.short_description = "Diet"

    def image_preview(self, obj):
        if obj.image: return format_html('<img src="{}" style="height: 40px; border-radius: 4px;" />', obj.image)
        return "-"
    image_preview.short_description = "Image"

    @admin.action(description="Mark selected products as Active")
    def make_active(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Mark selected products as Inactive")
    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    resource_class = CategoryResource
    list_display = ('id', 'name', 'slug', 'parent_name', 'sort_order', 'is_active')
    list_display_links = ('id', 'name')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'slug')
    list_editable = ('is_active', 'sort_order') 
    list_per_page = 50 
    ordering = ['sort_order', 'name']
    prepopulated_fields = {'slug': ('name',)}
    raw_id_fields = ('parent',)

    def parent_name(self, obj):
        return obj.parent.name if obj.parent else format_html('<b style="color:blue;">ROOT</b>')
    parent_name.short_description = "Parent Category"


@admin.register(Brand)
class BrandAdmin(ImportExportModelAdmin):
    resource_class = BrandResource
    list_display = ('id', 'name', 'slug', 'is_active')
    list_display_links = ('id', 'name')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    list_editable = ('is_active',) 
    list_per_page = 50 
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Banner)
class BannerAdmin(ImportExportModelAdmin):
    list_display = ('id', 'title', 'position', 'is_active')
    list_display_links = ('id', 'title')
    list_filter = ('position', 'is_active')
    search_fields = ('title', 'target_url')
    list_editable = ('is_active', 'position')


@admin.register(FlashSale)
class FlashSaleAdmin(ImportExportModelAdmin):
    list_display = ('id', 'product', 'discount_percentage', 'end_time', 'is_active')
    list_display_links = ('id', 'product')
    list_filter = ('is_active', 'end_time')
    search_fields = ('product__name', 'product__sku')
    raw_id_fields = ('product',)
    list_editable = ('is_active', 'discount_percentage')