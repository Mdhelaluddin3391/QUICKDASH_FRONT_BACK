from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Order
from apps.delivery.tasks import assign_rider_to_order
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# 1. PRE-SAVE: Order save hone se pehle uska purana status yaad rakhne ke liye
@receiver(pre_save, sender=Order)
def track_old_order_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Order.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

# 2. RIDER ASSIGNMENT: Jab order pack ho jaye
@receiver(post_save, sender=Order)
def auto_assign_rider_on_status_change(sender, instance, created, **kwargs):
    """
    Triggers rider assignment when order status changes to 'packed'.
    """
    if created:
        return 

    old_status = getattr(instance, '_old_status', None)
    if old_status != "packed" and instance.status == "packed":
        transaction.on_commit(lambda: assign_rider_to_order.delay(instance.id))

# 3. ADMIN WEBSOCKET: Naya order aane par admin panel ko real-time update bhejna
@receiver(post_save, sender=Order)
def notify_admin_on_new_order(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "admin_notifications_group",
            {
                "type": "send_notification", 
                "message": "new_order",
                "order_id": instance.id
            }
        )