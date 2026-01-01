# apps/customers/serializers.py
from rest_framework import serializers
from .models import CustomerProfile, CustomerAddress, SupportTicket

class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            "id",
            "latitude",
            "longitude",
            "house_no",
            "floor_no",
            "apartment_name",
            "landmark",
            "google_address_text",
            "city",
            "pincode",
            "label",
            "receiver_name",
            "receiver_phone",
            "is_default"
        )
        read_only_fields = ("id",)

    def validate(self, data):
        """
        Security & Integrity Checks.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Authentication required")

        # 1. Coordinate Bounds Sanity Check
        lat = data.get('latitude')
        lng = data.get('longitude')
        if lat is not None and lng is not None:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
            except (ValueError, TypeError):
                raise serializers.ValidationError("Invalid coordinates")
            if not (-90 <= lat_f <= 90) or not (-180 <= lng_f <= 180):
                raise serializers.ValidationError("Invalid coordinates")

        # 2. Label Uniqueness (Per User)
        # Prevent user from having 5 addresses named "Home"
        if request.method == 'POST':
            label = data.get('label')
            exists = CustomerAddress.objects.filter(
                customer__user=request.user,
                label__iexact=label, # Case insensitive check
                is_deleted=False
            ).exists()
            
            if exists:
                raise serializers.ValidationError({
                    "label": f"You already have an address named '{label}'. Please use a different name."
                })

        return data


class CustomerProfileSerializer(serializers.ModelSerializer):
    addresses = CustomerAddressSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ("id", "addresses")


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = '__all__'