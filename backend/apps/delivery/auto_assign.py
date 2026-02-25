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
        ).order_by("active_delivery_count", "?")

        top_candidates = list(candidates[:5])

        if not top_candidates:
            return None

        for rider_candidate in top_candidates:
            try:
                with transaction.atomic():
                
                    rider_locked = RiderProfile.objects.select_for_update(nowait=True).get(id=rider_candidate.id)
                    
                    current_load = rider_locked.deliveries.filter(
                        status__in=["assigned", "picked_up", "out_for_delivery"]
                    ).count()
                    
                    if current_load >= AutoRiderAssignmentService.MAX_DELIVERIES_PER_RIDER:
                        continue 

                    return DeliveryService.assign_rider(order, rider_locked)
                    
            except OperationalError:
                continue

        return None