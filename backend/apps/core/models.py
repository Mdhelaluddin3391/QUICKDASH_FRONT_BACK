from django.db import models
from django.core.exceptions import ValidationError

class StoreSettings(models.Model):
    is_store_open = models.BooleanField(default=True)
    store_closed_message = models.TextField(
        default="Sorry, we are currently closed. Please check back later."
    )

    class Meta:
        verbose_name = "Store Setting"
        verbose_name_plural = "Store Settings"

    def clean(self):
        if StoreSettings.objects.exists() and not self.pk:
            raise ValidationError("Only one StoreSettings instance is allowed.")

    def save(self, *args, **kwargs):
        self.pk = 1 
        super(StoreSettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Store Status: {'OPEN' if self.is_store_open else 'CLOSED'}"