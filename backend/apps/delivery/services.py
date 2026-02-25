import secrets
import logging
import boto3
import magic  
from botocore.exceptions import ClientError
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

from apps.inventory.services import InventoryService
from apps.notifications.services import NotificationService
from apps.audit.services import AuditService
from apps.orders.models import Order
from apps.delivery.models import Delivery
from apps.utils.exceptions import BusinessLogicException

logger = logging.getLogger(__name__)

class StorageService:
    """
    Handles secure file uploads (Proofs, Docs) directly to S3.
    """
    @staticmethod
    def generate_presigned_post(order_id, file_type):
        """
        Generates a secure Presigned POST policy.
        Enforces:
        1. Correct Bucket
        2. File Size Limit (5MB)
        3. Specific Content-Type
        """
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        if not bucket_name:
             raise BusinessLogicException("Storage configuration missing")

        ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}
        if file_type not in ALLOWED_TYPES:
            raise BusinessLogicException("Unsupported file type")

        s3_client = boto3.client('s3')
        object_name = f"proofs/order_{order_id}_{secrets.token_hex(4)}"
        
        try:
            response = s3_client.generate_presigned_post(
                Bucket=bucket_name,
                Key=object_name,
                Fields={
                    'Content-Type': file_type,
                },
                Conditions=[
                    ['content-length-range', 100, 5242880],
                    {'Content-Type': file_type}
                ],
                ExpiresIn=300 
            )
            return {"post_data": response, "key": object_name}
        except ClientError as e:
            logger.error(f"S3 Presign Error: {e}")
            raise BusinessLogicException("Storage service unavailable")

    @staticmethod
    def validate_upload(key):
        """
        Validates that the file exists in S3 AND checks Magic Bytes.
        Prevents 'Fake Key' attacks and Malware uploads.
        """
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        if not bucket_name:
             if settings.DEBUG: return
             raise BusinessLogicException("Storage configuration missing")

        s3_client = boto3.client('s3')
        try:
            head_response = s3_client.head_object(Bucket=bucket_name, Key=key)
            
            if head_response['ContentLength'] < 100:
                raise BusinessLogicException("File too small or empty")
            
            
            response = s3_client.get_object(Bucket=bucket_name, Key=key, Range='bytes=0-2048')
            file_header = response['Body'].read()
            
            mime_type = magic.from_buffer(file_header, mime=True)
            allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf']
            
            if mime_type not in allowed_types:
                logger.critical(f"Security Alert: Malicious file upload attempt. Detected: {mime_type}, Key: {key}")
                s3_client.delete_object(Bucket=bucket_name, Key=key)
                raise BusinessLogicException(f"Invalid file content. Detected {mime_type}, expected image/pdf.")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                raise BusinessLogicException("Proof file not found. Please upload again.")
            logger.error(f"S3 Validation Error for {key}: {e}")
            raise BusinessLogicException("Unable to validate file upload")


