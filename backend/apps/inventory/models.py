from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.warehouse.models import Bin
from django.conf import settings

User = settings.AUTH_USER_MODEL

class InventoryItem(models.Model):
    """
    Ab Inventory ek 'Batch' ke roop mein kaam karegi.
    Ek SKU ke multiple batches ho sakte hain alag-alag owners ke.
    """
    INVENTORY_MODE_CHOICES = (
        ("owned", "Owned Inventory (Company)"),             
        ("consignment", "Consignment (Vendor)"),           
        ("virtual", "Virtual Inventory (Drop-ship)"),         
    )

    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name="items")
    sku = models.CharField(max_length=100, db_index=True)
    product_name = models.CharField(max_length=255)
    
    # Ye customer ko dikhane wali price hai
    price = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    
    # NAYE FIELDS: Owner aur Cost Track karne ke liye
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_batches", help_text="Agar Null hai, toh Company ka stock hai")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default="0.00", help_text="Vendor ko kitna paisa dena hai per unit")

    total_stock = models.PositiveIntegerField(default=0)
    reserved_stock = models.PositiveIntegerField(default=0)
    
    mode = models.CharField(max_length=20, choices=INVENTORY_MODE_CHOICES, default="owned")
    lead_time_hours = models.PositiveIntegerField(default=0)
    
    # FIFO ke liye zaroori hai
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # unique_together = ("bin", "sku") # Ise hata diya gaya hai batch system ke liye
        indexes = [
            models.Index(fields=['bin', 'sku']),
            models.Index(fields=['sku', 'created_at']), # FIFO Query fast karne ke liye
            models.Index(fields=['owner']),
        ]
    
    @property
    def warehouse(self):
        return self.bin.rack.aisle.zone.warehouse

    @property
    def available_stock(self):
        return self.total_stock - self.reserved_stock

    def clean(self):
        if self.total_stock < self.reserved_stock:
            raise ValidationError("Total stock cannot be less than reserved stock.")

    def save(self, *args, **kwargs):
        from apps.catalog.models import Product
        product = Product.objects.filter(sku=self.sku).first()
        
        if product:
            if not self.product_name:
                self.product_name = product.name
            if self.price <= 0:
                self.price = product.mrp
            elif self.price > product.mrp:
                self.price = product.mrp

        super().save(*args, **kwargs)

    def __str__(self):
        owner_name = self.owner.phone if self.owner else "Company"
        return f"{self.sku} (Batch ID: {self.id}) | Owner: {owner_name}"


class InventoryTransaction(models.Model):
    # (Yeh waisa hi rahega jaisa apka pehle tha)
    TRANSACTION_TYPE_CHOICES = (
        ("add", "Add Stock"),
        ("reserve", "Reserve Stock"),
        ("release", "Release Stock"),
        ("commit", "Commit Stock"),
        ("adjust", "Cycle Count Adjust"),
    )

    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    quantity = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} for {self.inventory_item.sku}"