import random
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point, Polygon
from django.db import transaction
from apps.warehouse.models import Warehouse, StorageZone, Aisle, Rack, Bin
from apps.catalog.models import Product
from apps.inventory.models import InventoryItem

class Command(BaseCommand):
    help = "Sets up a Demo Warehouse in Bengaluru with Inventory for all products"

    def handle(self, *args, **options):
        self.stdout.write("🏗️  Setting up Demo Store...")

        with transaction.atomic():
            # 1. Create Warehouse (Bengaluru Coordinates)
            # Frontend Default: 12.9716, 77.5946
            # We create a large zone around it.
            wh_code = "BLR-01"
            warehouse, created = Warehouse.objects.get_or_create(
                code=wh_code,
                defaults={
                    "name": "Bengaluru Dark Store",
                    "warehouse_type": "dark_store",
                    "city": "Bengaluru",
                    "state": "Karnataka",
                    "location": Point(77.5946, 12.9716),
                    "is_active": True
                }
            )
            
            # Create a 20km box polygon around the center
            lat, lng = 12.9716, 77.5946
            delta = 0.1  # Approx 10km
            warehouse.delivery_zone = Polygon([
                (lng - delta, lat - delta),
                (lng + delta, lat - delta),
                (lng + delta, lat + delta),
                (lng - delta, lat + delta),
                (lng - delta, lat - delta)
            ])
            warehouse.save()
            
            if created:
                self.stdout.write(f"✅ Created Warehouse: {warehouse.name}")
            else:
                self.stdout.write(f"ℹ️  Using existing Warehouse: {warehouse.name}")

            # 2. Create Physical Layout (Zone -> Aisle -> Rack -> Bin)
            zone, _ = StorageZone.objects.get_or_create(warehouse=warehouse, name="General")
            aisle, _ = Aisle.objects.get_or_create(zone=zone, number="A1")
            rack, _ = Rack.objects.get_or_create(aisle=aisle, number="R1")
            bin_obj, _ = Bin.objects.get_or_create(rack=rack, bin_code=f"{wh_code}-Z1-A1-R1-B1")

            # 3. Add Inventory for ALL Products
            products = Product.objects.filter(is_active=True)
            if not products.exists():
                self.stdout.write(self.style.ERROR("❌ No products found! Run 'generate_fake_data' first."))
                return

            count = 0
            for product in products:
                # InventoryItem create karein (agar nahi hai)
                item, created = InventoryItem.objects.get_or_create(
                    sku=product.sku,
                    bin=bin_obj,
                    defaults={
                        "product_name": product.name,
                        "price": product.mrp,
                        "total_stock": random.randint(50, 200),
                        "reserved_stock": 0
                    }
                )
                if not created:
                    # Stock refresh karein
                    item.total_stock = random.randint(50, 200)
                    item.save()
                count += 1

            self.stdout.write(self.style.SUCCESS(f"✅ Stock added for {count} products in {warehouse.name}"))
            self.stdout.write(self.style.SUCCESS("🚀 System is ready! Frontend refresh karein."))