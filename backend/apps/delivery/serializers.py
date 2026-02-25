from rest_framework import serializers
from .models import Delivery
from apps.orders.serializers import OrderSerializer



class DeliverySerializer(serializers.ModelSerializer):
    """
    Standard serializer for Delivery instances.
    """
    order = OrderSerializer(read_only=True)
    class Meta:
        model = Delivery
        fields = (
            "id",
            "order",
            "rider",
            "status",
            "job_status",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "order")


class DeliveryCompleteSerializer(serializers.Serializer):
    """
    Validates payload for completing a delivery.
    Requires OTP and the S3 Key of the uploaded proof.
    """
    otp = serializers.CharField(max_length=6, min_length=6)
    proof_image_key = serializers.CharField(required=False)

    def validate_proof_image_key(self, value):
        if value and not value.startswith("proofs/order_"):
            raise serializers.ValidationError("Invalid proof image path. Please use the presigned URL flow.")
        return value