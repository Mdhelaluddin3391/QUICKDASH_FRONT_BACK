# apps/warehouse/services.py
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from .models import Warehouse, PickingTask, PackingTask, Bin
from apps.orders.models import Order
from apps.inventory.models import InventoryItem, InventoryTransaction
from apps.inventory.services import InventoryService
from apps.utils.exceptions import BusinessLogicException

class WarehouseService:
    
    @staticmethod
    def get_active_warehouses(city: str):
        return Warehouse.objects.filter(
            city__iexact=city,
            is_active=True,
        )

    @staticmethod
    def find_nearest_serviceable_warehouse(lat, lon, city=None, delivery_type="express"):
        try:
            # Lat/Lon ko Point object mein convert karein
            user_point = Point(float(lon), float(lat), srid=4326)
        except (ValueError, TypeError):
            return None

        # ---------------------------------------------------------
        # STRATEGY 1: Strict Polygon Check (Sabse Accurate)
        # Check karein user ka point kis warehouse ke delivery_zone mein hai.
        # Isme City ke naam ki zarurat nahi hai.
        # ---------------------------------------------------------
        warehouse_qs = Warehouse.objects.filter(
            is_active=True,
            delivery_zone__contains=user_point
        )
        
        # Agar frontend ne city bheji hai, toh extra verify kar lo, warna chhod do
        if city:
            warehouse_qs = warehouse_qs.filter(city__iexact=city)

        warehouse = warehouse_qs.first()

        if warehouse:
            return warehouse

        # ---------------------------------------------------------
        # STRATEGY 2: Radius Fallback (Agar Polygon set nahi hai)
        # ---------------------------------------------------------
        radius_km = getattr(settings, "WAREHOUSE_STANDARD_RADIUS_KM", 5)
        warehouse_type_filter = []

        if delivery_type == "express":
            radius_km = getattr(settings, "WAREHOUSE_DARK_STORE_RADIUS_KM", 3)
            warehouse_type_filter = ["dark_store"]
        else:
            radius_km = getattr(settings, "WAREHOUSE_MEGA_RADIUS_KM", 15)
            warehouse_type_filter = ["mega", "dark_store"]

        # Radius check ke liye hum city ka use kar sakte hain narrow down karne ke liye
        # Lekin agar city nahi hai, toh purely distance par search karein
        fallback_qs = Warehouse.objects.filter(
            is_active=True,
            warehouse_type__in=warehouse_type_filter,
            location__distance_lte=(user_point, D(km=radius_km))
        )

        if city:
            fallback_qs = fallback_qs.filter(city__iexact=city)

        warehouse = fallback_qs.annotate(
            distance=Distance("location", user_point)
        ).order_by("distance").first()

        return warehouse


