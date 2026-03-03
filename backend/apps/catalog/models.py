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
    sort_order = models.IntegerField(default=0, help_text="Lower number comes first (e.g. 1 for Grocery, 2 for Electronics)")

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['sort_order', 'name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    

class Product(models.Model):
    DIETARY_CHOICES = (
        ('VEG', 'Vegetarian (Green Dot)'),
        ('NON_VEG', 'Non-Vegetarian (Red Dot)'),
        ('VEGAN', 'Vegan'),
        ('EGG', 'Contains Egg'),
        ('NONE', 'Not Applicable (e.g., Electronics/Cleaning)'),
    )

    TAX_RATE_CHOICES = (
        (0.00, '0% GST'),
        (5.00, '5% GST'),
        (12.00, '12% GST'),
        (18.00, '18% GST'),
        (28.00, '28% GST'),
    )

    # --- 1. Basic Linking ---
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products", null=True, blank=True)
    
    # --- 2. Core Information ---
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=100, unique=True, db_index=True, help_text="Barcode / EAN / UPC")
    image = models.URLField(max_length=500, null=True, blank=True)
    unit = models.CharField(max_length=50, default="1 Unit", help_text="Display text, e.g., '1 Kg', '500 g'")
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    
    # --- 3. Customer Experience & Health (NEW) ---
    dietary_preference = models.CharField(max_length=20, choices=DIETARY_CHOICES, default='NONE')
    allergens = models.CharField(max_length=255, blank=True, null=True, help_text="e.g., 'Contains Peanuts, Soy, Milk'")
    shelf_life = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., 'Best before 6 months from manufacture'")
    nutri_score = models.CharField(max_length=5, blank=True, null=True, help_text="Grade: A, B, C, D, E")
    eco_score = models.CharField(max_length=5, blank=True, null=True, help_text="Grade: A, B, C, D, E")
    search_tags = models.TextField(blank=True, null=True, help_text="Comma separated keywords for better searching")

    # --- 4. Logistics & Fulfillment (NEW) ---
    weight_in_grams = models.PositiveIntegerField(blank=True, null=True, help_text="Used to calculate rider bag capacity")
    packaging_type = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Plastic Packet, Glass Bottle, Cardboard")
    is_returnable = models.BooleanField(default=False, help_text="Can the customer return this item?")
    max_order_quantity = models.PositiveIntegerField(default=10, help_text="Max items a customer can buy in one order")

    # --- 5. Billing & Legal (NEW) ---
    hsn_code = models.CharField(max_length=20, blank=True, null=True, help_text="HSN / SAC Code for GST Billing")
    tax_rate = models.DecimalField(max_digits=4, decimal_places=2, choices=TAX_RATE_CHOICES, default=0.00)

    # --- 6. Status & Timestamps ---
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