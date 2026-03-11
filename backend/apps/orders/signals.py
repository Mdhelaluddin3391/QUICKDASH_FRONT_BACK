from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Order
from apps.delivery.tasks import assign_rider_to_order
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.notifications.services import NotificationService  # <-- Push Notification Service Import

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

# 2. POST-SAVE: Customer ko Push Notification bhejne ke liye
@receiver(post_save, sender=Order)
def notify_customer_on_status_change(sender, instance, created, **kwargs):
    if created:
        # Naya order banne par bhi notification bhej sakte hain (Optional)
        return 

    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status

    # Agar status badla hai, tabhi notification bhejo
    if old_status != new_status:
        user = instance.user
        title = ""
        message = ""

        if new_status == "confirmed":
            title = "Order Confirmed! 🎉"
            message = f"Your order #{instance.id} has been confirmed and is being prepared."
        elif new_status == "packed":
            title = "Order Packed! 📦"
            message = f"Your order #{instance.id} is safely packed and waiting for our rider."
        elif new_status == "packed_at_mega_hub":
            title = "Packed at Mega Hub! 🏢"
            message = f"Your order #{instance.id} is packed at our Mega Hub and will be dispatched soon."
        elif new_status == "out_for_delivery":
            title = "Out for Delivery! 🛵"
            message = f"Yay! Your order #{instance.id} is on the way. Keep your phone handy!"
        elif new_status == "delivered":
            title = "Order Delivered! ✅"
            message = f"Your order #{instance.id} has been successfully delivered. Enjoy!"
        elif new_status == "cancelled":
            title = "Order Cancelled ❌"
            message = f"Your order #{instance.id} has been cancelled."

        # Agar title aur message set hua hai, toh notification background thread me bhej do
        if title and message:
            transaction.on_commit(lambda: NotificationService.send_push(
                user=user,
                title=title,
                message=message,
                extra_data={"order_id": str(instance.id), "status": new_status}
            ))