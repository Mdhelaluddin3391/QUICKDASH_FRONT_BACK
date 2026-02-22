import logging
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.inventory.services import InventoryService
from apps.pricing.services import SurgePricingService
from apps.audit.services import AuditService
from apps.customers.models import CustomerAddress
from apps.warehouse.models import Warehouse, PickingTask, PackingTask
from apps.warehouse.services import WarehouseOperationsService
from apps.delivery.services import DeliveryService
from apps.delivery.models import Delivery
from apps.riders.models import RiderProfile
from apps.utils.exceptions import BusinessLogicException
from .models import Order, OrderItem
from .abuse_services import OrderAbuseService

logger = logging.getLogger(__name__)
User = get_user_model()

class OrderService:

    @staticmethod
    def _broadcast_status(order):
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"order_{order.id}",
                {"type": "order_update", "status": order.status, "message": f"Order is {order.get_status_display()}"}
            )
        except Exception as e:
            logger.error(f"WebSocket Broadcast Failed: {e}")

    @staticmethod
    @transaction.atomic
    def create_order(user, warehouse, items, delivery_type, address_id=None, payment_method=None):
        """
        Wrapper for create_order_after_reservation for backward compatibility.
        """
        if address_id is None:
            # Find or create a default address
            from apps.customers.models import CustomerAddress, CustomerProfile
            address = CustomerAddress.objects.filter(customer__user=user, is_deleted=False).first()
            if not address:
                # Create a dummy address
                customer, _ = CustomerProfile.objects.get_or_create(user=user)
                address = CustomerAddress.objects.create(
                    customer=customer,
                    house_no="123",
                    apartment_name="Test Apt",
                    google_address_text="Test Address",
                    latitude=0.0,
                    longitude=0.0,
                    city="Test City"
                )
            address_id = address.id
        if payment_method is None:
            payment_method = "cash"
        
        # Reserve inventory
        InventoryService.bulk_lock_and_reserve(
            warehouse_id=warehouse.id,
            items_dict={i['sku']: i['quantity'] for i in items},
            reference=f"order_init_{user.id}"
        )
        
        return OrderService.create_order_after_reservation(
            user=user,
            warehouse_id=warehouse.id,
            items_data=items,
            delivery_type=delivery_type,
            address_id=address_id,
            payment_method=payment_method
        )

    @staticmethod
    @transaction.atomic
    def create_order_after_reservation(user, warehouse_id, items_data, delivery_type, address_id, payment_method):
        """
        Creates Order. 
        Validation Order: Abuse -> Ownership -> GeoFence -> Inventory -> Surge -> Save.
        """
        # 1. Abuse Check (Fail Fast)
        try:
            OrderAbuseService.check(user)
        except ValidationError as e:
            logger.warning(f"Order Blocked (Abuse): User {user.id} - {e}")
            raise BusinessLogicException(str(e), code="user_blocked")

        warehouse = get_object_or_404(Warehouse, id=warehouse_id)

        # 2. Address Ownership
        try:
            address = CustomerAddress.objects.get(id=address_id, customer__user=user, is_deleted=False)
        except CustomerAddress.DoesNotExist:
            raise BusinessLogicException("Invalid delivery address.", code="invalid_address")

        # 3. Geo-Fencing (Final Gatekeeper)
        try:
            address_point = Point(float(address.longitude), float(address.latitude), srid=4326)
        except (ValueError, TypeError):
             raise BusinessLogicException("Invalid coordinates", code="geo_error")

        is_serviceable = False
        if warehouse.delivery_zone and warehouse.delivery_zone.contains(address_point):
            is_serviceable = True
        elif not warehouse.delivery_zone:
            is_serviceable = True 
        
        if not is_serviceable:
            logger.warning(f"GeoFence Rejection: User={user.id} Addr={address.id} WH={warehouse.code}")
            raise BusinessLogicException("Address outside delivery area.", code="location_out_of_zone")

        # 4. Create Order Object
        address_snapshot = {
            "id": address.id,
            "full_address": address.google_address_text or f"{address.house_no}, {address.apartment_name}",
            "lat": float(address.latitude),
            "lng": float(address.longitude),
            "city": getattr(address, 'city', '')
        }

        order = Order.objects.create(
            user=user, warehouse=warehouse, status="created",
            delivery_type=delivery_type, total_amount=Decimal("0.00"),
            delivery_address_json=address_snapshot, payment_method=payment_method,
        )

        # 5. Process Items
        total = Decimal("0.00")
        skus = [item["sku"] for item in items_data]
        inventory_map = {inv.sku: inv for inv in InventoryItem.objects.filter(
            bin__rack__aisle__zone__warehouse=warehouse, sku__in=skus
        )}

        for item in items_data:
            sku = item["sku"]; qty = int(item["quantity"])
            if qty <= 0: raise BusinessLogicException(f"Invalid quantity: {sku}")
            
            inventory = inventory_map.get(sku)
            if not inventory: raise BusinessLogicException(f"Item {sku} unavailable")

            OrderItem.objects.create(
                order=order, sku=sku, product_name=inventory.product_name,
                quantity=qty, price=inventory.price
            )
            total += inventory.price * qty

        # 6. Pricing & Save (DYNAMIC FEE LOGIC)
        surge_multiplier = SurgePricingService.calculate(order)
        
        from apps.orders.models import OrderConfiguration
        config = OrderConfiguration.objects.first()
        base_delivery_fee = config.delivery_fee if config else Decimal("5.00")
        threshold = config.free_delivery_threshold if config else Decimal("100.00")
        
        if total >= threshold:
            actual_delivery_fee = Decimal("0.00")
        else:
            actual_delivery_fee = base_delivery_fee 
        
        order.total_amount = total + actual_delivery_fee
        
        if hasattr(order, "surge_multiplier"): 
            order.surge_multiplier = surge_multiplier
            
        order.save()

        transaction.on_commit(lambda: AuditService.order_created(order))
        transaction.on_commit(lambda: OrderService._broadcast_status(order))

        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order):
        order = Order.objects.select_for_update().get(id=order.id)
        if order.status in ["delivered", "cancelled", "out_for_delivery", "failed"]:
            raise BusinessLogicException(f"Cannot cancel: {order.status}")

        order.status = "cancelled"; order.save(update_fields=["status", "updated_at"])

        # Release Inventory
        for order_item in order.items.all():
            inv = InventoryItem.objects.filter(sku=order_item.sku, bin__rack__aisle__zone__warehouse=order.warehouse).first()
            if inv: InventoryService.release_stock(inv.id, order_item.quantity, f"cancel:{order.id}")

        if hasattr(order, "payment") and order.payment.status == "paid":
            from apps.payments.refund_services import RefundService
            RefundService.initiate_refund(order.payment)

        OrderAbuseService.record_cancel(order.user)
        AuditService.order_cancelled(order)
        transaction.on_commit(lambda: OrderService._broadcast_status(order))

