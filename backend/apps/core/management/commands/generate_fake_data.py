import random
import string
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from django.db import transaction, IntegrityError
from faker import Faker

from apps.catalog.models import Category, Brand, Product, Banner, FlashSale
from apps.locations.models import GeoLocation


class Command(BaseCommand):
    help = "Generates SAFE, production-grade fake data without breaking backend constraints."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Resetting fake data (safe mode)..."))

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
        # Atomic operation (NO PARTIAL DATA)
        # ------------------------------------------------------------------

        with transaction.atomic():
            FlashSale.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()
            Banner.objects.all().delete()
            GeoLocation.objects.all().delete()

            self.stdout.write(self.style.SUCCESS("Old data cleared."))

            # ------------------------------------------------------------------
            # Brands
            # ------------------------------------------------------------------
            brands = []
            for _ in range(20):
                name = safe_text(fake.company(), field_max(Brand, "name"))
                brands.append(
                    Brand.objects.create(
                        name=name,
                        slug=safe_slug(Brand, name),
                        is_active=True,
                    )
                )

            # ------------------------------------------------------------------
            # Categories (3-Level Tree)
            # ------------------------------------------------------------------
            categories = []

            for _ in range(20):
                parent_name = fake.word().capitalize()
                parent = Category.objects.create(
                    name=safe_text(parent_name, field_max(Category, "name")),
                    slug=safe_slug(Category, parent_name),
                    is_active=True,
                )
                categories.append(parent)

                for _ in range(3):
                    child_name = fake.color_name()
                    child = Category.objects.create(
                        name=safe_text(child_name, field_max(Category, "name")),
                        slug=safe_slug(Category, child_name),
                        parent=parent,
                        is_active=True,
                    )
                    categories.append(child)

                    for _ in range(2):
                        gname = fake.word().capitalize()
                        categories.append(
                            Category.objects.create(
                                name=safe_text(gname, field_max(Category, "name")),
                                slug=safe_slug(Category, gname),
                                parent=child,
                                is_active=True,
                            )
                        )

            # ------------------------------------------------------------------
            # Products
            # ------------------------------------------------------------------
            products = []

            for cat in categories:
                for _ in range(20):
                    pname = f"{fake.word().capitalize()} {fake.word().capitalize()}"
                    products.append(
                        Product.objects.create(
                            category=cat,
                            brand=random.choice(brands),
                            name=safe_text(pname, field_max(Product, "name")),
                            description=fake.text(max_nb_chars=120),
                            sku=unique_sku(),
                            unit="1 Unit",
                            mrp=random.randint(100, 5000),
                            is_active=True,
                        )
                    )

            # ------------------------------------------------------------------
            # Flash Sales
            # ------------------------------------------------------------------
            for prod in random.sample(products, min(50, len(products))):
                FlashSale.objects.create(
                    product=prod,
                    discount_percentage=random.randint(10, 70),
                    end_time=timezone.now()
                    + timezone.timedelta(days=random.randint(1, 7)),
                    is_active=True,
                )

            # ------------------------------------------------------------------
            # Banners (50-char safe)
            # ------------------------------------------------------------------
            for i in range(5):
                Banner.objects.create(
                    title=f"Offer {i + 1}",
                    position="HERO",
                    target_url="/",
                    bg_gradient=f"linear-gradient(to right, {fake.hex_color()}, {fake.hex_color()})"[:50],
                    is_active=True,
                )

            # ------------------------------------------------------------------
            # GeoLocations
            # ------------------------------------------------------------------
            for _ in range(10):
                GeoLocation.objects.create(
                    label=fake.city()[:100],
                    address_text=fake.address()[:255],
                    latitude=fake.latitude(),
                    longitude=fake.longitude(),
                )

        self.stdout.write(self.style.SUCCESS("✔ SAFE FAKE DATA GENERATED SUCCESSFULLY"))
