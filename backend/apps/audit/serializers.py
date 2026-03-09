from rest_framework import serializers
from .models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = (
            "id",
            "action",
            "reference_id",
            "user",
            "metadata",
            "created_at",
        )
        read_only_fields = fields