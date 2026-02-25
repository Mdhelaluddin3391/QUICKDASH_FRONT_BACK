from rest_framework import serializers
from .models import RiderProfile, RiderEarning
from apps.warehouse.serializers import WarehouseSerializer
from apps.accounts.serializers import UserSerializer
from .models import RiderDocument


class RiderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderProfile
        fields = (
            "id",
            "is_active",
            "is_available",
            "current_warehouse",
            "created_at",
        )

class RiderBootstrapSerializer(serializers.ModelSerializer):
    """
    Rich serializer for App Bootstrap.
    Embeds User info and Warehouse info.
    """
    user = UserSerializer(read_only=True)
    current_warehouse = WarehouseSerializer(read_only=True)

    class Meta:
        model = RiderProfile
        fields = (
            "id",
            "user",
            "is_active",
            "is_available",
            "current_warehouse",
            "created_at",
        )

class RiderEarningSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderEarning
        fields = (
            "id",
            "amount",
            "reference",
            "created_at",
        )

class RiderAvailabilitySerializer(serializers.Serializer):
    is_available = serializers.BooleanField()

class RiderDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderDocument
        fields = ('id', 'doc_type', 'file_key', 'status', 'admin_notes')
        read_only_fields = ('id', 'status', 'admin_notes')