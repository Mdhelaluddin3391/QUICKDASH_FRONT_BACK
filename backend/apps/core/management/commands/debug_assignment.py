from django.core.management.base import BaseCommand
from apps.orders.models import Order
from apps.riders.models import RiderProfile
from apps.delivery.auto_assign import AutoRiderAssignmentService

class Command(BaseCommand):
    help = 'Debug why an order is not getting assigned'

    def add_arguments(self, parser):
        parser.add_argument('order_id', type=int)

    def handle(self, *args, **options):
        order_id = options['order_id']
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Order {order_id} not found"))
            return

        self.stdout.write(f"--- Debugging Order #{order.id} ---")
        self.stdout.write(f"Status: {order.status}")
        self.stdout.write(f"Warehouse: {order.warehouse} (ID: {order.warehouse.id})")

        # Check Matching Riders
        riders = RiderProfile.objects.filter(current_warehouse=order.warehouse)
        self.stdout.write(f"\nTotal Riders in this Warehouse: {riders.count()}")

        for rider in riders:
            self.stdout.write(f"\nChecking Rider: {rider.user.first_name} ({rider.user.phone})")
            self.stdout.write(f" - Active: {rider.is_active}")
            self.stdout.write(f" - Available (Online): {rider.is_available}")
            
            active_deliveries = rider.deliveries.filter(status__in=["assigned", "picked_up", "out_for_delivery"]).count()
            self.stdout.write(f" - Active Deliveries: {active_deliveries}")

            if not rider.is_active:
                self.stdout.write(self.style.WARNING("   -> REJECTED: Rider not active"))
            elif not rider.is_available:
                self.stdout.write(self.style.WARNING("   -> REJECTED: Rider is Offline"))
            elif active_deliveries >= 3: # Default limit
                self.stdout.write(self.style.WARNING("   -> REJECTED: Rider has too many orders"))
            else:
                self.stdout.write(self.style.SUCCESS("   -> ELIGIBLE: System should assign this rider!"))

        # Try Force Assign
        self.stdout.write("\nAttempting Logic Execution...")
        result = AutoRiderAssignmentService.assign(order)
        if result:
            self.stdout.write(self.style.SUCCESS(f"SUCCESS! Assigned to Rider ID {result.rider.id}"))
        else:
            self.stdout.write(self.style.ERROR("FAILED: No suitable rider found by the algorithm."))