# apps/accounts/services.py
from django.db import transaction
from .models import User, UserRole

class AccountService:
    @staticmethod
    @transaction.atomic
    def create_customer(phone):
        # Naya line: Agar phone number mein +91 hai, toh usko hata do
        clean_phone = phone.replace("+91", "") if phone.startswith("+91") else phone
        
        # Ab hamesha 10-digit number se hi account banega ya find hoga
        user, created = User.objects.get_or_create(phone=clean_phone)
        UserRole.objects.get_or_create(user=user, role="customer")
        return user

    @staticmethod
    @transaction.atomic
    def create_rider(phone):
        user, _ = User.objects.get_or_create(phone=phone)
        UserRole.objects.get_or_create(user=user, role="rider")
        # Ensure RiderProfile exists (managed in RiderService, but safe to init here if needed)
        return user

    @staticmethod
    @transaction.atomic
    def create_employee(phone):
        user, _ = User.objects.get_or_create(phone=phone)
        UserRole.objects.get_or_create(user=user, role="employee")
        user.is_staff = True # Employees can access admin
        user.save()
        return user