# apps/customers/services.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from .models import CustomerProfile, CustomerAddress, SupportTicket
from apps.accounts.models import User

class CustomerService:

    @staticmethod
    def create_support_ticket(user, data):
        """
        Creates a support ticket for a specific order.
        """
        from apps.orders.models import Order
        order_id = data.get("order_id")
        
        # Validation: User must own the order
        order = get_object_or_404(Order, id=order_id, user=user)
        
        return SupportTicket.objects.create(
            user=user,
            order=order,
            issue_type=data.get("issue_type"),
            description=data.get("description")
        )

    @staticmethod
    def get_or_create_profile(user: User) -> CustomerProfile:
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    @transaction.atomic
    def add_address(user: User, data: dict) -> CustomerAddress:
        profile = CustomerService.get_or_create_profile(user)

        # Logic: If this is the first active address, force it to be default
        has_active_addresses = profile.addresses.filter(is_deleted=False).exists()
        is_default = data.get("is_default", False)

        if not has_active_addresses:
            is_default = True

        if is_default:
            # Unset previous default
            CustomerAddress.objects.filter(
                customer=profile,
                is_deleted=False,
                is_default=True
            ).update(is_default=False)

        return CustomerAddress.objects.create(
            customer=profile,
            label=data.get("label"),
            address_line=data.get("address_line"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            is_default=is_default
        )

    @staticmethod
    @transaction.atomic
    def set_default_address(user: User, address_id: int):
        profile = CustomerService.get_or_create_profile(user)

        # 1. Unset all defaults
        CustomerAddress.objects.filter(
            customer=profile,
            is_deleted=False
        ).update(is_default=False)

        # 2. Set new default
        address = get_object_or_404(
            CustomerAddress,
            id=address_id,
            customer=profile,
            is_deleted=False
        )
        address.is_default = True
        address.save()
        return address

    @staticmethod
    @transaction.atomic
    def soft_delete_address(user: User, address_id: int):
        profile = CustomerService.get_or_create_profile(user)

        address = get_object_or_404(
            CustomerAddress,
            id=address_id,
            customer=profile,
            is_deleted=False
        )
        
        was_default = address.is_default
        
        address.is_deleted = True
        address.is_default = False
        address.save()
        
        # If we deleted the default, should we auto-promote another?
        # For now, we leave it to the user to pick a new one, or the frontend to prompt.