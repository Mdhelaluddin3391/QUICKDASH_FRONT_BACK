from django.db import transaction
from .models import User, UserRole

class AccountService:
    @staticmethod
    @transaction.atomic
    def create_customer(phone):
        clean_phone = phone.replace("+91", "") if phone.startswith("+91") else phone
        
        user, created = User.objects.get_or_create(phone=clean_phone)
        UserRole.objects.get_or_create(user=user, role="customer")
        return user

    @staticmethod
    @transaction.atomic
    def create_rider(phone):
        user, _ = User.objects.get_or_create(phone=phone)
        UserRole.objects.get_or_create(user=user, role="rider")
        return user

    @staticmethod
    @transaction.atomic
    def create_employee(phone):
        user, _ = User.objects.get_or_create(phone=phone)
        UserRole.objects.get_or_create(user=user, role="employee")
        user.is_staff = True 
        user.save()
        return user