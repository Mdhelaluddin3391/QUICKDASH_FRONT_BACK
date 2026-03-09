from rest_framework import serializers
from .models import InventoryItem
from .models import InventoryTransaction

class InventoryItemSerializer(serializers.ModelSerializer):
    available_stock = serializers.IntegerField(read_only=True)

    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)

    class Meta:
        model = InventoryItem
        fields = (
            "id",
            "warehouse", 
            "sku",
            "product_name",
            "price",
            "total_stock",
            "reserved_stock",
            "available_stock",
        )
        read_only_fields = ("id", "available_stock", "reserved_stock")



class InventoryTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryTransaction
        fields = '__all__'