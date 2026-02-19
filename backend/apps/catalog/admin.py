# apps/catalog/admin.py
import csv
import io
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from .models import Product, Category, Brand, Banner, FlashSale
import requests


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
    change_list_template = "admin/catalog/product/change_list.html"  # ✅ CSV Button ke liye template

    list_display = (
        'name',
        'sku',
        'image_preview',
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
        ('Shop by Store', {  # ✅ Yahan naam change kiya gaya hai
            'fields': ('category', 'brand')
        }),
        ('Pricing & Inventory', {
            'fields': ('mrp', 'is_active')
        }),
        ('Media', {
            'fields': ('image', 'image_preview'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'image_preview')

    # ✅ CSV IMPORT URL ADDING
    def get_urls(self):
        urls = super().get_urls()
        new_urls = [
            path('import-csv/', self.import_csv),
        ]
        return new_urls + urls

    # ✅ CSV IMPORT LOGIC
    # ✅ SMART CSV IMPORT LOGIC
    def import_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            
            if not csv_file.name.endswith('.csv'):
                messages.warning(request, 'The wrong file type was uploaded. Please upload a CSV file.')
                return redirect("..")
            
            file_data = csv_file.read().decode("utf-8")
            csv_data = io.StringIO(file_data)
            
            reader = csv.DictReader(csv_data)
            
            count = 0
            for row in reader:
                sku_val = row.get('sku', '').strip()
                if not sku_val:
                    continue  # Agar sku nahi hai toh wo line skip kardo
                
                # CSV se data nikalna (agar hai toh)
                name_val = row.get('name', '').strip()
                brand_name = row.get('brand', '').strip()
                category_name = row.get('category', '').strip()
                image_val = row.get('image', '').strip()
                desc_val = row.get('description', '').strip()
                mrp_val = row.get('mrp', 0.00)

                # 🔥 API MAGIC: Agar name khali hai, toh OpenFoodFacts API se fetch karo
                if not name_val:
                    api_url = f"https://world.openfoodfacts.org/api/v0/product/{sku_val}.json"
                    try:
                        response = requests.get(api_url, timeout=5)
                        data = response.json()
                        
                        if data.get('status') == 1:
                            product_data = data.get('product', {})
                            
                            name_val = product_data.get('product_name', '')
                            image_val = product_data.get('image_front_url', '')
                            desc_val = product_data.get('ingredients_text', '') 
                            
                            # API se Brand aur Category laao (agar CSV me nahi thi)
                            if not brand_name and product_data.get('brands'):
                                brand_name = product_data.get('brands').split(',')[0].strip()
                                
                            if not category_name and product_data.get('categories'):
                                category_name = product_data.get('categories').split(',')[0].strip()
                    except Exception as e:
                        pass # API down ho toh error throw na kare

                # Agar API se bhi naam nahi mila aur CSV me bhi nahi tha
                if not name_val:
                    name_val = f"Unknown Product (SKU: {sku_val})"

                if not category_name:
                    category_name = "Uncategorized"

                try:
                    # Category dhoondo ya banao
                    category_obj, _ = Category.objects.get_or_create(
                        name=category_name, 
                        defaults={'slug': category_name.lower().replace(" ", "-")}
                    )

                    # Brand dhoondo ya banao
                    brand_obj = None
                    if brand_name:
                        brand_obj, _ = Brand.objects.get_or_create(
                            name=brand_name, 
                            defaults={'slug': brand_name.lower().replace(" ", "-")}
                        )

                    is_active_val = str(row.get('is_active', 'TRUE')).strip().upper() == 'TRUE'

                    # Product Update ya Create karo
                    obj, created = Product.objects.update_or_create(
                        sku=sku_val,
                        defaults={
                            'name': name_val,
                            'description': desc_val,
                            'unit': row.get('unit', '1 Unit'),
                            'image': image_val,
                            'mrp': mrp_val,
                            'is_active': is_active_val,
                            'category': category_obj,
                            'brand': brand_obj,
                        }
                    )
                    count += 1
                except Exception as e:
                    messages.error(request, f"Error in SKU {sku_val}: {e}")
                    continue

            self.message_user(request, f"{count} products imported (Missing data auto-fetched).")
            return redirect("..")
            
        form = {}
        payload = {"form": form}
        return render(request, "admin/csv_form.html", payload)

    # --- Purane Functions ---

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 50px; border-radius: 5px; object-fit: cover;" />', obj.image)
        return format_html('<span style="color: gray;">No Image</span>')
    image_preview.short_description = "Preview"

    def category_name(self, obj):
        return obj.category.name
    category_name.short_description = "Category"
    category_name.admin_order_field = 'category__name'

    def mrp_display(self, obj):
        return f"₹{obj.mrp:.2f}"
    mrp_display.short_description = "MRP"
    mrp_display.admin_order_field = 'mrp'

    def stock_status(self, obj):
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
    list_display = ('name', 'icon_preview', 'parent_name', 'is_active', 'product_count')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'parent__name')
    list_select_related = ('parent',)
    raw_id_fields = ('parent',)
    list_editable = ('is_active',)
    list_per_page = 25
    actions = ['activate_categories', 'deactivate_categories']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'parent') 
        }),
        ('Media', {
            'fields': ('icon', 'icon_preview'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('icon_preview',)

    def icon_preview(self, obj):
        if obj.icon:
            return format_html('<img src="{}" style="max-height: 40px; max-width: 40px; border-radius: 5px; object-fit: cover;" />', obj.icon)
        return "-"
    icon_preview.short_description = "Icon"

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
    list_display = ('name', 'logo_preview', 'is_active', 'product_count')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_editable = ('is_active',)
    list_per_page = 25
    actions = ['activate_brands', 'deactivate_brands']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug')
        }),
        ('Media', {
            'fields': ('logo', 'logo_preview'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('logo_preview',)

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 40px; max-width: 40px; border-radius: 5px; object-fit: cover;" />', obj.logo)
        return "-"
    logo_preview.short_description = "Logo"

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
    list_display = ('title', 'image_preview', 'position', 'is_active')
    list_filter = ('position', 'is_active')
    search_fields = ('title', 'target_url')
    list_editable = ('is_active',)
    list_per_page = 25

    fieldsets = (
        ('Content', {
            'fields': ('title', 'image', 'image_preview', 'target_url')
        }),
        ('Display Settings', {
            'fields': ('position', 'bg_gradient', 'is_active')
        }),
    )

    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 60px; max-width: 120px; border-radius: 5px; object-fit: cover;" />', obj.image)
        return "-"
    image_preview.short_description = "Banner Preview"

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