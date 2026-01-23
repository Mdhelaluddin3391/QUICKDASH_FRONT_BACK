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
import logging

logger = logging.getLogger(__name__)

class WarehouseService:
    CACHE_TIMEOUT = 300

    @staticmethod
    def get_active_warehouses(city: str):
        return Warehouse.objects.filter(city__iexact=city, is_active=True)

    @staticmethod
    def get_nearest_warehouse(lat, lng):
        """
        Finds the Serviceable Warehouse with Caching.
        Precision: 5 decimals (~1.1m) to avoid grid boundary errors.
        """
        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            return None

        # 1. Check Cache (Precision: 5 decimal places)
        cache_key = f"wh_lookup_{round(lat, 5)}_{round(lng, 5)}"
        cached_id = None
        try:
            cached_id = cache.get(cache_key)
        except Exception as e:
            logger.warning(f"Redis cache error in get_nearest_warehouse: {e}")

        if cached_id:
            try:
                return Warehouse.objects.get(id=cached_id, is_active=True)
            except Warehouse.DoesNotExist:
                try:
                    cache.delete(cache_key)
                except Exception:
                    pass

        # 2. DB Spatial Query
        point = Point(lng, lat, srid=4326)
        
        # Priority: Strict Polygon Containment (Deterministic: order by id)
        warehouse = Warehouse.objects.filter(
            delivery_zone__contains=point,
            is_active=True
        ).order_by('id').first()

        # 3. Cache & Return
        if warehouse:
            try:
                cache.set(cache_key, warehouse.id, timeout=WarehouseService.CACHE_TIMEOUT)
            except Exception as e:
                logger.warning(f"Redis cache set error: {e}")
            return warehouse
        
        return None

    @staticmethod
    def validate_warehouse_serviceability(warehouse, lat, lng):
        """
        Validates if user is strictly inside the warehouse zone.
        """
        if not warehouse.delivery_zone:
            # If no zone is defined, we might fallback to radius logic externally,
            # but for strict validation, we return False or check radius here.
            # Assuming Strict Mode for Checkout:
            return False 
            
        point = Point(float(lng), float(lat), srid=4326)
        return warehouse.delivery_zone.contains(point)

    @staticmethod
    def find_nearest_serviceable_warehouse(lat, lon, city=None, delivery_type="express"):
        try:
            user_point = Point(float(lon), float(lat), srid=4326)
        except (ValueError, TypeError):
            return None

        # 1. Check Strict Polygon First (Priority)
        warehouse_qs = Warehouse.objects.filter(
            is_active=True,
            delivery_zone__contains=user_point
        ).order_by('id')
        
        warehouse = warehouse_qs.first()
        if warehouse:
            return warehouse

        # ---------------------------------------------------------
        # FIX: Allow Radius Fallback even if Polygon exists
        # (Comment out or remove 'delivery_zone__isnull=True')
        # ---------------------------------------------------------
        
        if delivery_type == "express":
            # Settings se radius lein ya default 5km karein
            radius_km = getattr(settings, "WAREHOUSE_DARK_STORE_RADIUS_KM", 5) 
            warehouse_type_filter = ["dark_store"]
        else:
            radius_km = getattr(settings, "WAREHOUSE_MEGA_RADIUS_KM", 15)
            warehouse_type_filter = ["mega", "dark_store"]

        fallback_qs = Warehouse.objects.filter(
            is_active=True,
            warehouse_type__in=warehouse_type_filter,
            location__distance_lte=(user_point, D(km=radius_km)),
            # delivery_zone__isnull=True  <-- IS LINE KO COMMENT KAR DEIN YA HATA DEIN
        )

        warehouse = fallback_qs.annotate(
            distance=Distance("location", user_point)
        ).order_by("distance").first()

        return warehouse

# ... (WarehouseOperationsService remains unchanged) ...
class WarehouseOperationsService:
    # (The rest of WarehouseOperationsService provided in your original file is fine)
    # Including here to ensure file completeness if copied
    @staticmethod
    @transaction.atomic
    def inward_stock_putaway(warehouse_id, barcode, quantity, bin_code, user):
        bin_obj = get_object_or_404(Bin, bin_code=bin_code)
        inventory_item, created = InventoryItem.objects.select_for_update().get_or_create(
            sku=barcode, bin=bin_obj,
            defaults={"product_name": f"Product-{barcode}", "total_stock": 0, "reserved_stock": 0, "price": 0.00}
        )
        inventory_item.total_stock += int(quantity)
        inventory_item.updated_at = timezone.now()
        inventory_item.save()

        InventoryTransaction.objects.create(
            inventory_item=inventory_item, transaction_type="add",
            quantity=quantity, reference=f"inward_putaway_by_{user.id}"
        )
        transaction.on_commit(lambda: InventoryService._sync_redis_stock(inventory_item.id))
        return {"status": "success", "new_total": inventory_item.total_stock}

    @staticmethod
    def toggle_picker_status(user, is_online):
        cache.set(f"picker_status:{user.id}", is_online, timeout=None)
        return is_online

    @staticmethod
    @transaction.atomic
    def generate_picking_tasks(order):
        tasks = []
        for item in order.items.all():
            inventory = InventoryItem.objects.select_related('bin__rack__aisle__zone__warehouse').annotate(
                available_qty=F('total_stock') - F('reserved_stock')
            ).filter(
                sku=item.sku, bin__rack__aisle__zone__warehouse=order.warehouse,
                available_qty__gte=item.quantity
            ).order_by('-available_qty').first()

            if not inventory:
                raise BusinessLogicException(f"Insufficient stock for: {item.sku}")

            tasks.append(PickingTask(
                order=order, item_sku=item.sku, quantity_to_pick=item.quantity,
                target_bin=inventory, status="pending"
            ))
        PickingTask.objects.bulk_create(tasks)
        order.status = "picking"
        order.save(update_fields=["status"])

    @staticmethod
    @transaction.atomic
    def scan_pick(task_id, picker_user, scanned_bin_code, scanned_barcode):
        task = PickingTask.objects.select_for_update().get(id=task_id)
        if task.status == "picked": return "Already picked"
        if task.target_bin.bin.bin_code != scanned_bin_code: raise BusinessLogicException("Wrong Bin!")
        if task.target_bin.sku != scanned_barcode: raise BusinessLogicException("Wrong Item!")

        task.status = "picked"; task.picker = picker_user; task.picked_at = timezone.now(); task.save()
        order = Order.objects.select_for_update().get(id=task.order_id)
        
        if PickingTask.objects.filter(order=order).exclude(status="picked").count() == 0:
            if order.status != "packed":
                order.status = "packed"; order.save(update_fields=["status"])
                from apps.delivery.services import DeliveryService
                DeliveryService.initiate_delivery_search(order)
                return "Order Packed & Rider Search Started"
        return "Item Picked"

    @staticmethod
    def generate_packing_task(order):
        PackingTask.objects.create(order=order)
        order.status = "packing"; order.save(update_fields=["status"])

    @staticmethod
    @transaction.atomic
    def complete_packing(packing_task_id, user):
        task = PackingTask.objects.select_for_update().get(id=packing_task_id)
        task.is_completed = True; task.packer = user; task.save()
        order = task.order
        order.status = "confirmed"; order.save(update_fields=["status"])
        from apps.delivery.services import DeliveryService
        DeliveryService.initiate_delivery_search(order)

    @staticmethod
    def get_active_handover_orders(warehouse):
        return Order.objects.filter(warehouse=warehouse, status="packed").values('id', 'delivery__otp')