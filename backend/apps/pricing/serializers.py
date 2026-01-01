from rest_framework import serializers
from .models import SurgeRule

class SurgeRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurgeRule
        fields = '__all__'