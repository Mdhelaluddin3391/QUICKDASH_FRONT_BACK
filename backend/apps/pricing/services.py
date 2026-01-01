# apps/pricing/services.py
from decimal import Decimal
from apps.orders.models import Order
from apps.riders.models import RiderProfile

class SurgePricingService:
    """
    Dynamic Pricing Engine based on Supply (Riders) vs Demand (Active Orders).
    """

    @staticmethod
    def calculate(order: Order) -> Decimal:
        warehouse = order.warehouse
        
        # 1. Fetch Rules (Safe Defaults)
        rule = getattr(warehouse, "surge_rule", None)
        
        # Use strings for Decimal init to ensure precision
        max_multiplier = Decimal(str(rule.max_multiplier)) if rule else Decimal("2.0")
        base_factor = Decimal(str(rule.base_factor)) if rule else Decimal("0.1")

        # 2. Measure Demand (Active Orders requiring delivery)
        active_orders = Order.objects.filter(
            warehouse=warehouse,
            status__in=["confirmed", "picking", "packed", "out_for_delivery"]
        ).count()

        # 3. Measure Supply (Online Riders)
        available_riders = RiderProfile.objects.filter(
            current_warehouse=warehouse,
            is_available=True,
            is_active=True,
        ).count()

        # 4. Supply Shock Handling
        if available_riders == 0:
            # Extreme case: No riders. Apply Max Surge immediately.
            return max_multiplier

        # 5. Calculate Ratio
        # Formula: 1.0 + (Demand / Supply) * Sensitivity
        ratio = Decimal(active_orders) / Decimal(available_riders)
        surge = Decimal("1.0") + (ratio * base_factor)
        
        # 6. Clamp to Limits
        final_surge = min(surge, max_multiplier)
        
        # Ensure never below 1.0
        final_surge = max(final_surge, Decimal("1.0"))

        return final_surge.quantize(Decimal("0.01"))