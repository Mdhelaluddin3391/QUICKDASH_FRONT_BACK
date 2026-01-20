# apps/notifications/services.py
import secrets
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.conf import settings  # Ensure settings is imported
from apps.utils.exceptions import BusinessLogicException
from .models import OTPAbuseLog, PhoneOTP, Notification
from .tasks import send_otp_sms

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_sms(user, message):
        """
        Persist notification history and trigger async SMS delivery.
        """
        Notification.objects.create(
            user=user,
            type="sms",
            title="SMS",
            message=message,
        )
        
        # FIX: Robust Transaction Handling
        # Schedule task only after DB commit to ensure data consistency
        if transaction.get_connection().in_atomic_block:
            transaction.on_commit(lambda: send_otp_sms.delay(user.phone, message))
        else:
            send_otp_sms.delay(user.phone, message)

    @staticmethod
    def send_push(user, title, message):
        """
        Persist notification and log Push (Placeholder for FCM/APNS).
        """
        Notification.objects.create(
            user=user,
            type="push",
            title=title,
            message=message,
        )
        # Placeholder: Call actual Push Provider or enqueue task
        logger.info(f"[PUSH] Sent to {user.phone}: {title} - {message}")


class OTPService:
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = 60

    @staticmethod
    def generate_otp():
        # Cryptographically secure RNG (6 digits)
        return str(secrets.randbelow(900000) + 100000)

    @staticmethod
    def create_and_send(phone: str, ip_address: str = None):
        """
        Generates OTP, handles security checks, and queues SMS.
        """
        # 1. Input Validation
        allowed_prefixes = getattr(settings, "ALLOWED_COUNTRY_CODES", ["+91"])
        if not any(phone.startswith(prefix) for prefix in allowed_prefixes):
             raise BusinessLogicException("Phone number country code not supported", code="invalid_country")

        if len(phone) < 10 or len(phone) > 15:
             raise BusinessLogicException("Invalid phone number format", code="invalid_format")

        # 2. Per-Phone Rate Limiting (5 OTPs/hour)
        rate_key = f"otp_rate:{phone}"
        attempts = cache.get(rate_key, 0)
        if attempts >= 5:
            raise BusinessLogicException("Too many OTP requests. Try again later.", code="rate_limited")
        cache.set(rate_key, attempts + 1, timeout=3600)

        # 3. Resend Cooldown (Redis)
        cooldown_key = f"otp_cooldown:{phone}"
        if cache.get(cooldown_key):
             ttl = cache.ttl(cooldown_key)
             raise BusinessLogicException(f"Please wait {ttl} seconds before retrying", code="rate_limit")

        # 4. Abuse & Security Checks
        OTPAbuseService.check(phone, ip_address)

        # 4. Generate & Save (Atomic)
        with transaction.atomic():
            otp = OTPService.generate_otp()


# Debug-only OTP output (development only)
            if settings.DEBUG:
                logger.info("\n" + "="*40)
                logger.info(f" [DEV OTP] Phone: {phone}")
                logger.info(f" [DEV OTP] Code : {otp}")
                logger.info("" + "="*40 + "\n")
            
            # Invalidate old OTPs
            PhoneOTP.objects.filter(phone=phone, is_verified=False).delete()
            PhoneOTP.objects.create(phone=phone, otp=otp)

            # Set Cooldown
            cache.set(cooldown_key, "1", timeout=OTPService.RESEND_COOLDOWN_SECONDS)

            # 5. Queue Async Task
            msg = f"Your login code is {otp}. Valid for 5 mins."
            transaction.on_commit(lambda: send_otp_sms.delay(phone, msg))

    @staticmethod
    def verify(phone: str, otp: str) -> bool:
        """
        Verifies OTP and manages failure counters.
        """
        try:
            record = PhoneOTP.objects.filter(phone=phone, is_verified=False).latest("created_at")
        except PhoneOTP.DoesNotExist:
             raise BusinessLogicException("OTP not found or expired", code="otp_invalid")

        # Checks
        if record.is_expired():
             raise BusinessLogicException("OTP expired", code="otp_expired")

        if record.attempts >= OTPService.MAX_ATTEMPTS:
             raise BusinessLogicException("Too many attempts. Request a new OTP.", code="otp_limit")

        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(record.otp, otp):
            record.attempts += 1
            record.save(update_fields=["attempts"])
            OTPAbuseService.record_failure(phone)
            raise BusinessLogicException("Invalid OTP", code="otp_invalid")

        # Success
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
        # 1. Phone Blocking Check
        log, _ = OTPAbuseLog.objects.get_or_create(phone=phone)
        if log.is_blocked():
             raise BusinessLogicException(
                 f"Blocked until {log.blocked_until.strftime('%H:%M')}", 
                 code="otp_blocked"
             )

        # 2. IP Rate Limiting (Anti-Bot)
        if ip_address:
            ip_key = f"otp_ip_limit:{ip_address}"
            try:
                # Safe increment
                count = cache.incr(ip_key)
            except ValueError:
                cache.set(ip_key, 1, timeout=3600)
                count = 1
            
            if count > OTPAbuseService.IP_MAX_REQUESTS_PER_HOUR:
                logger.warning(f"IP Blocked due to SMS Pump: {ip_address}")
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