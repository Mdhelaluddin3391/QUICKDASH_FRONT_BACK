# apps/locations/serializers.py
from rest_framework import serializers
from .models import GeoLocation

class GeoLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoLocation
        fields = (
            "id",
            "label",
            "address_text",
            "latitude",
            "longitude",
        )