from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Order
from apps.delivery.tasks import assign_rider_to_order

@receiver(post_save, sender=Order)
def auto_assign_rider_on_status_change(sender, instance, created, **kwargs):
    """
    Triggers rider assignment when order status changes to 'packed'.
    """
    if created:
        return  # Skip for new orders

    # Check if status changed to 'packed'
    if instance.status == "packed":
        # Run the task after transaction commits
        transaction.on_commit(lambda: assign_rider_to_order.delay(instance.id))