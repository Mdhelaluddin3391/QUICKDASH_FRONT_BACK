# apps/catalog/admin.py
from django.contrib import admin
from .models import Category, Product, Banner, Brand, FlashSale

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    # FIX: Add search_fields required for autocomplete
    search_fields = ("name",)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "mrp", "is_active")
    list_filter = ("is_active", "category")
    search_fields = ("name", "sku")
    autocomplete_fields = ["category"]

@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ('product', 'discount_percentage', 'end_time', 'is_active')
    autocomplete_fields = ['product']

admin.site.register(Banner)
admin.site.register(Brand)