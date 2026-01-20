# apps/warehouse/models.py
from django.contrib.gis.db import models
from django.utils import timezone
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Warehouse(models.Model):
    WAREHOUSE_TYPE_CHOICES = (
        ("dark_store", "Dark Store"),
        ("mega", "Mega Warehouse"),
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, unique=True)
    warehouse_type = models.CharField(max_length=20, choices=WAREHOUSE_TYPE_CHOICES)
    
    city = models.CharField(max_length=50)
    state = models.CharField(max_length=50)

    # Spatial Fields
    location = models.PointField(srid=4326, help_text="Exact GPS coordinates")
    delivery_zone = models.PolygonField(srid=4326, null=True, blank=True, help_text="Serviceable Area")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["city", "is_active"]),
            # GIST Index for spatial queries
            models.Index(fields=['location'], name='warehouse_loc_gist_idx', opclasses=['gist_geometry_ops_2d']),
            models.Index(fields=['delivery_zone'], name='wh_del_zone_gist_idx', opclasses=['gist_geometry_ops_2d']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# --- Physical Layout Models ---

class StorageZone(models.Model):
    """ E.g., Cold Storage, Frozen, Dry, Secure """
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField(max_length=50)
    
    def __str__(self):
        return f"{self.warehouse.code} - {self.name}"

class Aisle(models.Model):
    zone = models.ForeignKey(StorageZone, on_delete=models.CASCADE, related_name="aisles")
    number = models.CharField(max_length=10) 

    def __str__(self):
        return f"{self.zone.name} - Aisle {self.number}"

class Rack(models.Model):
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name="racks")
    number = models.CharField(max_length=10) 

class Bin(models.Model):
    """ Specific Bin location: Smallest unit """
    rack = models.ForeignKey(Rack, on_delete=models.CASCADE, related_name="bins")
    bin_code = models.CharField(max_length=20, unique=True) # E.g., "MUM01-Z1-A1-R1-B04"
    capacity_units = models.IntegerField(default=100)

    def __str__(self):
        return self.bin_code


# --- Workflow Tasks ---

class PickingTask(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("picked", "Picked"),
        ("failed", "Failed"),
    )

    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name="picking_tasks")
    picker = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="assigned_picks")
    
    item_sku = models.CharField(max_length=100)
    quantity_to_pick = models.PositiveIntegerField()
    
    # Target specific physical location
    target_bin = models.ForeignKey("inventory.InventoryItem", on_delete=models.PROTECT)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    picked_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Pick {self.item_sku} for Order {self.order_id}"

class PackingTask(models.Model):
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    packer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)