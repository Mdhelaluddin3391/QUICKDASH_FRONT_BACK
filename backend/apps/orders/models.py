from django.conf import settings
from django.db import models
from django.utils import timezone
from apps.warehouse.models import Warehouse
from apps.catalog.models import Product
from decimal import Decimal

User = settings.AUTH_USER_MODEL

class Order(models.Model):
    STATUS_CHOICES = (
        ("created", "Created"),
        ("confirmed", "Confirmed"),
        ("picking", "Picking"),
        ("packed", "Packed"),
        ("out_for_delivery", "Out For Delivery"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
    )

    DELIVERY_TYPE_CHOICES = (
        ("express", "10 Minutes"),
        ("standard", "1–2 Days"),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ("COD", "Cash on Delivery"),
        ("RAZORPAY", "Razorpay"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    warehouse = models.ForeignKey('warehouse.Warehouse', on_delete=models.PROTECT)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="created")
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_TYPE_CHOICES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="COD")

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Snapshot of address at time of order (Preserves history even if user updates profile)
    delivery_address_json = models.JSONField(default=dict, help_text="Snapshot of address")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            # Optimize Warehouse Dashboards
            models.Index(fields=['warehouse', 'status', 'created_at']),
            # Optimize "My Orders" history
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Order #{self.id} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    
    # Denormalized fields to preserve order history even if Catalog changes
    sku = models.CharField(max_length=100)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.sku} x {self.quantity}"


class OrderAbuseLog(models.Model):
    """
    Tracks cancellation abuse to temporarily block users.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cancelled_orders = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_blocked(self):
        return self.blocked_until and self.blocked_until > timezone.now()

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="cart")
    
    # This ensures a cart created in 'Zone A' cannot be checked out in 'Zone B'
    # without re-validation.
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, null=True) 
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.user}) - {self.warehouse.code if self.warehouse else 'No WH'}"

    # ✅ NAYA LOGIC: Sirf items ka total nikalne ke liye
    @property
    def items_total(self):
        return sum(item.total_price for item in self.items.all())

    # ✅ NAYA LOGIC: Dynamic Delivery Fee calculate karne ke liye
    @property
    def delivery_fee(self):
        subtotal = self.items_total
        
        # Agar cart khali hai toh 0 delivery fee
        if subtotal == 0:
            return Decimal('0.00')
            
        # Agar subtotal 200 se kam hai, toh 15 Rs delivery charge, warna Free (0 Rs)
        if subtotal < Decimal('200.00'):
            return Decimal('15.00')
            
        return Decimal('0.00')

    # ✅ NAYA LOGIC: Ab total_amount mein items ka price + delivery fee judega
    @property
    def total_amount(self):
        return self.items_total + self.delivery_fee


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    
    # Link to InventoryItem directly for live stock checks
    sku = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ('cart', 'sku')

    @property
    def total_price(self):
        return self.sku.price * self.quantity