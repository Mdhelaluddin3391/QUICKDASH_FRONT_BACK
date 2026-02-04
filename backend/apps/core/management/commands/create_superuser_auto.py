from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Creates a superuser automatically for QuickDash'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # आपकी डिटेल्स (हार्डकोडेड)
        username = 'muhammadhela228'
        email = 'muhammadhela228@gmail.com'
        password = 'helal@123'
        phone = '9876543210'  # <-- ये डमी नंबर जरुरी है वरना एरर आएगा

        # चेक करें कि यूजर पहले से है या नहीं (Email से चेक करना ज्यादा सही है)
        if not User.objects.filter(email=email).exists():
            self.stdout.write(f'Creating superuser: {email}...')
            try:
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    phone_number=phone  # <-- ये लाइन मैंने जोड़ी है
                )
                self.stdout.write(self.style.SUCCESS('✅ Superuser created successfully!'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ Error creating superuser: {e}'))
        else:
            self.stdout.write(self.style.SUCCESS('ℹ️  Superuser already exists.'))