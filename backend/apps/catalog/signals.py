from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Product, Category

@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def invalidate_catalog_cache(sender, instance, **kwargs):
    """
    Bumps the Catalog Version Key.
    This effectively invalidates all "Read-Aside" caches that rely on this version key.
    """
    try:
        cache.incr("catalog_version")
    except ValueError:
        cache.set("catalog_version", 1, timeout=None)