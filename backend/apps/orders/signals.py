import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Order
from apps.delivery.tasks import assign_rider_to_order
from apps.notifications.services import NotificationService # Import zaroori hai

logger = logging.getLogger(__name__)

# 1. PRE-SAVE: Order save hone se pehle uska purana status yaad rakhne ke liye
# (Ise humne combine kar diya hai, ab yeh sirf ek baar run hoga)
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

# 4. CUSTOMER NOTIFICATION: Order status change par user ko push bhejna
# (Yeh aapka naya code hai jo humne yahan add kiya hai)
@receiver(post_save, sender=Order)
def notify_customer_order_updates(sender, instance, created, **kwargs):
    # 'created' par alag message bhej sakte hain (e.g., "Order Placed"), abhi status update track kar rahe hain
    if created:
        return

    status_messages = {
        'confirmed': ("Order Confirmed! 🛍️", "Your order has been confirmed successfully and is being processed."),
        'packed': ("Order Packed! 📦", "Your order has been packed and is ready for the next steps."),
        'packed_at_hub': ("Packed at Mega Hub! 🏢", "Your order has been safely packed at our mega hub and will transit soon."),
        'out_for_delivery': ("Out for Delivery! 🚚", "Your order is out for delivery today! Be ready to receive it."),
        'delivered': ("Delivered! 🎉", "Your order has been delivered successfully. Thank you so much for shopping with us!"),
    }
    
    current_status = getattr(instance, 'status', None)
    old_status = getattr(instance, '_old_status', None)

    # Agar status change hua hai aur hamari list mein hai
    if current_status != old_status and current_status in status_messages:
        if instance.user:
            title, msg = status_messages[current_status]
            try:
                NotificationService.send_push(
                    user=instance.user, 
                    title=title, 
                    message=msg, 
                    extra_data={"order_id": str(instance.id), "type": "order"}
                )
                logger.info(f"Push notification triggered for User {instance.user.phone}, Order ID {instance.id}, Status {current_status}")
            except Exception as e:
                logger.error(f"Failed to send push notification for Order {instance.id}: {e}")