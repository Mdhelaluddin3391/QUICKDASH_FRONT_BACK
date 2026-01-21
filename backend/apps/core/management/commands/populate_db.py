import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon, Point
from django.utils import timezone
from faker import Faker

# Models Import
from apps.catalog.models import Category, Product
from apps.warehouse.models import Warehouse, StorageZone, Aisle, Rack, Bin
from apps.inventory.models import InventoryItem
from apps.customers.models import CustomerProfile, CustomerAddress
from apps.orders.models import Order, OrderItem
from apps.riders.models import RiderProfile

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
        
        # 2. Create Catalog (Categories & Products)
        products = self._create_catalog()
        
        # 3. Create Warehouse & Storage
        warehouse, bins = self._create_warehouse_structure()
        
        # 4. Stock Inventory (Link Products to Warehouse Bins)
        self._stock_inventory(warehouse, products, bins)
        
        # 5. Create Customers & Addresses
        customers = self._create_customers()
        
        # 6. Create Dummy Orders
        self._create_orders(customers, warehouse, products)

        self.stdout.write(self.style.SUCCESS("✅ Database populated successfully!"))
        self.stdout.write(self.style.WARNING(f"👉 Admin Login: admin@quickdash.com / admin123"))

    def _clean_db(self):
        # Delete in reverse order of dependency
        Order.objects.all().delete()
        InventoryItem.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Warehouse.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()

    def _create_users(self):
        # Admin
        admin, _ = User.objects.get_or_create(
            email="admin@quickdash.com",
            defaults={
                "username": "admin",
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
            email="rider@quickdash.com", 
            password="password", 
            first_name="Raju", 
            last_name="Rider"
        )
        RiderProfile.objects.create(user=rider_user, is_active=True, is_verified=True)
        
        return admin

    def _create_catalog(self):
        categories = []
        cat_names = ["Dairy & Bread", "Vegetables", "Snacks & Chips", "Beverages", "Instant Food"]
        
        for name in cat_names:
            c = Category.objects.create(
                name=name,
                slug=fake.slug(),
                description=fake.text(),
                image="https://placehold.co/100x100/png", # Dummy Image
                is_active=True
            )
            categories.append(c)
            
        products = []
        for _ in range(30): # Create 30 products
            cat = random.choice(categories)
            p = Product.objects.create(
                category=cat,
                name=f"{fake.word().capitalize()} {fake.word()}",
                slug=fake.unique.slug(),
                description=fake.sentence(),
                price=Decimal(random.randint(20, 500)),
                mrp=Decimal(random.randint(501, 700)),
                image="https://placehold.co/400x400/png", # Dummy Image
                is_active=True
            )
            products.append(p)
        
        self.stdout.write(f"   - Created {len(categories)} Categories and {len(products)} Products")
        return products

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
            address="Indiranagar, Bengaluru",
            latitude=12.9716,
            longitude=77.5946,
            delivery_zone=poly,
            is_active=True
        )

        # Create Storage Hierarchy
        zone = StorageZone.objects.create(warehouse=wh, name="Ambient Zone", code="Z1")
        aisle = Aisle.objects.create(zone=zone, name="Aisle 1", code="A1")
        rack = Rack.objects.create(aisle=aisle, name="Rack 1", code="R1")
        
        bins = []
        for i in range(1, 11):
            b = Bin.objects.create(rack=rack, name=f"Bin {i}", code=f"B{i}")
            bins.append(b)
            
        self.stdout.write(f"   - Created Warehouse {wh.name} with storage bins")
        return wh, bins

    def _stock_inventory(self, warehouse, products, bins):
        for product in products:
            # Add item to a random bin
            _bin = random.choice(bins)
            InventoryItem.objects.create(
                sku=f"SKU-{product.id}",
                bin=_bin,
                product=product,
                quantity=random.randint(10, 100),
                batch_number=fake.ean8(),
                expiry_date=timezone.now() + timezone.timedelta(days=365)
            )
        self.stdout.write(f"   - Stocked inventory for all products")

    def _create_customers(self):
        customers = []
        for _ in range(5):
            u = User.objects.create_user(
                email=fake.email(), 
                password="password", 
                first_name=fake.first_name()
            )
            cust_profile = CustomerProfile.objects.create(user=u, phone=fake.phone_number()[:10])
            
            # Add Address inside the Delivery Zone
            CustomerAddress.objects.create(
                customer=cust_profile,
                house_no=str(random.randint(1, 100)),
                apartment_name="Test Apt",
                google_address_text="Indiranagar, Bengaluru",
                latitude=12.9720,
                longitude=77.5950, # Inside zone
                city="Bengaluru",
                pincode="560038"
            )
            customers.append(u)
        return customers

    def _create_orders(self, customers, warehouse, products):
        status_choices = ["created", "packed", "out_for_delivery", "delivered"]
        
        for i in range(10):
            user = random.choice(customers)
            # Find user address
            address = user.customer_profile.addresses.first()
            
            addr_snapshot = {
                "id": address.id,
                "full_address": address.google_address_text,
                "lat": address.latitude,
                "lng": address.longitude
            }

            order = Order.objects.create(
                user=user,
                warehouse=warehouse,
                status=random.choice(status_choices),
                delivery_type="express",
                total_amount=Decimal(0),
                delivery_address_json=addr_snapshot,
                payment_method="COD"
            )
            
            # Add items
            total = 0
            for _ in range(random.randint(1, 4)):
                prod = random.choice(products)
                qty = random.randint(1, 3)
                price = prod.price
                OrderItem.objects.create(
                    order=order,
                    sku=f"SKU-{prod.id}",
                    product_name=prod.name,
                    quantity=qty,
                    price=price
                )
                total += (price * qty)
            
            order.total_amount = total
            order.save()
            
        self.stdout.write(f"   - Created 10 dummy orders")