from django.db import models


class StoreSettings(models.Model):
    is_store_open = models.BooleanField(default=True, help_text="Agar check mark hata denge toh store frontend par OFF ho jayega.")
    store_closed_message = models.TextField(
        default="Sorry, we are currently closed. Please check back later.",
        help_text="Ye message users ko dikhega jab store OFF hoga."
    )

    class Meta:
        verbose_name = "Store Setting"
        verbose_name_plural = "Store Settings"

    def save(self, *args, **kwargs):
        self.pk = 1 
        super(StoreSettings, self).save(*args, **kwargs)

    def __str__(self):
        return f"Store Status: {'OPEN' if self.is_store_open else 'CLOSED'}"