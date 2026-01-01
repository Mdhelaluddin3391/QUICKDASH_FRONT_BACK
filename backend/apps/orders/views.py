# apps/orders/views.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.contrib.gis.geos import Point
from apps.customers.models import CustomerAddress
from apps.utils.idempotency import idempotent
from apps.utils.exceptions import BusinessLogicException
from apps.inventory.services import InventoryService
from apps.inventory.models import InventoryItem
from apps.warehouse.models import Warehouse
from apps.payments.services import PaymentService

from .models import Order, Cart, CartItem
from .services import OrderService, OrderSimulationService
from .serializers import (
    OrderSerializer, 
    OrderListSerializer, 
    CreateOrderSerializer, 
    CartSerializer
)



class ValidateCartAPIView(APIView):
    """
    Checks if cart items are available in the warehouse covering the selected location.
    Supports both Saved Address ID (L2) and Raw Lat/Lng (L1).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        address_id = request.data.get('address_id')
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        point = None

        # 1. Resolve Location Point
        if address_id:
            try:
                address = CustomerAddress.objects.get(id=address_id, customer__user=user)
                point = Point(float(address.longitude), float(address.latitude), srid=4326)
            except CustomerAddress.DoesNotExist:
                return Response({"error": "Address not found"}, status=status.HTTP_404_NOT_FOUND)
        elif lat and lng:
            try:
                point = Point(float(lng), float(lat), srid=4326)
            except (ValueError, TypeError):
                return Response({"error": "Invalid Coordinates"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Provide address_id OR lat/lng"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Find Active Warehouse
        target_warehouse = Warehouse.objects.filter(
            delivery_zone__contains=point, 
            is_active=True
        ).first()

        if not target_warehouse:
            return Response({
                "is_valid": False,
                "warehouse_id": None,
                "unavailable_items": [{"product_name": "All Items", "reason": "Not serviceable"}]
            })

        # 3. Check Cart Compatibility
        cart = Cart.objects.filter(user=user).first()
        if not cart or not cart.items.exists():
            return Response({"is_valid": True, "warehouse_id": target_warehouse.id})

        unavailable_items = []
        cart_items = cart.items.select_related('sku').all()

        for item in cart_items:
            sku_code = item.sku.sku
            qty_needed = item.quantity

            # Check inventory in the TARGET warehouse
            local_inventory = InventoryItem.objects.filter(
                sku=sku_code,
                bin__rack__aisle__zone__warehouse=target_warehouse
            ).first()

            if not local_inventory:
                unavailable_items.append({
                    "sku": sku_code,
                    "product_name": item.sku.product_name,
                    "reason": "Not sold at this store"
                })
            elif local_inventory.available_stock < qty_needed:
                unavailable_items.append({
                    "sku": sku_code,
                    "product_name": item.sku.product_name,
                    "reason": f"Only {local_inventory.available_stock} left"
                })

        # 4. Response
        if unavailable_items:
            return Response({
                "is_valid": False,
                "warehouse_id": target_warehouse.id,
                "unavailable_items": unavailable_items
            })

        return Response({
            "is_valid": True, 
            "warehouse_id": target_warehouse.id,
            "message": "All items available"
        })
    



class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CreateOrderAPIView(APIView):
    """
    Transactional Order Creation Endpoint.
    """
    permission_classes = [IsAuthenticated]

    @idempotent(timeout=86400)
    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        user = request.user
        items_data = data.get('items')
        should_clear_cart = False
        
        if not items_data:
            cart = get_object_or_404(Cart, user=user)
            if not cart.items.exists():
                return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)
            
            items_data = []
            for cart_item in cart.items.select_related('sku').all():
                items_data.append({
                    "sku": cart_item.sku.sku,
                    "quantity": cart_item.quantity
                })
            should_clear_cart = True

        warehouse_id = data.get('warehouse_id') 

        try:
            with transaction.atomic():
                InventoryService.bulk_lock_and_reserve(
                    warehouse_id=warehouse_id,
                    items_dict={i['sku']: i['quantity'] for i in items_data},
                    reference=f"order_{user.id}"
                )
                
                order = OrderService.create_order_after_reservation(
                    user=user,
                    warehouse_id=warehouse_id,
                    items_data=items_data,
                    delivery_type=data['delivery_type'],
                    address_id=data['delivery_address_id'],
                    payment_method=data['payment_method']
                )
                
                if data.get('max_accepted_amount'):
                    if order.total_amount > data['max_accepted_amount']:
                        raise BusinessLogicException(
                            "Price changed during checkout. Please review.", 
                            code="price_changed"
                        )

                if should_clear_cart:
                    cart.items.all().delete()

                razorpay_order = None
                if data['payment_method'] == 'RAZORPAY':
                    payment = PaymentService.create_payment(order)
                    razorpay_order = {
                        "id": payment.provider_order_id,
                        "amount": int(payment.amount * 100),
                        "currency": "INR",
                        "key_id": getattr(settings, 'RAZORPAY_KEY_ID', '')
                    }

                return Response({
                    "order": OrderSerializer(order).data,
                    "razorpay_order": razorpay_order
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            raise e


class MyOrdersAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderListSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'payment_method']

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)\
            .select_related("warehouse")\
            .prefetch_related("items")\
            .order_by("-created_at")


class OrderDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)\
            .select_related("warehouse", "delivery", "delivery__rider__user")\
            .prefetch_related("items")


class CancelOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        OrderService.cancel_order(order)
        return Response({"status": "order cancelled"})


class CartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart).data)


class AddToCartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sku_code = request.data.get('sku')
        sku_id = request.data.get('sku_id')
        qty = int(request.data.get('quantity', 1))
        warehouse_id = request.data.get('warehouse_id')
        force_clear = request.data.get('force_clear', False)  # [FIX] New param

        # 1. Resolve Warehouse Context
        if not warehouse_id:
            return Response(
                {"error": "Warehouse Context Missing. Please re-select your location."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Resolve SKU String from ID if needed
        if not sku_code and sku_id:
            try:
                sku_code = InventoryItem.objects.get(id=sku_id).sku
            except InventoryItem.DoesNotExist:
                return Response({"error": "Invalid Item ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not sku_code:
            return Response({"error": "SKU Required"}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Find Correct Inventory Item for this Warehouse
        item_inventory = InventoryItem.objects.filter(
            sku=sku_code,
            bin__rack__aisle__zone__warehouse_id=warehouse_id
        ).order_by('-available_stock').first()

        if not item_inventory:
            return Response(
                {"error": f"Item '{sku_code}' not available in this store."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Get Cart
        cart, _ = Cart.objects.get_or_create(user=request.user)

        # 5. [FIX] Warehouse Consistency Check
        if cart.items.exists():
            # Check the warehouse of the first existing item
            existing_item = cart.items.select_related('sku__bin__rack__aisle__zone__warehouse').first()
            if existing_item and existing_item.sku.warehouse.id != int(warehouse_id):
                if force_clear:
                    cart.items.all().delete()
                else:
                    return Response({
                        "error": "Location Mismatch",
                        "code": "warehouse_conflict",
                        "message": "Your cart has items from a different store. Clear cart to proceed?",
                        "action_required": "clear_cart"
                    }, status=status.HTTP_409_CONFLICT)

        # 6. Update Cart
        if qty <= 0:
            CartItem.objects.filter(cart=cart, sku__sku=sku_code).delete()
            cart.refresh_from_db()
            return Response(CartSerializer(cart).data)

        CartItem.objects.update_or_create(
            cart=cart,
            sku=item_inventory, 
            defaults={'quantity': qty}
        )

        return Response(CartSerializer(cart).data)


class OrderSimulationAPIView(APIView):
    """
    Admin/Dev Only: Force advance order state for testing/demo.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, order_id):
        target_status = request.data.get('status')
        order = get_object_or_404(Order, id=order_id)
        
        try:
            msg = ""
            if target_status == 'packed':
                msg = OrderSimulationService.advance_to_packed(order)
            elif target_status == 'out_for_delivery':
                msg = OrderSimulationService.advance_to_out_for_delivery(order)
            elif target_status == 'delivered':
                msg = OrderSimulationService.advance_to_delivered(order)
            else:
                return Response(
                    {"error": "Invalid target status. Use: packed, out_for_delivery, delivered"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({"status": "success", "message": msg})
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)