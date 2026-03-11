import secrets
import logging
import threading
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from firebase_admin import messaging  
from apps.utils.exceptions import BusinessLogicException
from .models import OTPAbuseLog, PhoneOTP, Notification
from .tasks import send_otp_sms

logger = logging.getLogger(__name__)

# --- BACKGROUND PUSH FUNCTIONS (Bina Celery) ---
def execute_push_to_user(fcm_token, title, body, data=None):
    if not fcm_token:
        return
    try:
        stringified_data = {str(k): str(v) for k, v in data.items()} if data else {}
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=fcm_token,
            data=stringified_data
        )
        response = messaging.send(message)
        logger.info(f"[FCM] Successfully sent to user: {response}")
    except Exception as e:
        logger.error(f"[FCM] Error sending to user: {e}")

def execute_push_to_topic(topic, title, body, data=None):
    try:
        stringified_data = {str(k): str(v) for k, v in data.items()} if data else {}
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            topic=topic,
            data=stringified_data
        )
        response = messaging.send(message)
        logger.info(f"[FCM] Successfully sent to topic '{topic}': {response}")
    except Exception as e:
        logger.error(f"[FCM] Error sending to topic '{topic}': {e}")


class NotificationService:
    @staticmethod
    def send_sms(user, message):
        Notification.objects.create(user=user, type="sms", title="SMS", message=message)
        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(lambda: send_otp_sms.delay(user.phone, message))
        else:
            send_otp_sms.delay(user.phone, message)

    @staticmethod
    def send_push(user, title, message, extra_data=None, delay_seconds=2):
        """User ko notification bhejna (Order status ke liye)"""
        Notification.objects.create(user=user, type="push", title=title, message=message)
        
        user_devices = user.devices.all()
        if user_devices.exists():
            for device in user_devices:
                threading.Timer(delay_seconds, execute_push_to_user, args=[device.fcm_token, title, message, extra_data]).start()
        elif getattr(user, 'fcm_token', None):
            threading.Timer(delay_seconds, execute_push_to_user, args=[user.fcm_token, title, message, extra_data]).start()
        else:
            logger.warning(f"[PUSH] User {user.phone} has no active FCM devices.")

    @staticmethod
    def send_global_push(topic, title, message, extra_data=None, delay_seconds=2):
        """Sabhi users ko notification bhejna (Flash sale, promotions)"""
        threading.Timer(delay_seconds, execute_push_to_topic, args=[topic, title, message, extra_data]).start()


# --- OTP SERVICES ---
class OTPService:
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = getattr(settings, "OTP_RESEND_COOLDOWN", 60)
    EXPIRY_SECONDS = getattr(settings, "OTP_EXPIRY_SECONDS", 300)

    @staticmethod
    def generate_otp():
        return str(secrets.randbelow(900000) + 100000)

    @staticmethod
    def create_and_send(phone: str, ip_address: str = None):
        allowed_prefixes = getattr(settings, "ALLOWED_COUNTRY_CODES", ["+91"])
        if not any(phone.startswith(prefix) for prefix in allowed_prefixes):
             raise BusinessLogicException("Phone number country code not supported", code="invalid_country")

        if len(phone) < 10 or len(phone) > 15:
             raise BusinessLogicException("Invalid phone number format", code="invalid_format")

        rate_key = f"otp_rate:{phone}"
        attempts = cache.get(rate_key, 0)
        if attempts >= 5:
            raise BusinessLogicException("Too many OTP requests. Try again later.", code="rate_limited")
        cache.set(rate_key, attempts + 1, timeout=3600)

        cooldown_key = f"otp_cooldown:{phone}"
        if cache.get(cooldown_key):
             ttl = cache.ttl(cooldown_key)
             raise BusinessLogicException(f"Please wait {ttl} seconds before retrying", code="rate_limit")

        OTPAbuseService.check(phone, ip_address)

        with transaction.atomic():
            otp = OTPService.generate_otp()
            logger.info(f" [DEV OTP] Phone: {phone} | Code : {otp}")
            PhoneOTP.objects.filter(phone=phone, is_verified=False).delete()
            PhoneOTP.objects.create(phone=phone, otp=otp)
            cache.set(cooldown_key, "1", timeout=OTPService.RESEND_COOLDOWN_SECONDS)

            minutes = max(1, OTPService.EXPIRY_SECONDS // 60)
            msg = f"Your login code is {otp}. Valid for {minutes} minute(s)."
            transaction.on_commit(lambda: send_otp_sms.delay(phone, msg))
            return otp

    @staticmethod
    def verify(phone: str, otp: str) -> bool:
        try:
            record = PhoneOTP.objects.filter(phone=phone, is_verified=False).latest("created_at")
        except PhoneOTP.DoesNotExist:
             raise BusinessLogicException("OTP not found or expired", code="otp_invalid")

        if record.is_expired():
             raise BusinessLogicException("OTP expired", code="otp_expired")

        if record.attempts >= OTPService.MAX_ATTEMPTS:
             raise BusinessLogicException("Too many attempts. Request a new OTP.", code="otp_limit")

        if not secrets.compare_digest(record.otp, otp):
            record.attempts += 1
            record.save(update_fields=["attempts"])
            OTPAbuseService.record_failure(phone)
            raise BusinessLogicException("Invalid OTP", code="otp_invalid")

        record.is_verified = True
        record.save(update_fields=["is_verified"])
        OTPAbuseService.reset(phone)
        return True

class OTPAbuseService:
    MAX_FAILS = 5
    BLOCK_MINUTES = 15
    IP_MAX_REQUESTS_PER_HOUR = 50 

    @staticmethod
    def check(phone, ip_address=None):
        log, _ = OTPAbuseLog.objects.get_or_create(phone=phone)
        if log.is_blocked():
             raise BusinessLogicException(f"Blocked until {log.blocked_until.strftime('%H:%M')}", code="otp_blocked")
        if ip_address:
            ip_key = f"otp_ip_limit:{ip_address}"
            try:
                count = cache.incr(ip_key)
            except ValueError:
                cache.set(ip_key, 1, timeout=3600)
                count = 1
            if count > OTPAbuseService.IP_MAX_REQUESTS_PER_HOUR:
                raise BusinessLogicException("Too many requests from this device", code="ip_blocked")

    @staticmethod
    def record_failure(phone):
        log, _ = OTPAbuseLog.objects.get_or_create(phone=phone)
        log.failed_attempts += 1
        if log.failed_attempts >= OTPAbuseService.MAX_FAILS:
            log.blocked_until = timezone.now() + timedelta(minutes=OTPAbuseService.BLOCK_MINUTES)
        log.save()

    @staticmethod
    def reset(phone):
        OTPAbuseLog.objects.filter(phone=phone).delete()