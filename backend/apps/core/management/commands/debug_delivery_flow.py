# backend/apps/core/management/commands/debug_delivery_flow.py
from django.core.management.base import BaseCommand
from apps.orders.models import Order
from apps.delivery.models import Delivery
from apps.riders.models import RiderProfile
from apps.delivery.auto_assign import AutoRiderAssignmentService

class Command(BaseCommand):
    help = "Debug assignment logic and print OTP for specific order"

    def add_arguments(self, parser):
        parser.add_argument('order_id', type=int)

    def handle(self, *args, **options):
        order_id = options['order_id']
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Order {order_id} not found"))
            return

        self.stdout.write(f"--- DEBUGGING ORDER #{order.id} ---")
        self.stdout.write(f"Status: {order.status}")
        self.stdout.write(f"Warehouse: {order.warehouse.name} ({order.warehouse.id})")

        # 1. Check existing delivery
        if hasattr(order, 'delivery'):
            d = order.delivery
            self.stdout.write(self.style.WARNING(f"Existing Delivery Found: ID={d.id}, Status={d.status}, Rider={d.rider}"))
            self.stdout.write(self.style.SUCCESS(f"Existing OTP: {d.otp}"))
        else:
            self.stdout.write("No delivery record yet.")

        # 2. Check Rider Availability
        riders = RiderProfile.objects.filter(
            current_warehouse=order.warehouse,
            is_active=True,
            is_available=True
        )
        self.stdout.write(f"Available Riders in Warehouse: {riders.count()}")
        for r in riders:
            active_jobs = r.deliveries.filter(status__in=['assigned', 'picked_up', 'out_for_delivery']).count()
            self.stdout.write(f" - {r.user.first_name}: {active_jobs} active jobs")

        # 3. Force Assignment (Optional)
        if hasattr(order, 'delivery') and not order.delivery.rider and riders.exists():
            self.stdout.write("Attempting manual assignment to first available rider...")
            rider = riders.first()
            order.delivery.rider = rider
            order.delivery.status = 'assigned'
            order.delivery.save()
            self.stdout.write(self.style.SUCCESS(f"Force Assigned to {rider.user.first_name}. OTP is: {order.delivery.otp}"))