class OrderSimulationService:
    # (Kept as is - useful for testing/demo)
    @staticmethod
    def _get_or_create_bot_user():
        u, _ = User.objects.get_or_create(email="ops-bot@quickdash.com", defaults={"first_name": "Bot", "is_active": True})
        return u

    @staticmethod
    def _get_or_create_bot_rider(warehouse):
        u = OrderSimulationService._get_or_create_bot_user()
        r, _ = RiderProfile.objects.get_or_create(user=u, defaults={"is_active": True, "current_warehouse": warehouse})
        return r

    @staticmethod
    @transaction.atomic
    def advance_to_packed(order):
        bot = OrderSimulationService._get_or_create_bot_user()
        if not order.picking_tasks.exists(): WarehouseOperationsService.generate_picking_tasks(order)
        for t in order.picking_tasks.all(): t.status='picked'; t.save()
        pt, _ = PackingTask.objects.get_or_create(order=order)
        WarehouseOperationsService.complete_packing(pt.id, bot)
        return "Packed"

    @staticmethod
    @transaction.atomic
    def advance_to_out_for_delivery(order):
        if order.status != 'packed': OrderSimulationService.advance_to_packed(order)
        if not hasattr(order, 'delivery'): DeliveryService.initiate_delivery_search(order)
        order.refresh_from_db()
        if not order.delivery.rider: 
            DeliveryService.assign_rider(order, OrderSimulationService._get_or_create_bot_rider(order.warehouse))
        order.delivery.status = "out_for_delivery"; order.delivery.save()
        order.status = "out_for_delivery"; order.save()
        OrderService._broadcast_status(order)
        return "Out for Delivery"

    @staticmethod
    @transaction.atomic
    def advance_to_delivered(order):
        if order.status != 'out_for_delivery': OrderSimulationService.advance_to_out_for_delivery(order)
        DeliveryService.mark_delivered(order.delivery, order.delivery.otp)
        return "Delivered"