from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Creates a superuser automatically for QuickDash'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # आपके मॉडल में PHONE ही USERNAME है
        # इसलिए हम यहाँ एक फोन नंबर इस्तेमाल करेंगे
        phone = '6009282670'  # <-- यह आपका लॉगिन ID होगा (Phone Number)
        email = 'admin@quickdash.com'
        password = 'helal@123'

        # Env variables se bhi le sakte hain (Optional)
        if os.getenv('DJANGO_SUPERUSER_PHONE'):
            phone = os.getenv('DJANGO_SUPERUSER_PHONE')
        
        if not phone or not password:
            self.stdout.write(self.style.WARNING('⚠️  Credentials missing. Skipping...'))
            return

        # चेक करें कि इस Phone Number वाला यूजर पहले से है या नहीं
        if not User.objects.filter(phone=phone).exists():
            self.stdout.write(f'Creating superuser with phone: {phone}...')
            try:
                # create_superuser ko 'phone' chahiye
                User.objects.create_superuser(
                    phone=phone,
                    email=email,
                    password=password
                )
                self.stdout.write(self.style.SUCCESS('✅ Superuser created successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error creating superuser: {e}'))
        else:
            self.stdout.write(self.style.SUCCESS('ℹ️  Superuser already exists.'))