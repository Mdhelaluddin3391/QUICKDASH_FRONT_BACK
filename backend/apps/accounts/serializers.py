# apps/accounts/serializers.py
from rest_framework import serializers
from .models import User, UserRole

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id", 
            "phone", 
            "email", 
            "first_name", 
            "last_name", 
            "is_active", 
            "created_at"
        )
        read_only_fields = ("id", "phone", "is_active", "created_at")


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ("id", "role")


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    uidb64 = serializers.CharField()
    new_password = serializers.CharField(min_length=8)