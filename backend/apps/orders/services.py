import logging
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point  # Added for Geo-Fencing
from django.utils import timezone  # Added for SimulationService timestamps

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.inventory.models import InventoryItem
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
        """
        Safe method to broadcast order status via WebSockets.
        Swallows errors to protect the DB transaction from Redis failures.
        """
        try:
            channel_layer = get_channel_layer()
            room_group_name = f"order_{order.id}"

            message_payload = {
                "type": "order_update",
                "status": order.status,
                "updated_at": str(order.updated_at),
                "message": f"Order is now {order.get_status_display()}",
            }

            async_to_sync(channel_layer.group_send)(
                room_group_name,
                message_payload
            )

        except Exception as e:
            logger.error(
                f"WebSocket Broadcast Failed for Order {order.id}: {e}",
                exc_info=True
            )

    @staticmethod
    @transaction.atomic
    def create_order_after_reservation(
        user,
        warehouse_id,
        items_data,
        delivery_type,
        address_id,
        payment_method
    ):
        """
        Creates Order records after inventory has been reserved.
        SECURITY: STRICT Geo-Fencing & Ownership Check.
        """
        warehouse = get_object_or_404(Warehouse, id=warehouse_id)

        # 1. Abuse Check (Rate Limiting)
        try:
            OrderAbuseService.check(user)
        except ValidationError as e:
            raise BusinessLogicException(str(e), code="user_blocked")

        # 2. Strict Ownership Check
        # Prevents IDOR: User cannot order using someone else's address ID
        try:
            address = CustomerAddress.objects.get(
                id=address_id,
                customer__user=user,  # Must belong to authenticated user
                is_deleted=False      # Must be an active address
            )
            logger.info(f"OrderService: using address id={address.id} lat={address.latitude} lng={address.longitude} for user={user.id}")
        except CustomerAddress.DoesNotExist:
            raise BusinessLogicException(
                "Delivery address not found or invalid.", 
                code="invalid_address"
            )

        # 3. CRITICAL: Geo-Fencing Enforcement (Server Side)
        # We ignore whatever 'serviceable' flag the frontend sent.
        # We recalculate point-in-polygon strictly.
        try:
            address_point = Point(float(address.longitude), float(address.latitude), srid=4326)
        except (ValueError, TypeError):
             raise BusinessLogicException("Invalid address coordinates", code="geo_error")

        is_serviceable = False
        
        # A. Polygon Check (Primary)
        if warehouse.delivery_zone and warehouse.delivery_zone.contains(address_point):
            is_serviceable = True
        # B. Fallback: Check if warehouse supports fallback radius (Optional config)
        elif not warehouse.delivery_zone:
             # If no polygon defined, fail safe or check radius (depending on business rule)
             # Here we fail safe for strictness.
             logger.warning(f"Warehouse {warehouse.code} has no delivery_zone defined.")
        
        if not is_serviceable:
            # Audit the rejection
            logger.warning(
                f"GeoFence Rejection: User={user.id} Addr={address.id} WH={warehouse.code} "
                f"Dist={warehouse.location.distance(address_point) * 100} km approx"
            )
            raise BusinessLogicException(
                "This address is outside the delivery area for the selected store.",
                code="location_out_of_zone"
            )

        # 4. Snapshot Address (Immutable History)
        address_snapshot = {
            "id": address.id,
            "full_address": address.google_address_text or f"{address.house_no}, {address.apartment_name}",
            "label": address.label,
            "lat": float(address.latitude),
            "lng": float(address.longitude),
            "city": address.city if hasattr(address, 'city') else '',
            "house_no": address.house_no,
            "landmark": address.landmark
        }

        # 5. Create Order
        order = Order.objects.create(
            user=user,
            warehouse=warehouse,
            status="created",
            delivery_type=delivery_type,
            total_amount=Decimal("0.00"),
            delivery_address_json=address_snapshot,
            payment_method=payment_method,
        )

        # 5. Process Items & Calculate Base Price
        total = Decimal("0.00")
        skus = [item["sku"] for item in items_data]

        inventory_items = InventoryItem.objects.filter(
            bin__rack__aisle__zone__warehouse=warehouse,
            sku__in=skus,
        )
        inventory_map = {inv.sku: inv for inv in inventory_items}

        for item in items_data:
            sku = item["sku"]
            qty = int(item["quantity"])

            if qty <= 0:
                raise BusinessLogicException(f"Invalid quantity for {sku}")

            inventory = inventory_map.get(sku)
            if not inventory:
                raise BusinessLogicException(f"Item {sku} not found in warehouse")

            item_price = inventory.price

            OrderItem.objects.create(
                order=order,
                sku=sku,
                product_name=inventory.product_name,
                quantity=qty,
                price=item_price,
            )
            total += item_price * qty

        # 6. Apply Surge Pricing & Save
        surge_multiplier = SurgePricingService.calculate(order)
        order.total_amount = total * surge_multiplier
        if hasattr(order, "surge_multiplier"):
            order.surge_multiplier = surge_multiplier

        order.save(update_fields=["total_amount", "surge_multiplier"] if hasattr(order, "surge_multiplier") else ["total_amount"])

        # 7. Auditing & Broadcast
        transaction.on_commit(lambda: AuditService.order_created(order))
        transaction.on_commit(lambda: OrderService._broadcast_status(order))

        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order):
        # Pessimistic Lock to prevent race conditions during cancellation
        order = Order.objects.select_for_update().get(id=order.id)

        if order.status in [
            "delivered",
            "cancelled",
            "out_for_delivery",
            "failed",
        ]:
            raise BusinessLogicException(
                f"Cannot cancel order in state: {order.status}"
            )

        order.status = "cancelled"
        order.save(update_fields=["status", "updated_at"])

        # 1. Release Inventory
        # Sorting prevents deadlocks if multiple orders are cancelled simultaneously
        sorted_items = order.items.all().order_by("sku")

        for order_item in sorted_items:
            inventory_item = InventoryItem.objects.filter(
                sku=order_item.sku,
                bin__rack__aisle__zone__warehouse=order.warehouse,
            ).first()

            if inventory_item:
                InventoryService.release_stock(
                    item_id=inventory_item.id,
                    quantity=order_item.quantity,
                    reference=f"order_cancel:{order.id}",
                )

        # 2. Trigger Refund (if paid)
        if hasattr(order, "payment") and order.payment.status == "paid":
            from apps.payments.refund_services import RefundService
            RefundService.initiate_refund(order.payment)

        # 3. Log Abuse & Audit
        OrderAbuseService.record_cancel(order.user)
        AuditService.order_cancelled(order)

        transaction.on_commit(
            lambda: OrderService._broadcast_status(order)
        )


