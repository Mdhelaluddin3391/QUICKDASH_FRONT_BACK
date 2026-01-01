from django.core.management.base import BaseCommand
from faker import Faker
from apps.locations.models import GeoLocation

class Command(BaseCommand):
    help = 'Generates fake data for the application'

    def handle(self, *args, **options):
        fake = Faker()
        for _ in range(10):
            location = GeoLocation.objects.create(
                label=fake.word(),
                address_text=fake.address(),
                latitude=fake.latitude(),
                longitude=fake.longitude(),
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created GeoLocation: {location.label}'))

        self.stdout.write(self.style.SUCCESS('Successfully generated fake data.'))