class WarehouseOperationsService:
    
    @staticmethod
    @transaction.atomic
    def inward_stock_putaway(warehouse_id, barcode, quantity, bin_code, user):
        """
        Inwarding Process: Scan Barcode -> Scan Bin -> Add Stock.
        """
        # Validate Bin exists
        bin_obj = get_object_or_404(Bin, bin_code=bin_code)
        
        # Lock or Create Inventory Item
        # Using select_for_update inside get_or_create context is tricky, 
        # so we fetch-lock or create safely.
        inventory_item, created = InventoryItem.objects.select_for_update().get_or_create(
            sku=barcode,
            bin=bin_obj,
            defaults={
                "product_name": f"Product-{barcode}", # Placeholder if catalog missing
                "total_stock": 0,
                "reserved_stock": 0,
                "price": 0.00
            }
        )

        inventory_item.total_stock += int(quantity)
        inventory_item.updated_at = timezone.now()
        inventory_item.save()

        # Audit Log
        InventoryTransaction.objects.create(
            inventory_item=inventory_item,
            transaction_type="add",
            quantity=quantity,
            reference=f"inward_putaway_by_{user.id}"
        )

        # Sync Cache
        transaction.on_commit(
            lambda: InventoryService._sync_redis_stock(inventory_item.id)
        )

        return {
            "status": "success",
            "product": inventory_item.product_name,
            "new_total": inventory_item.total_stock,
            "location": inventory_item.bin.bin_code
        }

    @staticmethod
    def toggle_picker_status(user, is_online):
        status_key = f"picker_status:{user.id}"
        cache.set(status_key, is_online, timeout=None)
        return is_online

    @staticmethod
    @transaction.atomic
    def generate_picking_tasks(order):
        """
        Breaks down an Order into specific Bin-level picking tasks.
        """
        tasks = []
        for item in order.items.all():
            # Find optimal inventory (FIFO or max stock)
            # Filter where available stock >= required
            inventory = InventoryItem.objects.select_related(
                'bin__rack__aisle__zone__warehouse'
            ).annotate(
                available_qty=F('total_stock') - F('reserved_stock')
            ).filter(
                sku=item.sku,
                bin__rack__aisle__zone__warehouse=order.warehouse,
                available_qty__gte=item.quantity
            ).order_by('-available_qty').first()

            if not inventory:
                # Critical: Inventory Mismatch (Sold but physically missing/reserved)
                # In production, this might trigger a "Short Pick" workflow
                raise BusinessLogicException(f"Insufficient available stock in warehouse bins for: {item.sku}")

            tasks.append(
                PickingTask(
                    order=order,
                    item_sku=item.sku,
                    quantity_to_pick=item.quantity,
                    target_bin=inventory,
                    status="pending"
                )
            )

        PickingTask.objects.bulk_create(tasks)
        
        order.status = "picking"
        order.save(update_fields=["status"])

    @staticmethod
    @transaction.atomic
    def scan_pick(task_id, picker_user, scanned_bin_code, scanned_barcode):
        """
        Picker scans Bin + Item. 
        Validates match, updates task, checks if Order is fully picked.
        """
        task = PickingTask.objects.select_for_update().get(id=task_id)

        # 1. Validation Logic
        if task.status == "picked":
            return "Already picked"
            
        if task.target_bin.bin.bin_code != scanned_bin_code:
            raise BusinessLogicException(f"Wrong Bin! Go to: {task.target_bin.bin.bin_code}")
            
        if task.target_bin.sku != scanned_barcode:
            raise BusinessLogicException("Wrong Item Scanned!")

        # 2. Update Task
        task.status = "picked"
        task.picker = picker_user
        task.picked_at = timezone.now()
        task.save()

        # 3. Check Order State
        order = Order.objects.select_for_update().get(id=task.order_id)
        
        if order.status == "cancelled":
            raise BusinessLogicException("Order Cancelled! Return item to bin.")

        # 4. Check if All Tasks Complete
        pending_count = PickingTask.objects.filter(order=order).exclude(status="picked").count()
        
        if pending_count == 0:
            if order.status != "packed":
                # Auto-transition to Packed (or Packing station if complex flow)
                order.status = "packed"
                order.save(update_fields=["status"])
                
                # Trigger Rider Search immediately after packing
                from apps.delivery.services import DeliveryService
                DeliveryService.initiate_delivery_search(order)
                return "Order Packed & Rider Search Started"

        return "Item Picked"

    @staticmethod
    def generate_packing_task(order: Order):
        PackingTask.objects.create(order=order)
        order.status = "packing"
        order.save(update_fields=["status"])

    @staticmethod
    @transaction.atomic
    def complete_packing(packing_task_id: int, user):
        task = PackingTask.objects.select_for_update().get(id=packing_task_id)
        task.is_completed = True
        task.packer = user
        task.save()

        order = task.order
        order.status = "confirmed" # or 'ready_for_handover'
        order.save(update_fields=["status"])

        from apps.delivery.services import DeliveryService
        DeliveryService.initiate_delivery_search(order)
        
    @staticmethod
    def get_active_handover_orders(warehouse):
        """
        Returns list of orders ready for rider handover in a specific warehouse.
        """
        return Order.objects.filter(
            warehouse=warehouse,
            status="packed"
        ).values('id', 'delivery__otp', 'delivery__rider__user__first_name')