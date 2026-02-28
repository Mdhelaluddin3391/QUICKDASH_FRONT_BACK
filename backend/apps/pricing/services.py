from decimal import Decimal
from apps.orders.models import Order
from apps.riders.models import RiderProfile

class SurgePricingService:
    """
    Dynamic Pricing Engine based on Supply (Riders) vs Demand (Active Orders).
    """

    @staticmethod
    def calculate(order: Order) -> Decimal:
        # 1. FIX: Changed 'order.warehouse' to 'order.last_mile_warehouse'
        warehouse = order.last_mile_warehouse
        
        # Ek safety check agar warehouse assign nahi hua hai
        if not warehouse:
            return Decimal("1.0")
            
        rule = getattr(warehouse, "surge_rule", None)
        
        max_multiplier = Decimal(str(rule.max_multiplier)) if rule else Decimal("2.0")
        base_factor = Decimal(str(rule.base_factor)) if rule else Decimal("0.1")

        # 2. FIX: Updated filter field from 'warehouse' to 'last_mile_warehouse'
        active_orders = Order.objects.filter(
            last_mile_warehouse=warehouse, 
            status__in=["confirmed", "picking", "packed", "out_for_delivery"]
        ).count()

        available_riders = RiderProfile.objects.filter(
            current_warehouse=warehouse,
            is_available=True,
            is_active=True,
        ).count()

        if available_riders == 0:
            return max_multiplier

        ratio = Decimal(active_orders) / Decimal(available_riders)
        surge = Decimal("1.0") + (ratio * base_factor)
        
        final_surge = min(surge, max_multiplier)
        
        final_surge = max(final_surge, Decimal("1.0"))

        return final_surge.quantize(Decimal("0.01"))