import redis
import logging
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from .models import InventoryItem, InventoryTransaction
from apps.utils.exceptions import BusinessLogicException
from django.db import models # Added missing import

logger = logging.getLogger(__name__)

# Initialize Redis connection safely
try:
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    logger.error(f"Redis Connection Failed: {e}")
    r = None

class InventoryService:
    INVENTORY_TTL = 3600  # 1 Hour
    
    # Lua Script Return Codes
    LUA_SUCCESS = 1
    LUA_STOCK_OUT = 0
    LUA_MISSING_KEY = -1

    @staticmethod
    def check_stock(product_id, warehouse_id, quantity):
        """
        Quick read-only check (Non-locking). 
        Used for UI display (Cart validation).
        """
        # We sum up available stock across all bins in the warehouse for this product
        inventory = InventoryItem.objects.filter(
            product_id=product_id,
            bin__rack__aisle__zone__warehouse_id=warehouse_id
        ).aggregate(total=models.Sum('available_stock'))['total'] or 0
        
        return inventory >= quantity

    @staticmethod
    def _get_cache_key(warehouse_id: int, sku: str) -> str:
        return f"inventory:{{wh_{warehouse_id}}}:{sku}"

    @staticmethod
    def reserve_stock_cached(sku: str, warehouse_id: int, quantity: int):
        """
        High-Performance Stock Reservation.
        1. Try Redis (Lua Script for Atomicity).
        2. If Key Missing -> Lazy Load from DB -> Retry.
        3. If Stock Out -> Fast Fail.
        """
        if not r:
            # Fallback if Redis is down: Direct DB Lock (slower but safe)
            return InventoryService._reserve_stock_db_fallback(sku, warehouse_id, quantity)

        key = InventoryService._get_cache_key(warehouse_id, sku)
        
        # Atomically check and decrement
        lua_script = """
        if redis.call("exists", KEYS[1]) == 0 then
            return -1 -- Missing Key
        end

        local current_stock = tonumber(redis.call("get", KEYS[1]))
        local qty = tonumber(ARGV[1])

        if current_stock >= qty then
            redis.call("decrby", KEYS[1], qty)
            redis.call("expire", KEYS[1], ARGV[2])
            return 1 -- Success
        else
            return 0 -- Stock Out
        end
        """
        
        try:
            result = r.eval(lua_script, 1, key, quantity, InventoryService.INVENTORY_TTL)
        except redis.RedisError as e:
            logger.error(f"Redis Lua Error: {e}")
            return InventoryService._reserve_stock_db_fallback(sku, warehouse_id, quantity)

        if result == InventoryService.LUA_SUCCESS:
            return True

        if result == InventoryService.LUA_STOCK_OUT:
            raise BusinessLogicException(f"Out of stock: {sku}", code="stock_out")

        if result == InventoryService.LUA_MISSING_KEY:
            # Cache Miss: Rehydrate from DB
            logger.info(f"Cache Miss: {sku} (WH: {warehouse_id})")
            InventoryService._hydrate_cache(sku, warehouse_id)
            
            # Retry Recursively (Once)
            return InventoryService.reserve_stock_cached(sku, warehouse_id, quantity)

        return False

    @staticmethod
    def _reserve_stock_db_fallback(sku, warehouse_id, quantity):
        """
        Fallback when Redis is down. Directly locks DB row.
        """
        with transaction.atomic():
            item = InventoryItem.objects.select_for_update().filter(
                sku=sku, 
                bin__rack__aisle__zone__warehouse_id=warehouse_id
            ).first()
            
            if not item or item.available_stock < quantity:
                raise BusinessLogicException(f"Out of stock: {sku}", code="stock_out")
            
            return True

    @staticmethod
    def _hydrate_cache(sku, warehouse_id):
        item = InventoryItem.objects.filter(
            sku=sku, 
            bin__rack__aisle__zone__warehouse_id=warehouse_id
        ).first()
        
        if item and r:
            key = InventoryService._get_cache_key(warehouse_id, sku)
            r.set(key, item.available_stock, ex=InventoryService.INVENTORY_TTL, nx=True)

    @staticmethod
    def rollback_redis_stock(sku: str, warehouse_id: int, quantity: int):
        if not r: return
        try:
            key = InventoryService._get_cache_key(warehouse_id, sku)
            if r.exists(key):
                r.incrby(key, quantity)
                r.expire(key, InventoryService.INVENTORY_TTL)
        except Exception as e:
            logger.error(f"Redis Rollback Failed for {sku}: {e}")

    @staticmethod
    @transaction.atomic
    def bulk_lock_and_reserve(warehouse_id: int, items_dict: dict, reference: str):
        """
        Bulk Stock Reservation with Deadlock Protection.
        1. Sort SKUs (prevent deadlocks).
        2. Lock Rows.
        3. Validate & Deduct.
        """
        skus = list(items_dict.keys())
        
        # 1. Fetch IDs for locking
        candidates = InventoryItem.objects.filter(
            bin__rack__aisle__zone__warehouse_id=warehouse_id,
            sku__in=skus
        ).values("id", "sku")
        
        sku_to_id = {item["sku"]: item["id"] for item in candidates}
        
        # Validate existence
        missing = set(skus) - set(sku_to_id.keys())
        if missing:
            raise BusinessLogicException(f"Items not found: {', '.join(missing)}")

        # 2. Sort IDs to enforce lock ordering (Avoid Deadlocks)
        sorted_ids = sorted(sku_to_id.values())

        # 3. Acquire Pessimistic Locks
        locked_items = list(InventoryItem.objects.select_for_update().filter(id__in=sorted_ids))
        item_map = {item.id: item for item in locked_items}
        
        reserved_items = []

        # 4. Process
        for item_id in sorted_ids:
            item = item_map[item_id]
            qty_needed = items_dict[item.sku]

            if item.available_stock < qty_needed:
                raise BusinessLogicException(
                    f"Stock insufficient: {item.sku}. Requested: {qty_needed}, Available: {item.available_stock}",
                    code="stock_out"
                )

            # DB Update
            item.reserved_stock = F("reserved_stock") + qty_needed
            item.save(update_fields=["reserved_stock"])
            
            # Audit Log
            InventoryTransaction.objects.create(
                inventory_item=item,
                transaction_type="reserve",
                quantity=qty_needed,
                reference=reference
            )
            reserved_items.append(item)

        # 5. Sync Redis (Async)
        def _sync_cache():
            for item in reserved_items:
                InventoryService._sync_redis_stock(item.id)
        
        transaction.on_commit(_sync_cache)
        return True

    @staticmethod
    @transaction.atomic
    def add_stock(item: InventoryItem, quantity: int, reference=""):
        if quantity <= 0:
            raise ValidationError("Quantity must be positive")

        item.total_stock = F("total_stock") + quantity
        item.save(update_fields=["total_stock"])

        InventoryTransaction.objects.create(
            inventory_item=item,
            transaction_type="add",
            quantity=quantity,
            reference=reference,
        )
        
        transaction.on_commit(lambda: InventoryService._sync_redis_stock(item.id))

    @staticmethod
    @transaction.atomic
    def release_stock(item_id: int, quantity: int, reference: str = ""):
        # Lock required
        item = InventoryItem.objects.select_for_update().get(id=item_id)
        
        release_qty = min(item.reserved_stock, quantity)
        if release_qty == 0:
            return

        item.reserved_stock = F("reserved_stock") - release_qty
        item.save(update_fields=["reserved_stock"])

        InventoryTransaction.objects.create(
            inventory_item=item,
            transaction_type="release",
            quantity=release_qty,
            reference=reference,
        )

        transaction.on_commit(lambda: InventoryService._sync_redis_stock(item.id))

    @staticmethod
    @transaction.atomic
    def commit_stock(item: InventoryItem, quantity: int, reference=""):
        """
        Finalizes a sale: Decrements Total Stock and Reserved Stock.
        """
        item = InventoryItem.objects.select_for_update().get(id=item.id)

        if item.reserved_stock < quantity:
            raise ValidationError("Cannot commit more than reserved stock")

        item.reserved_stock = F("reserved_stock") - quantity
        item.total_stock = F("total_stock") - quantity
        item.save(update_fields=["reserved_stock", "total_stock"])

        InventoryTransaction.objects.create(
            inventory_item=item,
            transaction_type="commit",
            quantity=-quantity,
            reference=reference,
        )

        transaction.on_commit(lambda: InventoryService._sync_redis_stock(item.id))

    @staticmethod
    @transaction.atomic
    def cycle_count_adjust(item: InventoryItem, new_total: int, reference: str = ""):
        item = InventoryItem.objects.select_for_update().get(id=item.id)
        delta = new_total - item.total_stock
        
        item.total_stock = new_total
        # Safety: Reserved can't exceed Total
        if item.total_stock < item.reserved_stock:
             item.reserved_stock = item.total_stock

        item.save(update_fields=["total_stock", "reserved_stock"])

        InventoryTransaction.objects.create(
            inventory_item=item,
            transaction_type="adjust",
            quantity=delta,
            reference=reference,
        )

        transaction.on_commit(lambda: InventoryService._sync_redis_stock(item.id))

    @staticmethod
    def _sync_redis_stock(item_id):
        if not r: return
        try:
            item = InventoryItem.objects.get(id=item_id)
            key = InventoryService._get_cache_key(item.warehouse.id, item.sku)
            r.set(key, item.available_stock, ex=InventoryService.INVENTORY_TTL)
        except Exception as e:
            logger.error(f"Redis Sync Error: {e}")

    @staticmethod
    @transaction.atomic
    def release_stock_for_order(order):
        """
        Rollback mechanism for failed payments or cancellations.
        Identifies all reserved items and returns them to 'available_stock'.
        """
        order_items = order.items.all()
        for item in order_items:
            inv_item = InventoryItem.objects.select_for_update().filter(
                sku=item.sku,
                bin__rack__aisle__zone__warehouse=order.warehouse
            ).first()
            
            if inv_item:
                inv_item.reserved_stock = F("reserved_stock") - item.quantity
                inv_item.save(update_fields=["reserved_stock"])
                
                InventoryTransaction.objects.create(
                    inventory_item=inv_item,
                    transaction_type="release",
                    quantity=item.quantity,
                    reference=f"failed_payment_cleanup:{order.id}"
                )
                transaction.on_commit(lambda: InventoryService._sync_redis_stock(inv_item.id))