class DeliveryService:
    
    @staticmethod
    def generate_otp():
        return str(secrets.randbelow(900000) + 100000)

    @staticmethod
    def initiate_delivery_search(order):
        """
        Creates the delivery record and triggers the async search task.
        """
        if hasattr(order, "delivery"):
            return order.delivery

        delivery = Delivery.objects.create(
            order=order,
            status="assigned",
            job_status="searching",
            otp=DeliveryService.generate_otp(),
        )

        from apps.delivery.tasks import retry_auto_assign_rider
        retry_auto_assign_rider.delay(order.id)
        
        return delivery

    @staticmethod
    @transaction.atomic
    def assign_rider(order, rider, actor=None):
        """
        Assigns a specific rider to an order.
        Used by: Auto-Assigner (System) and Admin (Manual).
        """
        delivery, created = Delivery.objects.get_or_create(
            order=order, 
            defaults={
                "otp": DeliveryService.generate_otp()
            }
        )

        delivery.rider = rider
        delivery.job_status = "assigned"
        delivery.status = "assigned" 
        delivery.save()

        transaction.on_commit(lambda: NotificationService.send_push(
            rider.user,
            "New Delivery Assigned",
            f"Order #{order.id} is assigned to you."
        ))

        action_type = "manual_assignment" if actor else "auto_assignment"
        AuditService.log(
            action=action_type,
            reference_id=str(order.id),
            user=actor, 
            metadata={
                "rider_id": rider.id,
                "rider_phone": rider.user.phone,
                "warehouse": order.warehouse.code
            }
        )

        return delivery

    @staticmethod
    @transaction.atomic
    def assign_nearest_rider(order_id):
        """
        Legacy/Simple Assignment Logic. 
        (Note: AutoRiderAssignmentService in auto_assign.py is preferred)
        """
        try:
            order = Order.objects.get(id=order_id)
            delivery = order.delivery
        except Exception:
            return False

        from apps.riders.models import RiderProfile
        warehouse = order.warehouse

        candidate = RiderProfile.objects.select_for_update(skip_locked=True).filter(
            current_warehouse=warehouse,
            is_active=True,
            is_available=True
        ).first()

        if not candidate:
            return False

        return DeliveryService.assign_rider(order, candidate)

    @staticmethod
    @transaction.atomic
    def place_in_dispatch_bin(order_id, dispatch_bin_code, picker_user):
        """
        Picker places packed order into a specific dispatch bin/shelf.
        """
        order = Order.objects.select_for_update().get(id=order_id)
        
        if not hasattr(order, 'delivery'):
            raise BusinessLogicException("Delivery record missing for this order")

        delivery = order.delivery
        
        order.status = "packed"
        order.save(update_fields=["status"])

        delivery.dispatch_location = dispatch_bin_code
        delivery.save(update_fields=["dispatch_location"])

        AuditService.log(
            action="order_placed_in_buffer",
            reference_id=str(order.id),
            user=picker_user,
            metadata={"bin": dispatch_bin_code}
        )

        return {"status": "success"}

    @staticmethod
    @transaction.atomic
    def rider_self_pickup(order_id, rider_user, scanned_bin_code):
        """
        Rider verifies they have picked up the right package from the bin.
        """
        order = Order.objects.select_for_update().get(id=order_id)
        delivery = order.delivery
        rider_profile = getattr(rider_user, 'rider_profile', None)

        if not rider_profile or not rider_profile.is_available:
            raise BusinessLogicException("Rider not available")
        
        if order.status != "packed":
             raise BusinessLogicException(f"Order not ready (Status: {order.status})")

        if delivery.dispatch_location != scanned_bin_code:
            raise BusinessLogicException(f"Wrong Bin! Item is in {delivery.dispatch_location}")

        order.status = "out_for_delivery"
        order.save(update_fields=["status"])

        delivery.status = "out_for_delivery"
        delivery.rider = rider_profile
        delivery.save(update_fields=["status", "rider"])

        return {"status": "success"}

    @staticmethod
    @transaction.atomic
    def mark_delivered(delivery, otp, proof_image_key=None):
        """
        Rider completes the delivery.
        Requires OTP validation and optional Proof of Delivery (PoD).
        """
        if delivery.status == "delivered":
            return


        if str(delivery.otp) != str(otp):
            raise ValidationError("Invalid OTP")

     
        if proof_image_key:
            StorageService.validate_upload(proof_image_key)
            delivery.proof_image = proof_image_key
            
        delivery.status = "delivered"
        delivery.save()

        order = delivery.order
        order.status = "delivered"
        order.save(update_fields=["status"])

     
        for item in order.items.all():
            from apps.inventory.models import InventoryItem
         
            inv_item = InventoryItem.objects.filter(
                sku=item.sku, 
                bin__rack__aisle__zone__warehouse=order.warehouse
            ).first()
            
            if inv_item:
                InventoryService.commit_stock(
                    item=inv_item,
                    quantity=item.quantity,
                    reference=f"sold_order_{order.id}"
                )

        from apps.riders.services import RiderService
        RiderService.add_earning(
            delivery.rider, 
            amount=settings.RIDER_FIXED_PAY_PER_ORDER, 
            reference=f"Delivery #{delivery.id}"
        )

        AuditService.delivery_completed(delivery)

    @staticmethod
    @transaction.atomic
    def mark_failed(delivery, reason, actor=None):
        """
        Handles Sad Path: Delivery Failed (e.g. Customer unavailable).
        Triggers Auto-Refund if paid.
        """
        if delivery.status in ["delivered", "failed"]:
            return

        delivery.status = "failed"
        delivery.save(update_fields=["status"])

        order = delivery.order
        if order.status != "cancelled":
            order.status = "cancelled"
            order.save(update_fields=["status"])
            
            if hasattr(order, 'payment') and order.payment.status == 'paid':
                from apps.payments.refund_services import RefundService
                RefundService.initiate_refund(order.payment)

        AuditService.log(
            action="delivery_failed",
            reference_id=str(delivery.id),
            user=actor if actor else delivery.rider.user,
            metadata={"reason": reason, "order_id": order.id}
        )
        
        return delivery

    @staticmethod
    def calculate_average_delivery_time(warehouse_id=None):
        """
        Analytics Helper.
        """
        qs = Delivery.objects.filter(status="delivered")
        if warehouse_id:
            qs = qs.filter(order__warehouse_id=warehouse_id)
            
        metrics = qs.aggregate(
            avg_time=models.Avg(models.F("updated_at") - models.F("created_at"))
        )
        return metrics["avg_time"]