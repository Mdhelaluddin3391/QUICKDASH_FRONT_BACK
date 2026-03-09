import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from celery import shared_task
from firebase_admin import messaging
import logging

logger = logging.getLogger(__name__)
logger = get_task_logger(__name__)

@shared_task(
    bind=True, 
    max_retries=3, 
    default_retry_delay=5, 
    queue='high_priority' 
)
def send_otp_sms(self, phone, content):
    """
    Async SMS Sender using 3rd party provider.
    """
    sms_key = getattr(settings, "SMS_PROVIDER_KEY", None)
    sms_url = getattr(settings, "SMS_PROVIDER_URL", None)

    if settings.DEBUG:
        
        return "Dev Sent"

    if not sms_key or not sms_url:
        logger.error("SMS Configuration missing")
        return "Config Missing"

    try:
        response = requests.post(
            sms_url,
            json={
                "to": phone, 
                "message": content, 
                "api_key": sms_key
            },
            timeout=5 
        )
        response.raise_for_status()
        return "Sent"

    except requests.RequestException as e:
        logger.warning(f"SMS Provider Failed: {e}. Retrying...")
        raise self.retry(exc=e)
    


@shared_task
def send_push_to_topic_task(topic, title, body, data=None):
    """
    Background task to send Firebase Push Notification to a topic.
    """
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            topic=topic,
            data=data or {}
        )
        response = messaging.send(message)
        logger.info(f"[FCM] Successfully sent message to topic '{topic}': {response}")
        return response
    except Exception as e:
        logger.error(f"[FCM] Error sending message to topic '{topic}': {e}")
        return str(e)
    
@shared_task
def send_push_to_user_task(fcm_token, title, body, data=None):
    """
    Background task to send Firebase Push Notification to a specific user.
    """
    if not fcm_token:
        return "No FCM token provided"
        
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=fcm_token,
            data=data or {}
        )
        response = messaging.send(message)
        logger.info(f"[FCM] Successfully sent message to token '{fcm_token}': {response}")
        return response
    except Exception as e:
        logger.error(f"[FCM] Error sending message to token '{fcm_token}': {e}")
        return str(e)