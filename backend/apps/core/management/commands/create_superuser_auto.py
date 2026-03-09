from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates a superuser automatically if it does not exist'

    def handle(self, *args, **options):
        PHONE = '6009282670'
        PASSWORD = 'helal@123'

        if User.objects.filter(phone=PHONE).exists():
            self.stdout.write(self.style.SUCCESS(f'Superuser "{PHONE}" already exists. Skipping creation.'))
        else:
            try:
                User.objects.create_superuser(phone=PHONE, password=PASSWORD)
                self.stdout.write(self.style.SUCCESS(f'Successfully created superuser: {PHONE}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating superuser: {str(e)}'))