import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon, Point
from django.utils import timezone
from faker import Faker

# Models Import
from apps.catalog.models import Category, Product, Brand, Banner, FlashSale
from apps.warehouse.models import Warehouse, StorageZone, Aisle, Rack, Bin
from apps.inventory.models import InventoryItem
from apps.customers.models import CustomerProfile, CustomerAddress
from apps.orders.models import Order, OrderItem, Cart, CartItem
from apps.riders.models import RiderProfile

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = "Populate database with fake data. Use --warehouse_id to add data to an existing warehouse without deleting old data."

    def add_arguments(self, parser):
        # Optional argument to target a specific warehouse
        parser.add_argument(
            '--warehouse_id', 
            type=int, 
            help='The ID of the specific Warehouse to populate with products'
        )

    def handle(self, *args, **options):
        target_wh_id = options['warehouse_id']

        if target_wh_id:
            self.stdout.write(self.style.WARNING(f"⚠️  Adding data to EXISTING Warehouse ID: {target_wh_id}. Skipping cleanup."))
            try:
                warehouse = Warehouse.objects.get(id=target_wh_id)
                self.stdout.write(self.style.SUCCESS(f"✅ Found Warehouse: {warehouse.name} ({warehouse.code})"))
            except Warehouse.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Warehouse with ID {target_wh_id} not found!"))
                return
        else:
            # Default behavior: Clean DB and create fresh
            self.stdout.write("🧹 Cleaning old data...")
            self._clean_db()
            self.stdout.write("🚀 Starting fresh population...")
            # Create Default Warehouse
            warehouse, _ = self._create_warehouse_structure()

        # 1. Ensure Users Exist (Skip if they exist)
        self._create_users()
        
        # 2. Create Brands (Get or Create)
        brands = self._create_brands()
        
        # 3. Create Catalog (Categories & Products)
        products = self._create_catalog(brands)
        
        # 4. Create Banners & Flash Sales
        self._create_banners(products)
        
        # 5. Ensure Bins Exist for the target warehouse
        bins = self._ensure_bins_exist(warehouse)
        
        # 6. Stock Inventory (Link Products to Warehouse Bins)
        self._stock_inventory(warehouse, products, bins)
        
        # 7. Create Customers & Addresses (Only if creating fresh)
        if not target_wh_id:
            customers = self._create_customers()
            self._create_orders(customers, warehouse, products)
            self._create_carts(customers, warehouse, products)

        self.stdout.write(self.style.SUCCESS("✅ Database populated successfully!"))

    def _clean_db(self):
        # Delete in reverse order of dependency
        Order.objects.all().delete()
        CartItem.objects.all().delete()
        Cart.objects.all().delete()
        InventoryItem.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Brand.objects.all().delete()
        Banner.objects.all().delete()
        FlashSale.objects.all().delete()
        Warehouse.objects.all().delete()
        CustomerAddress.objects.all().delete()
        CustomerProfile.objects.all().delete()
        RiderProfile.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()

    def _create_users(self):
        # Admin
        if not User.objects.filter(email="admin@quickdash.com").exists():
            admin = User.objects.create_user(
                phone="+1234567890",
                email="admin@quickdash.com",
                first_name="Super",
                last_name="Admin",
                password="password",
                is_staff=True,
                is_superuser=True,
                is_active=True
            )
            admin.set_password("admin123")
            admin.save()
        
        # Rider
        if not User.objects.filter(email="rider@quickdash.com").exists():
            rider_user = User.objects.create_user(
                phone="+1234567891",
                email="rider@quickdash.com", 
                password="password", 
                first_name="Raju", 
                last_name="Rider"
            )
            RiderProfile.objects.create(user=rider_user, is_active=True)

    def _create_brands(self):
        brands = []
        brand_names = ["Nestle", "Amul", "Britannia", "Coca-Cola", "Pepsi", "Haldiram's", "Parle", "ITC"]
        for name in brand_names:
            b, created = Brand.objects.get_or_create(
                name=name,
                defaults={'slug': fake.slug(), 'is_active': True}
            )
            brands.append(b)
        self.stdout.write(f"   - Brands ready: {len(brands)}")
        return brands

    def _create_catalog(self, brands):
        categories = []
        cat_names = ["Dairy & Bread", "Vegetables", "Snacks & Chips", "Beverages", "Instant Food", "Fruits", "Bakery", "Household"]
        
        for name in cat_names:
            c, created = Category.objects.get_or_create(
                name=name,
                defaults={'slug': fake.slug(), 'icon': "https://placehold.co/100x100/png", 'is_active': True}
            )
            categories.append(c)
            
        products = []
        self.stdout.write("   - Creating new products...")
        for _ in range(50): 
            cat = random.choice(categories)
            brand = random.choice(brands) if random.random() > 0.3 else None
            p = Product.objects.create(
                category=cat,
                brand=brand,
                name=f"{fake.word().capitalize()} {fake.word()} {random.randint(1,999)}", 
                sku=fake.unique.ean13(),
                description=fake.sentence(),
                mrp=Decimal(random.randint(20, 500)),
                image="https://placehold.co/400x400/png", 
                is_active=True
            )
            products.append(p)
        return products

    def _create_banners(self, products):
        if Banner.objects.count() < 5:
            for _ in range(3):
                Banner.objects.create(
                    title=fake.sentence()[:50],
                    image="https://placehold.co/800x400/png",
                    target_url="/products",
                    position=random.choice(['HERO', 'MID']),
                    is_active=True
                )
        
    def _create_warehouse_structure(self):
        coords = (
            (77.5800, 12.9600), (77.6500, 12.9600), 
            (77.6500, 13.0000), (77.5800, 13.0000), 
            (77.5800, 12.9600)
        )
        poly = Polygon(coords)

        wh = Warehouse.objects.create(
            name="Bengaluru Central",
            code="BLR-001",
            warehouse_type="dark_store",
            city="Bengaluru",
            state="Karnataka",
            location=Point(77.5946, 12.9716), 
            delivery_zone=poly,
            is_active=True
        )
        return wh, None 

    def _ensure_bins_exist(self, warehouse):
        bins = list(Bin.objects.filter(rack__aisle__zone__warehouse=warehouse))
        if not bins:
            self.stdout.write(f"   - Creating storage structure for {warehouse.name}")
            zone, _ = StorageZone.objects.get_or_create(warehouse=warehouse, name="Ambient Zone")
            aisle, _ = Aisle.objects.get_or_create(zone=zone, number="1")
            rack, _ = Rack.objects.get_or_create(aisle=aisle, number="1")
            
            for i in range(1, 21):
                b = Bin.objects.create(rack=rack, bin_code=f"{warehouse.code}-Z1-A1-R1-B{i:02d}", capacity_units=100)
                bins.append(b)
        else:
            self.stdout.write(f"   - Using {len(bins)} existing bins from {warehouse.name}")
        return bins

    def _stock_inventory(self, warehouse, products, bins):
        count = 0
        for product in products:
            _bin = random.choice(bins)
            if not InventoryItem.objects.filter(sku=product.sku, bin__rack__aisle__zone__warehouse=warehouse).exists():
                InventoryItem.objects.create(
                    sku=product.sku,
                    bin=_bin,
                    product_name=product.name,
                    price=product.mrp,
                    total_stock=random.randint(10, 100),
                    mode="owned"
                )
                count += 1
        self.stdout.write(f"   - Added {count} new inventory items to {warehouse.name}")

    def _create_customers(self):
        customers = []
        for _ in range(20):
            phone = fake.phone_number()[:15]
            if not User.objects.filter(phone=phone).exists():
                u = User.objects.create_user(
                    phone=phone,
                    email=fake.email(), 
                    password="password", 
                    first_name=fake.first_name(),
                    last_name=fake.last_name()
                )
                cust_profile = CustomerProfile.objects.create(user=u)
                CustomerAddress.objects.create(
                    customer=cust_profile,
                    house_no=str(random.randint(1, 100)),
                    apartment_name=fake.company(),
                    google_address_text="Indiranagar, Bengaluru",
                    latitude=12.9720 + random.uniform(-0.01, 0.01),
                    longitude=77.5950 + random.uniform(-0.01, 0.01),
                    city="Bengaluru",
                    pincode="560038"
                )
                customers.append(u)
        self.stdout.write(f"   - Created new Customers")
        return customers

    def _create_orders(self, customers, warehouse, products):
        status_choices = ["created", "confirmed", "packed", "out_for_delivery", "delivered"]
        for i in range(20):
            user = random.choice(customers)
            if hasattr(user, 'customer_profile') and user.customer_profile.addresses.exists():
                address = user.customer_profile.addresses.first()
                addr_snapshot = {
                    "id": address.id,
                    "full_address": address.google_address_text,
                    "lat": float(address.latitude),
                    "lng": float(address.longitude)
                }
                order = Order.objects.create(
                    user=user,
                    warehouse=warehouse,
                    status=random.choice(status_choices),
                    delivery_type=random.choice(["express", "standard"]),
                    total_amount=Decimal(0),
                    delivery_address_json=addr_snapshot,
                    payment_method=random.choice(["COD", "RAZORPAY"])
                )
                total = 0
                for _ in range(random.randint(1, 5)):
                    prod = random.choice(products)
                    qty = random.randint(1, 3)
                    price = prod.mrp
                    OrderItem.objects.create(
                        order=order,
                        sku=prod.sku,
                        product_name=prod.name,
                        quantity=qty,
                        price=price
                    )
                    total += (price * qty)
                order.total_amount = total
                order.save()

    def _create_carts(self, customers, warehouse, products):
        for user in customers[:5]:
            cart, _ = Cart.objects.get_or_create(user=user, warehouse=warehouse)
            cart_products = random.sample(products, random.randint(1, 3))
            for prod in cart_products:
                inv_item = InventoryItem.objects.filter(sku=prod.sku).first()
                if inv_item:
                    CartItem.objects.create(
                        cart=cart,
                        sku=inv_item,
                        quantity=random.randint(1, 2)
                    )