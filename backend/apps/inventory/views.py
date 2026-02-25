from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from django.shortcuts import get_object_or_404
from .serializers import InventoryTransactionSerializer
from .models import InventoryItem
from .serializers import InventoryItemSerializer
from .services import InventoryService
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from django.shortcuts import get_object_or_404
from .serializers import InventoryTransactionSerializer
from .models import InventoryItem, InventoryTransaction 
from .serializers import InventoryItemSerializer
from .services import InventoryService



class InventoryItemListCreateAPIView(APIView):
    """
    Admin: Manage Warehouse Inventory.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = InventoryItem.objects.select_related(
            "bin__rack__aisle__zone__warehouse"
        ).all()
        
        return Response(InventoryItemSerializer(qs, many=True).data)

    def post(self, request):
        serializer = InventoryItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(InventoryItemSerializer(item).data, status=status.HTTP_201_CREATED)


class AddStockAPIView(APIView):
    """
    Admin: Manual Stock Injection (e.g. GRN).
    """
    permission_classes = [IsAdminUser]

    def post(self, request, item_id):
        item = get_object_or_404(InventoryItem, id=item_id)
        
        try:
            qty = int(request.data.get("quantity", 0))
            if qty <= 0: raise ValueError
        except (ValueError, TypeError):
            return Response({"error": "Positive integer quantity required"}, status=status.HTTP_400_BAD_REQUEST)

        InventoryService.add_stock(item, qty, reference="manual_api_add")
        
        return Response({"status": "stock added", "new_total": item.total_stock})


class CycleCountAPIView(APIView):
    """
    Admin: Stock Correction (e.g. Lost/Found items).
    """
    permission_classes = [IsAdminUser]

    def post(self, request, item_id):
        item = get_object_or_404(InventoryItem, id=item_id)
        
        try:
            new_total = int(request.data.get("new_total"))
            if new_total < 0: raise ValueError
        except (ValueError, TypeError):
             return Response({"error": "Valid new_total required"}, status=status.HTTP_400_BAD_REQUEST)

        InventoryService.cycle_count_adjust(
            item,
            new_total,
            reference=f"cycle_count_admin_{request.user.id}",
        )
        
        return Response({"status": "inventory adjusted"})


class InventoryHistoryAPIView(generics.ListAPIView):
    """
    Admin: Kisi specific Item ki stock movement history dekhne ke liye.
    """
    permission_classes = [IsAdminUser]
    serializer_class = InventoryTransactionSerializer

    def get_queryset(self):
        item_id = self.kwargs.get('item_id')
        return InventoryTransaction.objects.filter(inventory_item_id=item_id).order_by('-created_at')