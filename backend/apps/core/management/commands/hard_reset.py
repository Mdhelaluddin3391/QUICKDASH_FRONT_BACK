import os
import shutil
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings

class Command(BaseCommand):
    help = "DANGER: Deletes all migration files and wipes the database schema."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Run without confirmation',
        )

    def handle(self, *args, **options):
        # Safety Check: Production mein na chale
        if not settings.DEBUG:
            self.stdout.write(self.style.ERROR("❌ SAFETY ERROR: Yeh command sirf DEBUG=True (Development) mein chal sakti hai."))
            return

        if not options['force']:
            confirm = input("⚠️  WARNING: Sab kuch delete ho jayega (Data + Migrations). Continue? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

        self.stdout.write(self.style.MIGRATE_HEADING("🚀 Starting Hard Reset..."))

        # ---------------------------------------------------------
        # STEP 1: Delete Migration Files
        # ---------------------------------------------------------
        apps_dir = os.path.join(settings.BASE_DIR, 'apps')
        deleted_files = 0

        for root, dirs, files in os.walk(apps_dir):
            if 'migrations' in dirs:
                migrations_path = os.path.join(root, 'migrations')
                for filename in os.listdir(migrations_path):
                    if filename != '__init__.py' and filename.endswith('.py'):
                        file_path = os.path.join(migrations_path, filename)
                        try:
                            os.remove(file_path)
                            deleted_files += 1
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Failed to delete {filename}: {e}"))
                
                # __pycache__ bhi saaf karein
                cache_path = os.path.join(migrations_path, '__pycache__')
                if os.path.exists(cache_path):
                    shutil.rmtree(cache_path)

        self.stdout.write(self.style.SUCCESS(f"✅ Deleted {deleted_files} migration files."))

        # ---------------------------------------------------------
        # STEP 2: Wipe Database (PostgreSQL)
        # ---------------------------------------------------------
        self.stdout.write("🗑️  Wiping Database Schema...")
        
        with connection.cursor() as cursor:
            # Public schema ko uda kar wapas create karein (Fastest Wipe)
            cursor.execute("DROP SCHEMA public CASCADE;")
            cursor.execute("CREATE SCHEMA public;")
            cursor.execute("GRANT ALL ON SCHEMA public TO public;")
            # Agar specific user permission chahiye toh yahan add karein, usually public is enough for dev
        
        self.stdout.write(self.style.SUCCESS("✅ Database wiped successfully."))

        # ---------------------------------------------------------
        # Conclusion
        # ---------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("\n🎉 HARD RESET COMPLETE!"))
        self.stdout.write("Ab ye commands chalayein naya system banane ke liye:")
        self.stdout.write(self.style.WARNING("1. python manage.py makemigrations"))
        self.stdout.write(self.style.WARNING("2. python manage.py migrate"))
        self.stdout.write(self.style.WARNING("3. python manage.py setup_demo_data"))