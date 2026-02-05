from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates a superuser automatically if it does not exist'

    def handle(self, *args, **options):
        # Aapka predefined Phone aur Password
        PHONE = '6009282670'
        PASSWORD = 'helal@123'

        # 1. Check karein agar user pehle se exist karta hai
        if User.objects.filter(phone=PHONE).exists():
            self.stdout.write(self.style.SUCCESS(f'Superuser "{PHONE}" already exists. Skipping creation.'))
        else:
            # 2. Agar nahi hai, to create karein
            try:
                # create_superuser method automatically is_staff=True aur is_superuser=True set kar deta hai
                User.objects.create_superuser(phone=PHONE, password=PASSWORD)
                self.stdout.write(self.style.SUCCESS(f'Successfully created superuser: {PHONE}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating superuser: {str(e)}'))