# apps/warehouse/serializers.py
from rest_framework import serializers
from .models import Warehouse, PickingTask

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = (
            "id",
            "name",
            "code",
            "warehouse_type",
            "city",
            "state",
            "location", # PostGIS Point field serializes to GeoJSON or text usually
            "is_active",
        )


class PickingTaskSerializer(serializers.ModelSerializer):
    bin_location = serializers.CharField(source='target_bin.bin.bin_code', read_only=True)
    
    class Meta:
        model = PickingTask
        fields = (
            "id",
            "order",
            "picker",
            "item_sku",
            "quantity_to_pick",
            "target_bin",
            "bin_location",
            "status",
            "picked_at",
        )