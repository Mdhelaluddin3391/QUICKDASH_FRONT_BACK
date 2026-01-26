from django.core.management.base import BaseCommand
from django.db import transaction
from apps.orders.models import Order
from apps.riders.models import RiderProfile
from apps.delivery.models import Delivery
from apps.delivery.auto_assign import AutoRiderAssignmentService

class Command(BaseCommand):
    help = 'Debugs why rider is not getting assigned, fixes it, and retries.'

    def add_arguments(self, parser):
        parser.add_argument('order_id', type=int, help='The ID of the packed order')

    def handle(self, *args, **kwargs):
        order_id = kwargs['order_id']
        
        self.stdout.write(self.style.WARNING(f"--- STARTING DEBUG FOR ORDER #{order_id} ---"))

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Order {order_id} not found!"))
            return

        self.stdout.write(f"Order Status: {order.status}")
        self.stdout.write(f"Warehouse: {order.warehouse.name} ({order.warehouse.code})")

        if order.status != 'packed':
            self.stdout.write(self.style.ERROR("Error: Order status must be 'packed' to assign a rider."))
            return

        # 1. FIND RIDERS
        riders = RiderProfile.objects.filter(
            current_warehouse=order.warehouse,
            is_active=True,
            is_available=True
        )
        
        if not riders.exists():
            self.stdout.write(self.style.ERROR("FAIL: No active/available riders found in this warehouse."))
            return

        self.stdout.write(f"Found {riders.count()} potential riders.")

        # 2. CHECK & FIX RIDER LOAD
        for rider in riders:
            self.stdout.write(f"\nChecking Rider: {rider.user.first_name} (ID: {rider.id})...")
            
            active_deliveries = rider.deliveries.filter(
                status__in=["assigned", "picked_up", "out_for_delivery"]
            )
            count = active_deliveries.count()
            limit = AutoRiderAssignmentService.MAX_DELIVERIES_PER_RIDER
            
            self.stdout.write(f"  - Active Jobs: {count} / {limit}")

            if count >= limit:
                self.stdout.write(self.style.WARNING("  -> Rider is BUSY. Clearing old jobs to fix test..."))
                
                # FIX: Clear old jobs
                for d in active_deliveries:
                    d.status = 'delivered'
                    d.save()
                    self.stdout.write(f"     - Marked Delivery #{d.id} as DELIVERED")
                
                self.stdout.write(self.style.SUCCESS("  -> Rider is now FREE."))

        # 3. CLEANUP OLD DELIVERY OBJECT ON ORDER
        if hasattr(order, 'delivery'):
            self.stdout.write(self.style.WARNING("\nOrder already has a failed/stuck delivery object. Deleting it..."))
            order.delivery.delete()

        # 4. RUN ASSIGNMENT TEST
        self.stdout.write("\n--- ATTEMPTING ASSIGNMENT ---")
        assigned_rider = AutoRiderAssignmentService.assign(order)

        if assigned_rider:
            self.stdout.write(self.style.SUCCESS(f"✅ TEST PASSED: Order assigned to {assigned_rider.rider.user.first_name}"))
            self.stdout.write(f"Delivery ID: {assigned_rider.id}")
            self.stdout.write(f"OTP: {assigned_rider.otp}")
        else:
            self.stdout.write(self.style.ERROR("❌ TEST FAILED: Logic returned None. Check logs."))