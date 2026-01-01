# apps/inventory/serializers.py
from rest_framework import serializers
from .models import InventoryItem
from .models import InventoryTransaction

class InventoryItemSerializer(serializers.ModelSerializer):
    # Calculated field from model property
    available_stock = serializers.IntegerField(read_only=True)

    # Price is editable to allow warehouse-specific pricing overrides
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)

    class Meta:
        model = InventoryItem
        fields = (
            "id",
            "warehouse", # Read from property/relation
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