# apps/inventory/models.py
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.warehouse.models import Bin

class InventoryItem(models.Model):
    """
    Inventory is tracked at the BIN level.
    Uniquely identified by (Bin + SKU).
    """
    INVENTORY_MODE_CHOICES = (
        ("owned", "Owned Inventory"),             
        ("consignment", "Consignment"),           
        ("virtual", "Virtual Inventory"),         
    )

    bin = models.ForeignKey(
        Bin,
        on_delete=models.CASCADE,
        related_name="items"
    )

    sku = models.CharField(max_length=100, db_index=True)
    
    # Denormalized fields for performance (Warehouse Ops don't query Catalog Join constantly)
    product_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")

    total_stock = models.PositiveIntegerField(default=0)
    reserved_stock = models.PositiveIntegerField(default=0)
    
    mode = models.CharField(
        max_length=20, 
        choices=INVENTORY_MODE_CHOICES, 
        default="owned"
    )
    
    lead_time_hours = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("bin", "sku")
        indexes = [
            models.Index(fields=['bin', 'sku']),
            models.Index(fields=['mode']),
            models.Index(fields=['updated_at']),
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
        # Product details fetch karne ke liye import kiya
        from apps.catalog.models import Product
        
        # Pehle hum SKU ke base par related product fetch karenge
        product = Product.objects.filter(sku=self.sku).first()
        
        if product:
            # Sync product name if missing
            if not self.product_name:
                self.product_name = product.name
                
            # Agar price 0 ya negative hai, toh seedha MRP laga do
            if self.price <= 0:
                self.price = product.mrp
            # AUTO-CORRECTION LOGIC: 
            # Agar inventory ki selling price product ke MRP se zyada hai,
            # toh usko automatically reduce karke MRP ke barabar kar do.
            elif self.price > product.mrp:
                self.price = product.mrp

        # Baaki ka default save behavior run karega
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} @ {self.bin.bin_code}"


class InventoryTransaction(models.Model):
    """
    Immutable ledger of all stock movements.
    """
    TRANSACTION_TYPE_CHOICES = (
        ("add", "Add Stock"),
        ("reserve", "Reserve Stock"),
        ("release", "Release Stock"),
        ("commit", "Commit Stock"),
        ("adjust", "Cycle Count Adjust"),
    )

    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    quantity = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} for {self.inventory_item.sku}"