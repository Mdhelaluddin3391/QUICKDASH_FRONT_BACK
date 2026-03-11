from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.db import transaction
from .models import Product, Category, FlashSale
from apps.notifications.services import NotificationService # <-- Push Notification Service Import

@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def invalidate_catalog_cache(sender, instance, **kwargs):
    """
    Bumps the Catalog Version Key.
    """
    try:
        cache.incr("catalog_version")
    except ValueError:
        cache.set("catalog_version", 1, timeout=None)

# 1. PRE-SAVE: Product save hone se pehle uska purana Price (MRP) yaad rakhne ke liye
@receiver(pre_save, sender=Product)
def track_old_product_price(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            instance._old_mrp = old_instance.mrp
        except Product.DoesNotExist:
            instance._old_mrp = None
    else:
        instance._old_mrp = None

# 2. POST-SAVE: Price Drop ya Naya Product Add hone par Push Notification
@receiver(post_save, sender=Product)
def notify_on_product_changes(sender, instance, created, **kwargs):
    # Ye notification sabhi users ko bhejni hai, toh 'global' topic use karenge
    # Note: Aapke frontend me FCM topic subscription setup hona chahiye (e.g. "promotions" topic)
    topic = "promotions" 
    
    if created and instance.is_active:
        # Condition A: Naya Product Add Hua Hai
        title = "New Arrival! 🌟"
        message = f"Check out our latest addition: {instance.name}. Order now on QuickDash!"
        transaction.on_commit(lambda: NotificationService.send_global_push(
            topic=topic, 
            title=title, 
            message=message,
            extra_data={"product_sku": instance.sku}
        ))
        
    elif not created and instance.is_active:
        # Condition B: Product update hua hai, check karo Price Drop hua kya?
        old_mrp = getattr(instance, '_old_mrp', None)
        if old_mrp and instance.mrp < old_mrp:
            # Agar naya daam (mrp) purane se KAM hai, tabhi notification bhejenge
            title = "Price Drop Alert! 📉"
            message = f"Great news! {instance.name} is now available at just ₹{instance.mrp}."
            transaction.on_commit(lambda: NotificationService.send_global_push(
                topic=topic, 
                title=title, 
                message=message,
                extra_data={"product_sku": instance.sku}
            ))

# 3. POST-SAVE: Flash Sale Add hone par Push Notification
@receiver(post_save, sender=FlashSale)
def notify_on_flash_sale(sender, instance, created, **kwargs):
    if created and instance.is_active:
        topic = "promotions"
        title = "⚡ Flash Sale Live! ⚡"
        message = f"Hurry! Get {instance.discount_percentage}% OFF on {instance.product.name}. Limited time offer!"
        
        transaction.on_commit(lambda: NotificationService.send_global_push(
            topic=topic, 
            title=title, 
            message=message,
            extra_data={"product_sku": instance.product.sku, "type": "flash_sale"}
        ))