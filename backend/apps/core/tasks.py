import logging
import redis
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from apps.inventory.models import InventoryItem
from apps.inventory.services import InventoryService
from apps.orders.models import Order

logger = logging.getLogger(__name__)

@shared_task
def reconcile_inventory_redis_db():
    """
    Self-Healing: Periodic Sync between DB (Source of Truth) and Redis (Cache).
    Iterates over tracked inventory keys to fix drift.
    """
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.error(f"Skipping Reconciliation: Redis unavailable ({e})")
        return

    inventory_set_key = "active_inventory_keys"
    
    for key in r.sscan_iter(inventory_set_key, count=100):
        try:
            key_str = str(key)
            parts = key_str.split(':')
            if len(parts) < 3:
                r.srem(inventory_set_key, key)
                continue
                
            warehouse_id = parts[1].replace('{wh_', '').replace('}', '')
            sku = parts[2]
            
            item = InventoryItem.objects.filter(
                sku=sku,
                bin__rack__aisle__zone__warehouse_id=warehouse_id
            ).first()
            
            if item:
                InventoryService._sync_redis_stock(item.id)
            else:
                r.delete(key_str)
                r.srem(inventory_set_key, key)
                
        except Exception as e:
            logger.error(f"Reconciliation error for {key}: {e}")

@shared_task
def monitor_stuck_orders():
    """
    SLA Monitor: Alerts on orders stuck in transient states > 10 minutes.
    """
    limit = timezone.now() - timedelta(minutes=10)
    
    stuck_picking = Order.objects.filter(status="picking", updated_at__lt=limit).count()
    stuck_packing = Order.objects.filter(status="packed", updated_at__lt=limit).count()
    
    stuck_searching = Order.objects.filter(
        delivery__job_status="searching", 
        updated_at__lt=limit
    ).count()
    
    if stuck_picking or stuck_packing or stuck_searching:
        msg = (
            f"[SLA BREACH] Stuck Orders: "
            f"Picking={stuck_picking}, Packing={stuck_packing}, RiderSearch={stuck_searching}"
        )
        logger.warning(msg)
        return msg
    
    return "All systems nominal"


@shared_task
def beat_heartbeat():
    """
    Liveness Signal: Writes timestamp to Redis.
    The HealthCheck endpoint checks this to ensure the Scheduler is alive.
    """
    cache.set("celery_beat_health", timezone.now().timestamp(), timeout=120)
    return "Beat Alive"