from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import RiderProfile
from apps.delivery.tasks import retry_auto_assign_rider
from apps.orders.models import Order

@receiver(post_save, sender=RiderProfile)
def trigger_assignment_on_rider_availability(sender, instance, created, **kwargs):
    """
    Jab Rider offline se 'Available' hota hai, tab check karein
    ki uske warehouse main koi 'Packed' order pending to nahi hai.
    """
    # Agar rider ab available hai aur warehouse set hai
    if instance.is_available and instance.current_warehouse:
        
        # Un orders ko dhoondo jo 'packed' hain lekin rider assign nahi hua
        pending_orders = Order.objects.filter(
            warehouse=instance.current_warehouse,
            status='packed'
        ).filter(
            # Delivery object ya to exist nahi karta, ya rider null hai
            delivery__rider__isnull=True
        )

        # Har pending order ke liye assignment task dobara chalao
        for order in pending_orders:
            # Transaction ke baad task queue karo taaki race condition na ho
            transaction.on_commit(lambda: retry_auto_assign_rider.delay(order.id))