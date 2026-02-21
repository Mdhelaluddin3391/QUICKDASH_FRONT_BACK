from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Order
from apps.delivery.tasks import assign_rider_to_order

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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




@receiver(post_save, sender=Order)
def notify_admin_on_new_order(sender, instance, created, **kwargs):
    if created: # Sirf naya order banne par
        channel_layer = get_channel_layer()
        
        # 'admin_notifications_group' me message bhej rahe hain
        async_to_sync(channel_layer.group_send)(
            "admin_notifications_group",
            {
                "type": "send_notification", # Yeh Consumer ka function name hoga
                "message": "new_order",
                "order_id": instance.id
            }
        )