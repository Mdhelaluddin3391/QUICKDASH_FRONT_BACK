# apps/notifications/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.inventory.models import InventoryTransaction
from apps.catalog.models import FlashSale
from apps.notifications.services import NotificationService
from apps.inventory.models import InventoryTransaction
from apps.catalog.models import FlashSale, Product, Category
from apps.orders.models import Order # Assume kar rahe hain
from apps.notifications.services import NotificationService


# 1. New Stock Added Signal
@receiver(post_save, sender=InventoryTransaction)
def notify_new_stock(sender, instance, created, **kwargs):
    if created and instance.transaction_type == "add":
        product_name = instance.inventory_item.product_name
        quantity = instance.quantity
        
        # Topic name define karte hain
        topic = "new_arrivals"
        title = "New Stock Alert! 🎉"
        message = f"Hurry! {quantity} new units of {product_name} have just arrived in stock."
        
        # Notification trigger karna
        NotificationService.send_global_push(
            topic=topic,
            title=title,
            message=message,
            extra_data={"sku": instance.inventory_item.sku, "type": "inventory"}
        )


# 2. Flash Sale / Discount Signal
@receiver(post_save, sender=FlashSale)
def notify_flash_sale(sender, instance, created, **kwargs):
    # Sirf tab bhejo jab sale nayi ho ya active ho
    if created and instance.is_active:
        product_name = instance.product.name
        discount = instance.discount_percentage
        
        topic = "promotions"
        title = "Massive Discount! 💸"
        message = f"Get {discount}% OFF on {product_name}. Limited time offer, order now!"
        
        NotificationService.send_global_push(
            topic=topic,
            title=title,
            message=message,
            extra_data={"product_id": str(instance.product.id), "type": "discount"}
        )


@receiver(pre_save, sender=Order)
def track_order_status_change(sender, instance, **kwargs):
    """
    Status change track karne ke liye pre_save signal.
    """
    if instance.pk:
        try:
            old_order = Order.objects.get(pk=instance.pk)
            instance._old_status = old_order.status
        except Order.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Order)
def notify_order_updates(sender, instance, created, **kwargs):
    """
    Jab order create ho ya status update ho.
    """
    status_messages = {
        'placed': ("Order Confirmed! 🛍️", "Your order has been placed successfully."),
        'shipped': ("Order Shipped! 📦", "Your order has been shipped and is on its way."),
        'out_for_delivery': ("Out for Delivery! 🚚", "Your order is out for delivery today!"),
        'delivered': ("Delivered! 🎉", "Your order has been delivered. Enjoy!"),
    }

    current_status = getattr(instance, 'status', None)
    old_status = getattr(instance, '_old_status', None)

    # Agar naya order bana hai (placed) ya status change hua hai
    if created and current_status == 'placed':
        title, msg = status_messages['placed']
        NotificationService.send_push(instance.user, title, msg, {"order_id": str(instance.id), "type": "order"})
    
    elif not created and current_status != old_status and current_status in status_messages:
        title, msg = status_messages[current_status]
        NotificationService.send_push(instance.user, title, msg, {"order_id": str(instance.id), "type": "order"})


# ---------------------------------------------------------
# 4. Price Drop Alert (Wishlist Users)
# ---------------------------------------------------------
@receiver(pre_save, sender=Product)
def notify_price_drop(sender, instance, **kwargs):
    """
    Agar product ki price kam hoti hai, toh wishlist waale users ko notify karein.
    """
    if instance.pk:
        try:
            old_product = Product.objects.get(pk=instance.pk)
            if instance.price < old_product.price:
                # Price drop detect ho gaya!
                # Assuming ek Wishlist model hai jisme 'user' aur 'product' foreign keys hain
                from apps.catalog.models import Wishlist # Assume import
                
                wishlisted_users = Wishlist.objects.filter(product=instance).select_related('user')
                for item in wishlisted_users:
                    NotificationService.send_push(
                        user=item.user,
                        title="Price Drop Alert! 💰",
                        message=f"Good news! The price for {instance.name} has dropped to ₹{instance.price}.",
                        extra_data={"product_id": str(instance.id), "type": "price_drop"}
                    )
        except Product.DoesNotExist:
            pass


# ---------------------------------------------------------
# 5. New Product Launch Alert
# ---------------------------------------------------------
@receiver(post_save, sender=Product)
def notify_new_product_launch(sender, instance, created, **kwargs):
    """
    Jab bhi system mein naya product add ho (Global notification)
    """
    if created and instance.is_active:
        topic = "new_arrivals"
        title = "New Arrival! 🚀"
        message = f"Check out our latest product: {instance.name}. Available now!"
        
        NotificationService.send_global_push(
            topic=topic,
            title=title,
            message=message,
            extra_data={"product_id": str(instance.id), "type": "new_product"}
        )