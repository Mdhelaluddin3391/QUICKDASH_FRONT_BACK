from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics
from rest_framework.pagination import PageNumberPagination 
from django.conf import settings

from apps.customers.models import CustomerAddress
from apps.inventory.services import InventoryService
from apps.warehouse.services import WarehouseService
from apps.payments.services import PaymentService
from .models import Order, Cart, CartItem
from .services import OrderService
from .serializers import CreateOrderSerializer, CartSerializer, OrderListSerializer, OrderSerializer
from .services import OrderService, OrderSimulationService 

from .serializers import CreateOrderSerializer, CartSerializer, OrderListSerializer, OrderSerializer
from apps.utils.idempotency import idempotent
from apps.accounts.permissions import IsCustomer



class ValidateCartAPIView(APIView):
    """
    Checks if cart items are valid for the CURRENT detected location.
    If the user moved locations, this returns 409 Conflict.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        current_warehouse = request.warehouse

        if not current_warehouse:
            return Response(
                {"error": "Location not serviceable", "code": "LOCATION_INVALID"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = Cart.objects.filter(user=request.user).first()
        if not cart or not cart.items.exists():
            return Response({"valid": True, "warehouse_id": current_warehouse.id})

        if cart.warehouse_id != current_warehouse.id:
            return Response({
                "is_valid": False,
                "error": "Location changed",
                "code": "WAREHOUSE_MISMATCH",
                "message": "Your location changed. Cart contains items from a different store.",
                "action_required": "clear_cart"
            }, status=status.HTTP_409_CONFLICT)

        unavailable_items = []
        for item in cart.items.select_related('sku').all():
           
            if item.sku.available_stock < item.quantity:
                unavailable_items.append({
                    "sku": item.sku.sku,
                    "product_name": item.sku.product_name,
                    "reason": f"Only {item.sku.available_stock} left"
                })

        if unavailable_items:
            return Response({
                "is_valid": False,
                "unavailable_items": unavailable_items
            })

        return Response({"is_valid": True, "warehouse_id": current_warehouse.id})

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class CreateOrderAPIView(APIView):
    """
    Secure Order Creation.
    TRUSTS: Server-side calculated warehouse.
    IGNORES: Client-side warehouse_id.
    """
    permission_classes = [IsCustomer]

    @idempotent(timeout=300)
    @transaction.atomic
    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            address = CustomerAddress.objects.get(id=data['delivery_address_id'], customer__user=request.user)
        except CustomerAddress.DoesNotExist:
            return Response({"error": "Invalid Delivery Address"}, status=400)

        warehouse = WarehouseService.find_nearest_serviceable_warehouse(
            address.latitude, address.longitude
        )

        if not warehouse:
            return Response(
                {"error": "This address is not serviceable."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = get_object_or_404(Cart, user=request.user)
        if not cart.items.exists():
            return Response({"error": "Cart is empty"}, status=400)

        if cart.warehouse_id != warehouse.id:
            return Response(
                {"error": "Cart mismatch. Please refresh cart."}, 
                status=status.HTTP_409_CONFLICT
            )

        items_data = []
        for item in cart.items.select_related('sku').all():
            items_data.append({
                "sku": item.sku.sku,
                "quantity": item.quantity
            })

        try:
            InventoryService.bulk_lock_and_reserve(
                warehouse_id=warehouse.id,
                items_dict={i['sku']: i['quantity'] for i in items_data},
                reference=f"order_init_{request.user.id}"
            )
            
            order = OrderService.create_order_after_reservation(
                user=request.user,
                warehouse_id=warehouse.id, 
                items_data=items_data,
                delivery_type=data['delivery_type'],
                address_id=address.id,
                payment_method=data['payment_method']
            )

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
                "order": {"id": order.id, "status": order.status, "total": order.total_amount},
                "razorpay_order": razorpay_order
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=400)


class MyOrdersAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderListSerializer
    pagination_class = StandardResultsSetPagination 

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by("-created_at")

class OrderDetailAPIView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer
    lookup_field = 'id'
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

class CancelOrderAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        OrderService.cancel_order(order)
        return Response({"status": "order cancelled"})

class CartAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart).data)

class AddToCartAPIView(APIView):
    """
    Adds items to cart, handling warehouse binding.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        sku_code = request.data.get('sku')
        qty = int(request.data.get('quantity', 1))
        warehouse = request.warehouse 
        force_clear = request.data.get('force_clear', False)

        if not warehouse:
            return Response(
                {"error": "Location required to add items."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from apps.inventory.models import InventoryItem
        item_inventory = InventoryItem.objects.filter(
            sku=sku_code,
            bin__rack__aisle__zone__warehouse=warehouse
        ).first()

        if not item_inventory:
            return Response(
                {"error": "Item not available in this store."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        cart, _ = Cart.objects.get_or_create(user=request.user)

        if cart.warehouse and cart.warehouse != warehouse:
            if force_clear:
                cart.items.all().delete()
                cart.warehouse = warehouse
                cart.save()
            else:
                return Response({
                    "error": "Location Mismatch",
                    "code": "warehouse_conflict",
                    "message": "Cart contains items from another store. Clear cart?",
                }, status=status.HTTP_409_CONFLICT)
        
        if not cart.warehouse:
            cart.warehouse = warehouse
            cart.save()

        if qty <= 0:
            CartItem.objects.filter(cart=cart, sku__sku=sku_code).delete()
        else:
            CartItem.objects.update_or_create(
                cart=cart,
                sku=item_inventory,
                defaults={'quantity': qty}
            )

        return Response(CartSerializer(cart).data)

class OrderSimulationAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

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