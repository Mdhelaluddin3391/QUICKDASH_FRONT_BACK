# apps/payments/serializers.py
from rest_framework import serializers
from .models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "order",
            "amount",
            "status",
            "provider",
            "provider_order_id",
            "provider_payment_id",
            "created_at"
        )
        read_only_fields = fields 