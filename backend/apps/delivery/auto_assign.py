# apps/delivery/auto_assign.py
from django.conf import settings
from django.db import transaction, OperationalError
from django.db.models import Count, Q
from apps.riders.models import RiderProfile
from apps.orders.models import Order
from apps.delivery.services import DeliveryService

class AutoRiderAssignmentService:
    """
    Intelligent Rider Matching Logic.
    """
    MAX_DELIVERIES_PER_RIDER = getattr(settings, "DELIVERY_MAX_PER_RIDER", 3)

    @staticmethod
    def assign(order: Order):
        """
        Finds optimal rider using Non-Blocking Locking.
        """
        # 1. Filter Candidates (Spatial & Status)
        # Assuming we filter by warehouse linkage for MVP (simple geofence)
        candidates = RiderProfile.objects.filter(
            is_active=True,
            is_available=True,
            current_warehouse=order.warehouse, 
        ).annotate(
            active_delivery_count=Count(
                "deliveries",
                filter=Q(deliveries__status__in=["assigned", "picked_up", "out_for_delivery"])
            )
        ).filter(
            active_delivery_count__lt=AutoRiderAssignmentService.MAX_DELIVERIES_PER_RIDER
        ).order_by("active_delivery_count", "?") # Load Balance + Randomize to reduce collisions

        # Optimize: Check top 5 candidates only
        top_candidates = list(candidates[:5])

        if not top_candidates:
            return None

        # 2. Try-Lock Strategy
        for rider_candidate in top_candidates:
            try:
                with transaction.atomic():
                    # Attempt to lock this rider row NOWAIT
                    # If locked by another txn, we skip immediately (OperationalError)
                    rider_locked = RiderProfile.objects.select_for_update(nowait=True).get(id=rider_candidate.id)
                    
                    # Double Check Constraints inside Lock
                    current_load = rider_locked.deliveries.filter(
                        status__in=["assigned", "picked_up", "out_for_delivery"]
                    ).count()
                    
                    if current_load >= AutoRiderAssignmentService.MAX_DELIVERIES_PER_RIDER:
                        continue 

                    # Assign
                    return DeliveryService.assign_rider(order, rider_locked)
                    
            except OperationalError:
                # Rider is busy in another transaction, skip to next
                continue

        return None