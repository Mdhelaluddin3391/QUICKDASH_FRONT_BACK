from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Creates a superuser automatically from environment variables'

    def handle(self, *args, **options):
        User = get_user_model()
        
        username = 'muhammadhela228'
        email = 'muhammadhela228@gmail.com'
        password = 'helal@123'

        if not username or not password:
            self.stdout.write(self.style.WARNING('⚠️  Superuser variables not found. Skipping...'))
            return

        if not User.objects.filter(username=username).exists():
            self.stdout.write(f'Creating superuser: {username}...')
            try:
                # User create karein
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                self.stdout.write(self.style.SUCCESS('✅ Superuser created successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error creating superuser: {e}'))
        else:
            self.stdout.write(self.style.SUCCESS('ℹ️  Superuser already exists.'))