# apps/riders/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum

from .models import RiderProfile, RiderEarning, RiderPayout
from apps.utils.exceptions import BusinessLogicException

class RiderService:

    @staticmethod
    @transaction.atomic
    def create_rider_profile(user):
        """
        Idempotent profile creation.
        """
        if not user.roles.filter(role="rider").exists():
            raise ValidationError("User does not have rider role")

        profile, created = RiderProfile.objects.get_or_create(user=user)
        return profile

    @staticmethod
    def set_availability(profile: RiderProfile, available: bool):
        """
        Toggles Rider Availability with Safety Checks.
        """
        if available:
            # 1. KYC Check
            if not profile.is_kyc_verified:
                 raise BusinessLogicException(
                     "KYC Pending. Please upload verified License and RC to go online.",
                     code="kyc_required"
                 )
                 
            # 2. Block if currently busy (Optional strictness)
            # If we allow them to go online while busy, they might get double assigned.
            # Usually, 'available' implies 'ready for NEW orders'.
            pass 

        else:
            # 3. Prevent going Offline if carrying a live order
            active_deliveries = profile.deliveries.filter(
                status__in=['assigned', 'picked_up']
            ).exists()
            
            if active_deliveries:
                 raise BusinessLogicException(
                     "Cannot go offline while you have active deliveries.",
                     code="active_delivery_restriction"
                 )

        profile.is_available = available
        profile.save(update_fields=["is_available"])

    @staticmethod
    def assign_warehouse(profile: RiderProfile, warehouse):
        profile.current_warehouse = warehouse
        profile.save(update_fields=["current_warehouse"])

    @staticmethod
    def add_earning(profile: RiderProfile, amount, reference):
        """
        Log an immutable earning record.
        """
        # FIX: Financial Safety
        if amount < 0:
            raise ValidationError("Earning amount cannot be negative")
            
        return RiderEarning.objects.create(
            rider=profile,
            amount=amount,
            reference=reference,
        )

    @staticmethod
    @transaction.atomic
    def generate_payout(rider: RiderProfile):
        """
        Aggregates unpaid earnings into a Payout.
        HARDENING:
        - Uses 'select_for_update' to lock rows.
        - Materializes the list to ensure the SUM matches the rows updated.
        """
        # 1. Lock candidate rows (Prevent modification during calc)
        earnings_qs = RiderEarning.objects.select_for_update().filter(
            rider=rider,
            payout__isnull=True
        )
        
        # 2. Materialize list to capture IDs and enforce lock
        locked_earnings = list(earnings_qs)
        
        if not locked_earnings:
            return None

        # 3. Calculate Sum in Python (Safe because rows are locked)
        total_amount = sum(e.amount for e in locked_earnings)

        # 4. Create Payout Record
        payout = RiderPayout.objects.create(
            rider=rider,
            amount=total_amount,
            status="processing"
        )
        
        # 5. Link ONLY the locked IDs
        # This prevents "Phantom Reads" where a new earning inserted 
        # ms ago gets linked but wasn't included in the sum.
        locked_ids = [e.id for e in locked_earnings]
        RiderEarning.objects.filter(id__in=locked_ids).update(payout=payout)
        
        return payout