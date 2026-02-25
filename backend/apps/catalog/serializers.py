from rest_framework import serializers
from decimal import Decimal
from .models import Category, Product, Brand, Banner, FlashSale
from apps.inventory.models import InventoryItem


class NavigationCategorySerializer(serializers.ModelSerializer):
    """
    Used for the Navbar. Returns ONLY essential data for parent categories.
    No recursion, no products.
    """
    icon_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "icon_url")

    def get_icon_url(self, obj):
        if not obj.icon:
            return None
        if obj.icon.startswith('http'):
            return obj.icon
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.icon)
        return obj.icon
    

class HomeCategorySerializer(serializers.ModelSerializer):
    """
    Used for 'Shop by Category'. Returns Level-1 categories.
    Includes parent_id for reference if needed.
    """
    icon_url = serializers.SerializerMethodField()
    parent_name = serializers.ReadOnlyField(source='parent.name')

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "icon_url", "parent", "parent_name")

    def get_icon_url(self, obj):
        if not obj.icon:
            return None
        if obj.icon.startswith('http'):
            return obj.icon
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.icon)
        return obj.icon


class ProductSerializer(serializers.ModelSerializer):
    sale_price = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    
    effective_price = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        read_only=True, 
        required=False,
        allow_null=True 
    )

    class Meta:
        model = Product
        fields = (
            "id", "name", "sku", "description", "mrp", 
            "sale_price", "effective_price", "unit", "image_url", "is_active"
        )

    def get_image_url(self, obj):
        if not obj.image:
            return None
        if obj.image.startswith('http'):
            return obj.image
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image)
        return obj.image

    def get_sale_price(self, obj):
        if hasattr(obj, 'effective_price') and obj.effective_price is not None:
            return obj.effective_price
        return obj.mrp

class CategorySerializer(serializers.ModelSerializer):
    """
    Full serializer for Detail Views (optional usage).
    Removed crashing get_descendants logic.
    """
    icon_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "icon_url", "parent")

    def get_icon_url(self, obj):
        if not obj.icon:
            return None
        if obj.icon.startswith('http'):
            return obj.icon
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.icon)
        return obj.icon

class BrandSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Brand
        fields = ('id', 'name', 'slug', 'logo_url')
    
    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        if obj.logo.startswith('http'):
            return obj.logo
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.logo)
        return obj.logo


class BannerSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Banner
        fields = ('id', 'title', 'image_url', 'target_url', 'position', 'bg_gradient')

    def get_image_url(self, obj):
        if not obj.image:
            return None
        if obj.image.startswith('http'):
            return obj.image
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.image)
        return obj.image

class FlashSaleSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='product.sku', read_only=True)
    sku_name = serializers.CharField(source='product.name', read_only=True)
    sku_image = serializers.SerializerMethodField()
    original_price = serializers.DecimalField(source='product.mrp', max_digits=10, decimal_places=2, read_only=True)
    discounted_price = serializers.SerializerMethodField()
    discount_percent = serializers.IntegerField(source='discount_percentage', read_only=True)

    class Meta:
        model = FlashSale
        fields = (
            'id', 'sku', 'sku_name', 'sku_image', 
            'original_price', 'discounted_price', 'discount_percent', 'end_time'
        )

    def get_sku_image(self, obj):
        if not obj.product.image:
            return None
        if obj.product.image.startswith('http'):
            return obj.product.image
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.product.image)
        return obj.product.image

    def get_discounted_price(self, obj):
        mrp = obj.product.mrp
        discount = (mrp * obj.discount_percentage) / 100
        return mrp - discount


class StorefrontProductDocSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    image = serializers.URLField()
    sku = serializers.CharField()
    mrp = serializers.DecimalField(max_digits=10, decimal_places=2)
    selling_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    available_stock = serializers.IntegerField()

class StorefrontCategoryDocSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    products = StorefrontProductDocSerializer(many=True)

class StorefrontResponseDocSerializer(serializers.Serializer):
    serviceable = serializers.BooleanField()
    warehouse_id = serializers.IntegerField()
    categories = StorefrontCategoryDocSerializer(many=True)

class SimpleCategorySerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the 'View All Categories' page.
    Excludes products to ensure fast performance.
    """
    icon_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "icon_url", "parent", "is_active")

    def get_icon_url(self, obj):
        if not hasattr(obj, 'icon') or not obj.icon:
            return None
        if obj.icon.startswith('http'):
            return obj.icon
        return obj.icon