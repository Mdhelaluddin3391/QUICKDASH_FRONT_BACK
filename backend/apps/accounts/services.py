from django.db import transaction
from .models import User, UserRole

class AccountService:
    
    @staticmethod
    def _format_phone(phone):
        """
        Helper function: Ye ensure karega ki phone number hamesha +91 ke sath ho.
        Spaces aur dashes ko bhi remove kar dega.
        """
        phone = phone.replace(" ", "").replace("-", "")
        if not phone.startswith("+91"):
            if phone.startswith("91") and len(phone) == 12:
                return "+" + phone
            return "+91" + phone
        return phone

    @staticmethod
    @transaction.atomic
    def create_customer(phone):
        formatted_phone = AccountService._format_phone(phone)
        
        user, created = User.objects.get_or_create(phone=formatted_phone)
        UserRole.objects.get_or_create(user=user, role="customer")
        return user

    @staticmethod
    @transaction.atomic
    def create_rider(phone):
        formatted_phone = AccountService._format_phone(phone)
        
        user, created = User.objects.get_or_create(phone=formatted_phone)
        UserRole.objects.get_or_create(user=user, role="rider")
        return user

    @staticmethod
    @transaction.atomic
    def create_employee(phone):
        formatted_phone = AccountService._format_phone(phone)
        
        user, created = User.objects.get_or_create(phone=formatted_phone)
        UserRole.objects.get_or_create(user=user, role="employee")
        user.is_staff = True 
        user.save()
        return user