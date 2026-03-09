from rest_framework import serializers
from .models import CustomerProfile, CustomerAddress, SupportTicket
from rest_framework import serializers
from .models import CustomerAddress




class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            'id', 'label', 'house_no', 'floor_no', 'apartment_name', 
            'landmark', 'city', 'pincode', 
            'latitude', 'longitude', 'is_default', 'google_address_text',
            'receiver_name', 'receiver_phone'
        )
        read_only_fields = ('id',)

    def validate(self, data):
        """
        STRICT GEO-VALIDATION
        We cannot allow an address to be saved without coordinates, 
        as this would bypass the Serviceability Checks during checkout.
        """
        lat = data.get('latitude')
        lng = data.get('longitude')

        if not lat or not lng:
            raise serializers.ValidationError(
                "Precise location is required. Please select your location on the map."
            )

        try:
            if not (-90 <= float(lat) <= 90) or not (-180 <= float(lng) <= 180):
                raise serializers.ValidationError("Invalid coordinates.")
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid coordinate format.")

        return data

    def update(self, instance, validated_data):
        """
        PREVENT COORDINATE DRIFT
        If a user wants to change the location pin, they should create a new address.
        Editing coordinates of an existing address causes order history inconsistencies.
        """
        if 'latitude' in validated_data or 'longitude' in validated_data:
            old_lat = float(instance.latitude)
            new_lat = float(validated_data.get('latitude', old_lat))
            
            if abs(old_lat - new_lat) > 0.0001: 
                raise serializers.ValidationError(
                    "You cannot move the pin of a saved address. Please delete and create a new one."
                )
        
        return super().update(instance, validated_data)


class CustomerProfileSerializer(serializers.ModelSerializer):
    addresses = CustomerAddressSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerProfile
        fields = ("id", "addresses")


class SupportTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = '__all__'