import random
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from django.db import transaction
from django.contrib.gis.geos import Point, Polygon
from faker import Faker

# Models Import
from apps.catalog.models import Category, Brand, Product, Banner, FlashSale
from apps.locations.models import GeoLocation
from apps.warehouse.models import Warehouse, StorageZone, Aisle, Rack, Bin
from apps.inventory.models import InventoryItem

class Command(BaseCommand):
    help = "Generates COMPLETE production-grade fake data (Catalog + Warehouse + Inventory) for full app functionality."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("🚀 Starting Full Data Reset & Generation..."))

        fake = Faker()
        Faker.seed(42)
        random.seed(42)

        # ------------------------------------------------------------------
        # Helpers
        # ------------------------------------------------------------------
        def field_max(model, field):
            return model._meta.get_field(field).max_length or 255

        def safe_text(text, max_len):
            return text[:max_len] if text else ""

        def safe_slug(model, name):
            max_len = field_max(model, "slug")
            base = slugify(name)[: max_len - 6] or "item"
            slug = base
            if model.objects.filter(slug=slug).exists():
                slug = f"{base}-{random.randint(1000,9999)}"
            return slug[:max_len]

        def unique_sku():
            while True:
                sku = f"SKU-{random.randint(10**7, 10**8 - 1)}"
                if not Product.objects.filter(sku=sku).exists():
                    return sku

        # ------------------------------------------------------------------
        # MAIN EXECUTION (Atomic)
        # ------------------------------------------------------------------
        with transaction.atomic():
            # 1. CLEANUP (Order matters to avoid ForeignKey errors)
            self.stdout.write("🧹 Clearing old data...")
            FlashSale.objects.all().delete()
            InventoryItem.objects.all().delete()
            Bin.objects.all().delete()
            Rack.objects.all().delete()
            Aisle.objects.all().delete()
            StorageZone.objects.all().delete()
            Warehouse.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()
            Banner.objects.all().delete()
            GeoLocation.objects.all().delete()

            # ------------------------------------------------------------------
            # 2. CATALOG DATA (Brands, Categories, Products)
            # ------------------------------------------------------------------
            self.stdout.write("📦 Generating Catalog (Brands, Categories, Products)...")
            
            # Brands
            brands = []
            for _ in range(10):
                name = safe_text(fake.company(), field_max(Brand, "name"))
                brands.append(Brand.objects.create(name=name, slug=safe_slug(Brand, name), is_active=True))

            # Categories (Parent -> Child -> Grandchild)
            all_categories = []
            for _ in range(5): # 5 Top level categories
                parent_name = fake.word().capitalize()
                parent = Category.objects.create(
                    name=safe_text(parent_name, field_max(Category, "name")),
                    slug=safe_slug(Category, parent_name),
                    is_active=True
                )
                all_categories.append(parent)

                for _ in range(3): # 3 Sub-categories each
                    child_name = fake.color_name()
                    child = Category.objects.create(
                        name=safe_text(child_name, field_max(Category, "name")),
                        slug=safe_slug(Category, child_name),
                        parent=parent,
                        is_active=True
                    )
                    all_categories.append(child)

            # Products
            products = []
            for cat in all_categories:
                # Add 5 products per category
                for _ in range(5):
                    pname = f"{fake.word().capitalize()} {fake.word().capitalize()}"
                    products.append(Product.objects.create(
                        category=cat,
                        brand=random.choice(brands),
                        name=safe_text(pname, field_max(Product, "name")),
                        description=fake.text(max_nb_chars=120),
                        sku=unique_sku(),
                        unit="1 Unit",
                        mrp=random.randint(100, 5000),
                        is_active=True,
                    ))

            # ------------------------------------------------------------------
            # 3. WAREHOUSE & LOCATION (Crucial for Home Page)
            # ------------------------------------------------------------------
            self.stdout.write("yah  Generating Warehouse & Delivery Zone...")

            # Create Warehouse in Bengaluru (Default Test Location)
            # Center: 12.9716, 77.5946
            wh_code = "BLR-01"
            warehouse = Warehouse.objects.create(
                name="Bengaluru Main Store",
                code=wh_code,
                warehouse_type="dark_store",
                city="Bengaluru",
                state="Karnataka",
                location=Point(77.5946, 12.9716),
                is_active=True
            )

            # Create Delivery Zone (20km Box around center)
            lat, lng = 12.9716, 77.5946
            delta = 0.1  # Approx 10km radius coverage
            warehouse.delivery_zone = Polygon([
                (lng - delta, lat - delta),
                (lng + delta, lat - delta),
                (lng + delta, lat + delta),
                (lng - delta, lat + delta),
                (lng - delta, lat - delta)
            ])
            warehouse.save()

            # Physical Layout (Zone -> Aisle -> Rack -> Bin)
            zone = StorageZone.objects.create(warehouse=warehouse, name="General Storage")
            aisle = Aisle.objects.create(zone=zone, number="A1")
            rack = Rack.objects.create(aisle=aisle, number="R1")
            # Create a main Bin for all items
            main_bin = Bin.objects.create(rack=rack, bin_code=f"{wh_code}-GEN-01")

            # ------------------------------------------------------------------
            # 4. INVENTORY (Linking Products to Warehouse)
            # ------------------------------------------------------------------
            self.stdout.write("📊 Adding Stock (Inventory) for ALL products...")
            
            # Har product ke liye stock add karein taaki woh Home Page par dikhe
            inventory_count = 0
            for product in products:
                InventoryItem.objects.create(
                    bin=main_bin,
                    sku=product.sku,
                    product_name=product.name,
                    price=product.mrp,
                    total_stock=random.randint(50, 500), # Full stock
                    reserved_stock=0,
                    mode="owned"
                )
                inventory_count += 1

            # ------------------------------------------------------------------
            # 5. MARKETING (Banners & Flash Sales)
            # ------------------------------------------------------------------
            self.stdout.write("🎉 Generating Banners & Offers...")

            # Flash Sales
            for prod in random.sample(products, min(10, len(products))):
                FlashSale.objects.create(
                    product=prod,
                    discount_percentage=random.randint(10, 50),
                    end_time=timezone.now() + timezone.timedelta(days=7),
                    is_active=True
                )

            # Banners
            for i in range(3):
                Banner.objects.create(
                    title=f"Big Sale Offer {i + 1}",
                    position="HERO",
                    target_url="/", # Leads to home
                    bg_gradient=f"linear-gradient(to right, {fake.hex_color()}, {fake.hex_color()})"[:50],
                    is_active=True
                )

        # ------------------------------------------------------------------
        # DONE
        # ------------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS(f"✔ SUCCESS! Data Generated:"))
        self.stdout.write(f"  - Products: {len(products)}")
        self.stdout.write(f"  - Warehouse: {warehouse.name} (with Stock)")
        self.stdout.write(f"  - Inventory Items: {inventory_count}")
        self.stdout.write("frontend refresh karke 'Bengaluru' location select karein.")