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
        ("packed_at_hub", "Packed at Mega Hub"),
        ("in_transit_to_local", "In Transit to Dark Store"),
        ("received_at_local", "Received at Dark Store"),
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

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="orders")
    
    fulfillment_warehouse = models.ForeignKey('warehouse.Warehouse', on_delete=models.PROTECT, related_name="fulfilled_orders", null=True, blank=True)
    last_mile_warehouse = models.ForeignKey('warehouse.Warehouse', on_delete=models.PROTECT, related_name="last_mile_orders", null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="created", db_index=True)
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_TYPE_CHOICES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default="COD")

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_address_json = models.JSONField(default=dict)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['fulfillment_warehouse', 'status', 'created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Order #{self.id} ({self.status})"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    
    sku = models.CharField(max_length=100, db_index=True)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    cancel_reason = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.sku} x {self.quantity} - {self.status}"

class OrderAbuseLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    cancelled_orders = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_blocked(self):
        return self.blocked_until and self.blocked_until > timezone.now()

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, related_name="cart")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.user}) - {self.warehouse.code if self.warehouse else 'No WH'}"

    @property
    def total_amount(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def delivery_fee(self):
        config = OrderConfiguration.objects.first()
        fee = config.delivery_fee if config else Decimal("5.00")
        threshold = config.free_delivery_threshold if config else Decimal("100.00")
        
        if self.total_amount >= threshold:
            return Decimal("0.00")
        return fee

    @property
    def final_total(self):
        return self.total_amount + self.delivery_fee

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    sku = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ('cart', 'sku')

    @property
    def total_price(self):
        return self.sku.price * self.quantity

class OrderConfiguration(models.Model):
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=2, default=5.00)
    free_delivery_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    
    def __str__(self):
        return "Order & Delivery Configuration"

    class Meta:
        verbose_name = "Order Configuration"
        verbose_name_plural = "Order Configurations"

class OrderItemFulfillment(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="fulfillments")
    inventory_batch = models.ForeignKey('inventory.InventoryItem', on_delete=models.PROTECT, related_name="order_fulfillments")
    quantity_allocated = models.PositiveIntegerField()
    vendor_payable_amount = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity_allocated}x {self.order_item.sku} from Batch #{self.inventory_batch.id}"