class OrderSimulationService:
    """
    Simulation / God-Mode service to advance orders through lifecycle
    without physical apps (For Demo/Testing purposes).
    """

    @staticmethod
    def _get_or_create_bot_user():
        bot_email = "ops-bot@quickdash.com"
        user, _ = User.objects.get_or_create(
            phone="+910000000000",
            defaults={
                "first_name": "QuickDash",
                "last_name": "Bot",
                "email": bot_email,
                "is_active": True
            }
        )
        return user

    @staticmethod
    def _get_or_create_bot_rider(warehouse):
        bot_user = OrderSimulationService._get_or_create_bot_user()
        rider, _ = RiderProfile.objects.get_or_create(
            user=bot_user,
            defaults={
                "is_active": True,
                "is_available": True,
                "current_warehouse": warehouse
            }
        )
        if rider.current_warehouse != warehouse:
            rider.current_warehouse = warehouse
            rider.save()
        return rider

    @staticmethod
    @transaction.atomic
    def advance_to_packed(order):
        if order.status not in ['confirmed', 'picking', 'packing']:
            raise BusinessLogicException(f"Order must be confirmed/picking to pack. Current: {order.status}")

        bot_user = OrderSimulationService._get_or_create_bot_user()

        # 1. Generate tasks if missing
        if not order.picking_tasks.exists():
            WarehouseOperationsService.generate_picking_tasks(order)

        # 2. Force complete picking tasks
        for task in order.picking_tasks.filter(status__ne='picked'):
            task.status = 'picked'
            task.picker = bot_user
            task.picked_at = timezone.now()
            task.save()

        # 3. Ensure Packing Task Exists
        packing_task, _ = PackingTask.objects.get_or_create(order=order)
        
        # 4. Complete Packing
        WarehouseOperationsService.complete_packing(packing_task.id, bot_user)
        
        # 5. Move to Dispatch Bin (Ready for Handover)
        if hasattr(order, 'delivery'):
            order.delivery.dispatch_location = "DISPATCH-A1"
            order.delivery.save()
            order.status = "packed" # Ensure status is synced
            order.save()

        OrderService._broadcast_status(order)
        return "Order Packed & Ready for Dispatch"

    @staticmethod
    @transaction.atomic
    def advance_to_out_for_delivery(order):
        if order.status != 'packed':
            OrderSimulationService.advance_to_packed(order)
            order.refresh_from_db()

        # 1. Ensure Delivery Record
        if not hasattr(order, 'delivery'):
            DeliveryService.initiate_delivery_search(order)
            order.refresh_from_db()

        delivery = order.delivery
        
        # 2. Assign Rider (Bot if none)
        if not delivery.rider:
            bot_rider = OrderSimulationService._get_or_create_bot_rider(order.warehouse)
            DeliveryService.assign_rider(order, bot_rider)
            delivery.refresh_from_db()

        # 3. Simulate Pickup
        # We bypass the 'scan' check of rider_self_pickup and set state directly for simulation
        delivery.status = "out_for_delivery"
        delivery.save()
        
        order.status = "out_for_delivery"
        order.save()

        OrderService._broadcast_status(order)
        return f"Order Out for Delivery (Rider: {delivery.rider.user.first_name})"

    @staticmethod
    @transaction.atomic
    def advance_to_delivered(order):
        if order.status != 'out_for_delivery':
            OrderSimulationService.advance_to_out_for_delivery(order)
            order.refresh_from_db()

        delivery = order.delivery
        
        # 1. Simulate Delivery Completion (OTP Verification bypassed essentially, but using correct OTP)
        DeliveryService.mark_delivered(delivery, delivery.otp)
        
        return "Order Delivered & Settled"