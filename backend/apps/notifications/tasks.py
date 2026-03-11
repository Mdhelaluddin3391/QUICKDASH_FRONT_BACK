import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

from celery import shared_task
from firebase_admin import messaging
import logging

logger = get_task_logger(__name__)

@shared_task(
    bind=True, 
    max_retries=3, 
    default_retry_delay=5, 
    queue='high_priority' 
)
def send_otp_sms(self, phone, content):
    """
    Async SMS Sender using Twilio provider.
    """
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    twilio_number = getattr(settings, "TWILIO_PHONE_NUMBER", "")

    # Agar Twilio config missing hai, toh SMS nahi jayega (Fallback chalega)
    if not account_sid or not auth_token or not twilio_number:
        logger.warning("Twilio config missing. SMS not sent. Relying on API fallback.")
        return "Config Missing - Fallback Active"

    try:
        # Twilio Client Initialize
        client = Client(account_sid, auth_token)
        
        # SMS Send Request
        message = client.messages.create(
            body=content,
            from_=twilio_number,
            to=phone
        )
        logger.info(f"Twilio SMS sent successfully to {phone}. SID: {message.sid}")
        return f"Sent: {message.sid}"

    except TwilioRestException as e:
        logger.error(f"Twilio API Error: {e}")
        # Agar Server error ya Rate Limit error aaye, toh Task retry karega
        if e.status in [429, 500, 502, 503, 504]:
            logger.warning(f"Retrying SMS for {phone} due to Twilio error...")
            raise self.retry(exc=e)
        return f"Twilio Failed: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in SMS sending: {e}")
        raise self.retry(exc=e)

@shared_task
def send_push_to_topic_task(topic, title, body, data=None):
    """
    Background task to send Firebase Push Notification to a topic.
    """
    try:
        # 🔥 CHANGE: Data ko string mein convert karne ka logic
        stringified_data = {}
        if data:
            stringified_data = {str(k): str(v) for k, v in data.items()}

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            topic=topic,
            data=stringified_data # 🔥 CHANGE: Yahan stringified_data pass kiya hai
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
        # 🔥 CHANGE: Data ko string mein convert karne ka logic
        stringified_data = {}
        if data:
            stringified_data = {str(k): str(v) for k, v in data.items()}

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            token=fcm_token,
            data=stringified_data # 🔥 CHANGE: Yahan stringified_data pass kiya hai
        )
        response = messaging.send(message)
        logger.info(f"[FCM] Successfully sent message to token '{fcm_token}': {response}")
        return response
    except Exception as e:
        logger.error(f"[FCM] Error sending message to token '{fcm_token}': {e}")
        return str(e)