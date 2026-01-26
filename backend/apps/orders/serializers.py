# apps/orders/serializers.py
from rest_framework import serializers
from .models import Order, OrderItem, Cart, CartItem
from apps.catalog.models import Product
from rest_framework import serializers
from .models import Order, OrderItem, Cart, CartItem
from apps.catalog.models import Product
from rest_framework import serializers
from .models import Order
# apps/orders/serializers.py
from rest_framework import serializers
from .models import Order, OrderItem, Cart, CartItem
from apps.catalog.models import Product
from rest_framework import serializers
from .models import Order, OrderItem, Cart, CartItem
from apps.catalog.models import Product



class CartItemSerializer(serializers.ModelSerializer):
    sku_code = serializers.CharField(source='sku.sku', read_only=True)
    product_name = serializers.CharField(source='sku.product_name', read_only=True)
    price = serializers.DecimalField(source='sku.price', max_digits=10, decimal_places=2, read_only=True)
    image = serializers.SerializerMethodField()
    sku_name = serializers.CharField(source='sku.product_name', read_only=True)

    class Meta:
        model = CartItem
        fields = ('id', 'sku_code', 'sku_name','product_name', 'quantity', 'price', 'total_price', 'image')

    def get_image(self, obj):
        # Resolve via SKU string from Catalog
        p = Product.objects.filter(sku=obj.sku.sku).first()
        if p and p.image:
            return p.image.url
        return None

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Cart
        fields = ('id', 'items', 'total_amount', 'warehouse')

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

    delivery_otp = serializers.SerializerMethodField()


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
            "refund_details",
            "delivery_otp"
        )

    def get_delivery_otp(self, obj):
        # Sirf tab dikhaye jab Delivery assign ho chuki ho
        if hasattr(obj, 'delivery') and obj.delivery:
            return obj.delivery.otp
        return None

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
    # ✅ यहाँ PAYMENT_METHOD_CHOICES का सही इस्तेमाल किया गया है
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_METHOD_CHOICES, default="COD")
    
    # Address ID required for delivery validation
    delivery_address_id = serializers.IntegerField(required=True)
    
    # total_amount validation
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2) 
    
    delivery_type = serializers.ChoiceField(choices=Order.DELIVERY_TYPE_CHOICES, default="express")
    
    # Optional Items (if not using Cart)
    items = serializers.ListField(child=serializers.DictField(), required=False, allow_null=True)
    
    max_accepted_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )