# apps/warehouse/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Bin, Rack
from .models import Warehouse, PickingTask
from .serializers import WarehouseSerializer
from .services import WarehouseService, WarehouseOperationsService
from apps.orders.models import Order
from apps.delivery.services import DeliveryService
from apps.accounts.permissions import IsWarehouseManager # Assuming this exists or using IsAdminUser

class WarehouseListCreateAPIView(APIView):
    """
    Admin: List all or create new warehouse.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = Warehouse.objects.all()
        return Response(WarehouseSerializer(qs, many=True).data)

    def post(self, request):
        serializer = WarehouseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        warehouse = serializer.save()
        return Response(WarehouseSerializer(warehouse).data, status=status.HTTP_201_CREATED)


class ServiceableWarehouseAPIView(APIView):
    """
    Public: Find warehouse covering a specific location.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        lat = request.data.get("latitude")
        lon = request.data.get("longitude")
        city = request.data.get("city") # अगर नहीं आया तो यह None होगा, जो सही है।

        # 1. Validation: सिर्फ Lat/Long चेक करें (City की चिंता न करें)
        if not lat or not lon:
            return Response({"error": "Latitude and Longitude are required"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Call Service directly
        # अगर city None है, तो सर्विस कोड उसे इग्नोर कर देगा और सिर्फ Lat/Long से ढूंढेगा।
        warehouse = WarehouseService.find_nearest_serviceable_warehouse(lat, lon, city)

        if not warehouse:
            return Response(
                {"serviceable": False, "message": "Not available in this area"},
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "serviceable": True,
                "warehouse": WarehouseSerializer(warehouse).data,
            },
            status=status.HTTP_200_OK
        )


class PickerTaskListView(APIView):
    """
    Picker App: Get pending tasks for the picker's current warehouse.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Identify Context
        if not hasattr(request.user, 'rider_profile') or not request.user.rider_profile.current_warehouse:
            # Assuming Pickers are modeled similar to Riders or have an EmployeeProfile.
            # Adjust based on exact auth model. For now, checking rider_profile/warehouse linkage.
            return Response(
                {"error": "User not linked to a warehouse."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        warehouse = request.user.rider_profile.current_warehouse

        # 2. Optimized Query
        tasks = PickingTask.objects.filter(
            status="pending",
            target_bin__bin__rack__aisle__zone__warehouse=warehouse
        ).select_related(
            "target_bin__bin"
        ).order_by(
            'target_bin__bin__rack__aisle__number', 
            'target_bin__bin__bin_code'
        )
        
        data = [
            {
                "task_id": t.id,
                "order_id": t.order_id,
                "sku": t.item_sku,
                "qty": t.quantity_to_pick,
                "bin_location": t.target_bin.bin.bin_code,
                "status": t.status
            }
            for t in tasks
        ]
        return Response(data)


class ScanPickAPIView(APIView):
    """
    Picker App: Scan Bin & Product to pick item.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get("task_id")
        scanned_bin = request.data.get("scanned_bin_code")
        scanned_sku = request.data.get("scanned_sku")

        if not all([task_id, scanned_bin, scanned_sku]):
            return Response({"error": "Scan data missing"}, status=status.HTTP_400_BAD_REQUEST)

        # Delegate to Service
        message = WarehouseOperationsService.scan_pick(
            task_id=task_id,
            picker_user=request.user,
            scanned_bin_code=scanned_bin,
            scanned_barcode=scanned_sku
        )
        
        return Response({"status": "success", "message": message})


class PackingCompleteAPIView(APIView):
    """
    Packer App: Mark order as packed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        packing_task_id = request.data.get("packing_task_id")
        
        WarehouseOperationsService.complete_packing(
            packing_task_id=packing_task_id,
            user=request.user
        )
        
        return Response({"status": "order_ready_for_dispatch"})


class InwardStockAPIView(APIView):
    """
    Manager App: Add stock to a bin.
    """
    permission_classes = [IsAuthenticated] # Should ideally be IsWarehouseManager

    def post(self, request):
        barcode = request.data.get("barcode")
        bin_code = request.data.get("bin_code")
        raw_quantity = request.data.get("quantity")
        warehouse_id = request.data.get("warehouse_id")

        if not all([barcode, bin_code, raw_quantity, warehouse_id]):
            return Response({"error": "Missing data"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quantity = int(raw_quantity)
            if quantity <= 0: raise ValueError
        except (ValueError, TypeError):
             return Response({"error": "Positive integer quantity required"}, status=status.HTTP_400_BAD_REQUEST)

        result = WarehouseOperationsService.inward_stock_putaway(
            warehouse_id=warehouse_id,
            barcode=barcode,
            quantity=quantity,
            bin_code=bin_code,
            user=request.user
        )
        
        return Response(result)


class PickerActiveOrdersAPIView(APIView):
    """
    Picker App: View orders ready for handover.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Determine Warehouse
        warehouse = None
        if hasattr(request.user, 'rider_profile') and request.user.rider_profile.current_warehouse:
             warehouse = request.user.rider_profile.current_warehouse
        
        if not warehouse:
             return Response({"error": "No warehouse context"}, status=status.HTTP_403_FORBIDDEN)

        packed_orders = WarehouseOperationsService.get_active_handover_orders(warehouse)
        
        return Response({
            "message": "Handover pending",
            "orders": packed_orders
        })


class OrderDispatchPlacementAPIView(APIView):
    """
    Picker App: Place packed order in dispatch bin.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        dispatch_bin_code = request.data.get("dispatch_bin_code")

        result = DeliveryService.place_in_dispatch_bin(
            order_id=order_id,
            dispatch_bin_code=dispatch_bin_code,
            picker_user=request.user
        )
        return Response(result)


class WarehouseManagerStatsAPIView(APIView):
    """
    Dashboard: Stats for Warehouse Manager.
    """
    permission_classes = [IsAuthenticated] # Should be IsWarehouseManager

    def get(self, request):
        warehouse_id = request.query_params.get("warehouse_id")
        if not warehouse_id:
             return Response({"error": "warehouse_id required"}, status=status.HTTP_400_BAD_REQUEST)
             
        # Basic Counts
        pending_picks = PickingTask.objects.filter(
            order__warehouse_id=warehouse_id, status="pending"
        ).count()
        
        pending_orders = Order.objects.filter(
            warehouse_id=warehouse_id, status="confirmed"
        ).count()
        
        return Response({
            "pending_picks": pending_picks,
            "pending_orders": pending_orders,
        })


class BinListCreateAPIView(APIView):
    """
    Manager: List or Create Bins dynamically.
    """
    permission_classes = [IsAuthenticated] # Should be IsWarehouseManager

    def get(self, request):
        # Filter by warehouse if needed, for now listing all
        bins = Bin.objects.select_related('rack__aisle__zone').all()[:100]
        data = [{"id": b.id, "code": b.bin_code, "capacity": b.capacity_units} for b in bins]
        return Response(data)

    def post(self, request):
        # Simple Bin Creation
        rack_id = request.data.get("rack_id")
        code = request.data.get("bin_code")
        
        rack = get_object_or_404(Rack, id=rack_id)
        bin_obj = Bin.objects.create(rack=rack, bin_code=code)
        
        return Response({"id": bin_obj.id, "code": bin_obj.bin_code}, status=201)