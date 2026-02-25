from django.db import models


class Brand(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    logo = models.URLField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
class Category(models.Model):
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='subcategories'
    )
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.URLField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    image = models.URLField(max_length=500, null=True, blank=True)
    
    unit = models.CharField(max_length=50, default="1 Unit")
    
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.sku})"



class Banner(models.Model):
    POSITION_CHOICES = (('HERO', 'Hero Slider'), ('MID', 'Mid Section'))
    
    title = models.CharField(max_length=100)
    image = models.URLField(max_length=500)
    target_url = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='HERO')
    bg_gradient = models.CharField(max_length=50, default="linear-gradient(to right, #333, #000)")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class FlashSale(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="flash_sale")
    discount_percentage = models.PositiveIntegerField(help_text="Discount in %")
    end_time = models.DateTimeField(help_text="Sale ends at")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} ({self.discount_percentage}% OFF)"