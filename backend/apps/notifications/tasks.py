# apps/notifications/tasks.py
import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

logger = get_task_logger(__name__)

@shared_task(
    bind=True, 
    max_retries=3, 
    default_retry_delay=5, 
    queue='high_priority' # Critical for User Experience
)
def send_otp_sms(self, phone, content):
    """
    Async SMS Sender using 3rd party provider.
    """
    sms_key = getattr(settings, "SMS_PROVIDER_KEY", None)
    sms_url = getattr(settings, "SMS_PROVIDER_URL", None)

    # 1. Dev Mode Bypass
    if settings.DEBUG:
        # Humne is line ko comment kar diya taaki terminal saaf rahe (Duplicate log hat gaya)
        # logger.info(f"[DEV-SMS] To: {phone} | Msg: {content}")
        return "Dev Sent"

    if not sms_key or not sms_url:
        logger.error("SMS Configuration missing")
        return "Config Missing"

    try:
        # 2. Call Provider
        response = requests.post(
            sms_url,
            json={
                "to": phone, 
                "message": content, 
                "api_key": sms_key
            },
            timeout=5 # Fast timeout to prevent worker clogging
        )
        response.raise_for_status()
        return "Sent"

    except requests.RequestException as e:
        logger.warning(f"SMS Provider Failed: {e}. Retrying...")
        raise self.retry(exc=e)