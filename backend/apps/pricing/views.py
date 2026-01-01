from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from .models import SurgeRule
from .serializers import SurgeRuleSerializer # Hame serializer bhi chahiye hoga

class SurgeRuleListCreateAPIView(generics.ListCreateAPIView):
    """
    Admin: Warehouse wise surge rules set karne ke liye.
    """
    permission_classes = [IsAdminUser]
    queryset = SurgeRule.objects.all()
    serializer_class = SurgeRuleSerializer

class SurgeRuleDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    queryset = SurgeRule.objects.all()
    serializer_class = SurgeRuleSerializer