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
from apps.notifications.models import Notification  # Assuming it exists
from apps.payments.models import Payment  # Assuming it exists

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = "Populate database with comprehensive fake data for testing"

    def handle(self, *args, **kwargs):
        self.stdout.write("🧹 Cleaning old data...")
        self._clean_db()
        
        self.stdout.write("🚀 Starting population...")
        
        # 1. Create Superuser & Users
        admin = self._create_users()
        
        # 2. Create Brands
        brands = self._create_brands()
        
        # 3. Create Catalog (Categories & Products)
        products = self._create_catalog(brands)
        
        # 4. Create Banners & Flash Sales
        self._create_banners(products)
        
        # 5. Create Warehouse & Storage
        warehouse, bins = self._create_warehouse_structure()
        
        # 6. Stock Inventory (Link Products to Warehouse Bins)
        self._stock_inventory(warehouse, products, bins)
        
        # 7. Create Customers & Addresses
        customers = self._create_customers()
        
        # 8. Create Dummy Orders & Payments
        self._create_orders(customers, warehouse, products)

        # 9. Create Carts
        self._create_carts(customers, warehouse, products)

        self.stdout.write(self.style.SUCCESS("✅ Database populated successfully!"))
        self.stdout.write(self.style.WARNING(f"👉 Admin Login: admin@quickdash.com / admin123"))

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
        admin, _ = User.objects.get_or_create(
            phone="+1234567890",
            defaults={
                "email": "admin@quickdash.com",
                "first_name": "Super",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True
            }
        )
        admin.set_password("admin123")
        admin.save()
        
        # Rider
        rider_user = User.objects.create_user(
            phone="+1234567891",
            email="rider@quickdash.com", 
            password="password", 
            first_name="Raju", 
            last_name="Rider"
        )
        RiderProfile.objects.create(user=rider_user, is_active=True)
        
        return admin

    def _create_brands(self):
        brands = []
        brand_names = ["Nestle", "Amul", "Britannia", "Coca-Cola", "Pepsi", "Haldiram's", "Parle", "ITC"]
        for name in brand_names:
            b = Brand.objects.create(
                name=name,
                slug=fake.slug(),
                is_active=True
            )
            brands.append(b)
        self.stdout.write(f"   - Created {len(brands)} Brands")
        return brands

    def _create_catalog(self, brands):
        categories = []
        cat_names = ["Dairy & Bread", "Vegetables", "Snacks & Chips", "Beverages", "Instant Food", "Fruits", "Bakery", "Household"]
        
        for name in cat_names:
            c = Category.objects.create(
                name=name,
                slug=fake.slug(),
                icon="https://placehold.co/100x100/png", # Dummy Image
                is_active=True
            )
            categories.append(c)
            
        products = []
        for _ in range(100): # Create 100 products
            cat = random.choice(categories)
            brand = random.choice(brands) if random.random() > 0.3 else None
            p = Product.objects.create(
                category=cat,
                brand=brand,
                name=f"{fake.word().capitalize()} {fake.word()}",
                sku=fake.unique.ean13(),
                description=fake.sentence(),
                mrp=Decimal(random.randint(20, 500)),
                image="https://placehold.co/400x400/png", # Dummy Image
                is_active=True
            )
            products.append(p)
        
        self.stdout.write(f"   - Created {len(categories)} Categories and {len(products)} Products")
        return products

    def _create_banners(self, products):
        banners = []
        for _ in range(5):
            b = Banner.objects.create(
                title=fake.sentence()[:50],
                image="https://placehold.co/800x400/png",
                target_url="/products",
                position=random.choice(['HERO', 'MID']),
                is_active=True
            )
            banners.append(b)
        
        # Flash Sales for 10 random products
        flash_products = random.sample(products, 10)
        for prod in flash_products:
            FlashSale.objects.create(
                product=prod,
                discount_percentage=random.randint(10, 50),
                end_time=timezone.now() + timezone.timedelta(days=random.randint(1, 7)),
                is_active=True
            )
        
        self.stdout.write(f"   - Created {len(banners)} Banners and {len(flash_products)} Flash Sales")

    def _create_warehouse_structure(self):
        # Create a Polygon for Bengaluru (Indiranagar/Domlur area)
        # This ensures current location works if you simulate location there
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
            location=Point(77.5946, 12.9716),  # longitude, latitude
            delivery_zone=poly,
            is_active=True
        )

        # Create Storage Hierarchy
        zone = StorageZone.objects.create(warehouse=wh, name="Ambient Zone")
        aisle = Aisle.objects.create(zone=zone, number="1")
        rack = Rack.objects.create(aisle=aisle, number="1")
        
        bins = []
        for i in range(1, 21):  # More bins
            b = Bin.objects.create(rack=rack, bin_code=f"BLR001-Z1-A1-R1-B{i:02d}", capacity_units=100)
            bins.append(b)
            
        self.stdout.write(f"   - Created Warehouse {wh.name} with {len(bins)} storage bins")
        return wh, bins

    def _stock_inventory(self, warehouse, products, bins):
        for product in products:
            # Add item to a random bin
            _bin = random.choice(bins)
            InventoryItem.objects.create(
                sku=product.sku,  # Use product's SKU
                bin=_bin,
                product_name=product.name,
                price=product.mrp,
                total_stock=random.randint(10, 100),
                mode="owned"
            )
        self.stdout.write(f"   - Stocked inventory for all products")

    def _create_customers(self):
        customers = []
        for _ in range(20):  # More customers
            phone = fake.phone_number()[:15]
            u = User.objects.create_user(
                phone=phone,
                email=fake.email(), 
                password="password", 
                first_name=fake.first_name(),
                last_name=fake.last_name()
            )
            cust_profile = CustomerProfile.objects.create(user=u)
            
            # Add Address inside the Delivery Zone
            CustomerAddress.objects.create(
                customer=cust_profile,
                house_no=str(random.randint(1, 100)),
                apartment_name=fake.company(),
                google_address_text="Indiranagar, Bengaluru",
                latitude=12.9720 + random.uniform(-0.01, 0.01),
                longitude=77.5950 + random.uniform(-0.01, 0.01), # Inside zone
                city="Bengaluru",
                pincode="560038"
            )
            customers.append(u)
        self.stdout.write(f"   - Created {len(customers)} Customers")
        return customers

    def _create_orders(self, customers, warehouse, products):
        status_choices = ["created", "confirmed", "packed", "out_for_delivery", "delivered"]
        
        for i in range(50):  # More orders
            user = random.choice(customers)
            # Find user address
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
            
            # Add items
            total = 0
            for _ in range(random.randint(1, 5)):
                prod = random.choice(products)
                qty = random.randint(1, 3)
                price = prod.mrp  # Fixed: use mrp instead of price
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
            
        self.stdout.write(f"   - Created 50 dummy orders")

    def _create_carts(self, customers, warehouse, products):
        for user in customers[:10]:  # Carts for first 10 customers
            cart = Cart.objects.create(user=user, warehouse=warehouse)
            # Add random items
            cart_products = random.sample(products, random.randint(1, 3))
            for prod in cart_products:
                inv_item = InventoryItem.objects.filter(sku=prod.sku).first()
                if inv_item:
                    CartItem.objects.create(
                        cart=cart,
                        sku=inv_item,
                        quantity=random.randint(1, 2)
                    )
        self.stdout.write(f"   - Created carts for 10 customers")