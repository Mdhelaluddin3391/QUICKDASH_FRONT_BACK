from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Order
from apps.delivery.tasks import retry_auto_assign_rider

@receiver(post_save, sender=Order)
def auto_assign_rider_on_admin_change(sender, instance, created, **kwargs):
    """
    Agar Admin Panel se bhi status 'packed' change kiya gaya,
    toh ye signal Rider dhoondhne wala task chala dega.
    """
    if created:
        return  # Naye order par kuch nahi karna

    # Agar Order 'packed' status main hai
    if instance.status == "packed":
        # Transaction complete hone ke baad task run karein
        transaction.on_commit(lambda: retry_auto_assign_rider.delay(instance.id))