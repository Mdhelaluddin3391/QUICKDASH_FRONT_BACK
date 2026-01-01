# apps/orders/serializers.py
from rest_framework import serializers
from .models import Order, OrderItem, Cart, CartItem
from apps.catalog.models import Product

class CartItemSerializer(serializers.ModelSerializer):
    sku_id = serializers.IntegerField(source='sku.id', read_only=True)
    sku = serializers.CharField(source='sku.sku', read_only=True)  # Added SKU String
    sku_name = serializers.CharField(source='sku.product_name', read_only=True)
    sku_image = serializers.SerializerMethodField()
    sku_unit = serializers.SerializerMethodField()
    unit_price = serializers.DecimalField(source='sku.price', max_digits=10, decimal_places=2, read_only=True)
    warehouse_id = serializers.IntegerField(source='sku.warehouse.id', read_only=True)
    
    class Meta:
        model = CartItem
        fields = (
            'id', 'sku_id', 'sku', 'sku_name', 'sku_image', 
            'sku_unit', 'quantity', 'unit_price', 'total_price', 
            'warehouse_id'
        )

    def get_sku_image(self, obj):
        # Resolve product image from Catalog Product model via SKU code
        product = Product.objects.filter(sku=obj.sku.sku).first()
        if product and product.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(product.image.url)
            return product.image.url
        return None

    def get_sku_unit(self, obj):
        product = Product.objects.filter(sku=obj.sku.sku).first()
        return product.unit if product else "1 Unit"

    def get_total_price(self, obj):
        return obj.unit_price * obj.quantity



class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ('id', 'items', 'total_amount')

class OrderItemSerializer(serializers.ModelSerializer):
    sku_image = serializers.SerializerMethodField()
    sku_name = serializers.CharField(source='product_name', read_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ("sku", "product_name", "sku_name", "quantity", "price", "total_price", "sku_image")

    def get_sku_image(self, obj):
        product = Product.objects.filter(sku=obj.sku).first()
        return product.image.url if (product and product.image) else None

    def get_total_price(self, obj):
        return obj.price * obj.quantity

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    final_amount = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2)
    delivery_lat = serializers.SerializerMethodField()
    delivery_lng = serializers.SerializerMethodField()
    payment_status = serializers.CharField(source='payment.status', read_only=True, default="N/A")
    refund_details = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "delivery_type",
            "final_amount",
            "payment_method",
            "items",
            "created_at",
            "delivery_address_json",
            "delivery_lat",
            "delivery_lng",
            "payment_status",
            "refund_details"
        )

    def get_delivery_lat(self, obj):
        return obj.delivery_address_json.get('lat') 

    def get_delivery_lng(self, obj):
        return obj.delivery_address_json.get('lng')

    def get_refund_details(self, obj):
        if hasattr(obj, 'payment') and hasattr(obj.payment, 'refund'):
            refund = obj.payment.refund
            return {
                "status": refund.status,
                "amount": str(refund.amount),
                "id": refund.provider_refund_id
            }
        return None

class OrderListSerializer(serializers.ModelSerializer):
    final_amount = serializers.DecimalField(source='total_amount', max_digits=10, decimal_places=2)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ("id", "status", "delivery_type", "final_amount", "created_at", "item_count")

    def get_item_count(self, obj):
        return obj.items.count()

class CreateOrderSerializer(serializers.Serializer):
    # [FIX] Removed default=1. Warehouse ID is mandatory for inventory locking.
    warehouse_id = serializers.IntegerField(required=True)
    
    delivery_type = serializers.ChoiceField(choices=["express", "standard"], default="express")
    delivery_address_id = serializers.IntegerField(required=True)
    payment_method = serializers.ChoiceField(choices=["COD", "RAZORPAY"], default="COD")
    items = serializers.ListField(child=serializers.DictField(), required=False, allow_null=True)
    max_accepted_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )