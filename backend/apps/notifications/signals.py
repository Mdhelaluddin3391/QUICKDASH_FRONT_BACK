# apps/notifications/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from apps.inventory.models import InventoryTransaction
from apps.catalog.models import FlashSale, Product, Category, Banner
from apps.orders.models import Order
from apps.notifications.services import NotificationService


# =========================================================
# 1. INVENTORY & STOCK ALERTS
# =========================================================
@receiver(post_save, sender=InventoryTransaction)
def notify_new_stock(sender, instance, created, **kwargs):
    """
    Jab naya stock aaye ya item restock ho, toh global notification send karein
    with product name & description.
    """
    valid_transaction_types = ["add", "restock", "in"] 
    
    if created and instance.transaction_type in valid_transaction_types:
        inventory_item = instance.inventory_item
        product_name = inventory_item.product_name
        
        # Product model se description nikalne ki koshish karte hain
        description = ""
        if hasattr(inventory_item, 'product') and inventory_item.product:
            # Sirf pehle 100 characters dikhayenge taaki notification badi na ho
            description = str(inventory_item.product.description)[:100] + "..."
        
        topic = "new_arrivals"
        title = "Stock Update! 🎉"
        message = f"Hurry! {product_name} is back in stock. {description}"
        
        NotificationService.send_global_push(
            topic=topic,
            title=title,
            message=message,
            extra_data={"sku": inventory_item.sku, "type": "inventory"}
        )


# =========================================================
# 2. PRODUCT PRICE DROP & NEW ARRIVALS
# =========================================================
@receiver(pre_save, sender=Product)
def track_product_price_change(sender, instance, **kwargs):
    """
    Product save hone se pehle uski purani price track karenge.
    """
    if instance.pk:
        try:
            old_product = Product.objects.get(pk=instance.pk)
            instance._old_price = old_product.price
        except Product.DoesNotExist:
            instance._old_price = None
    else:
        instance._old_price = None

@receiver(post_save, sender=Product)
def notify_price_drop(sender, instance, created, **kwargs):
    """
    Sirf tab notify karega jab price KAM hui ho (Price Drop).
    """
    old_price = getattr(instance, '_old_price', None)
    
    if not created and old_price is not None:
        if instance.price < old_price:
            topic = "promotions"
            title = "Price Drop Alert! 📉"
            message = f"Amazing deal! The price of {instance.name} just dropped from ₹{old_price} to ₹{instance.price}. Grab it now!"
            
            NotificationService.send_global_push(
                topic=topic,
                title=title,
                message=message,
                extra_data={"product_id": str(instance.id), "type": "price_drop"}
            )

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


# =========================================================
# 3. PROMOTIONS: FLASH SALE & BANNERS
# =========================================================
@receiver(post_save, sender=FlashSale)
def notify_flash_sale(sender, instance, created, **kwargs):
    """
    Jab nayi flash sale create ho, toh dhasu notification jaye.
    """
    if created and instance.is_active:
        product_name = instance.product.name
        discount = instance.discount_percentage
        
        topic = "promotions"
        title = f"⚡ FLASH SALE: {discount}% OFF! ⚡"
        message = f"Massive price drop on {product_name}! Hurry, the clock is ticking. Grab it before the sale ends!"
        
        NotificationService.send_global_push(
            topic=topic,
            title=title,
            message=message,
            extra_data={"product_id": str(instance.product.id), "type": "flash_sale"}
        )

@receiver(post_save, sender=Banner)
def notify_new_banner(sender, instance, created, **kwargs):
    """
    Jab bhi koi naya banner app me add ho (Hero ya Mid section me).
    """
    if created and instance.is_active:
        topic = "promotions"
        
        if instance.position == 'HERO':
            title = f"📢 Mega Update: {instance.title}"
            message = "Tap to check out our biggest offers and latest collections right now!"
        else:
            title = f"✨ Special Highlight: {instance.title}"
            message = "We have something special for you. Don't miss out, check it out today!"
        
        NotificationService.send_global_push(
            topic=topic,
            title=title,
            message=message,
            extra_data={
                "target_url": instance.target_url, 
                "type": "banner",
                "position": instance.position
            }
        )


# =========================================================
# 4. ORDER STATUS UPDATES
# =========================================================
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
    Jab order ka status (confirmed, packed, delivered etc.) update ho.
    """
    status_messages = {
        'confirmed': ("Order Confirmed! 🛍️", "Your order has been confirmed successfully and is being processed."),
        'packed': ("Order Packed! 📦", "Your order has been packed and is ready for the next steps."),
        'packed_at_hub': ("Packed at Mega Hub! 🏢", "Your order has been safely packed at our mega hub and will transit soon."),
        'out_for_delivery': ("Out for Delivery! 🚚", "Your order is out for delivery today! Be ready to receive it."),
        'delivered': ("Delivered! 🎉", "Your order has been delivered successfully. Thank you so much for shopping with us!"),
    }

    current_status = getattr(instance, 'status', None)
    old_status = getattr(instance, '_old_status', None)

    # Sirf tab bhejein jab status actually change hua ho
    if not created and current_status != old_status and current_status in status_messages:
        if instance.user:
            title, msg = status_messages[current_status]
            NotificationService.send_push(
                user=instance.user, 
                title=title, 
                message=msg, 
                extra_data={"order_id": str(instance.id), "type": "order"}
            )