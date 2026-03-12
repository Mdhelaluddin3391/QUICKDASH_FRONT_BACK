import requests
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from celery import shared_task
from firebase_admin import messaging
from celery.utils.log import get_task_logger
from django.contrib.auth import get_user_model

from celery import shared_task
from firebase_admin import messaging
import logging

User = get_user_model()
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
def send_push_to_user_task(user_id, title, body, data=None):
    """
    Background task to send Firebase Push Notification to all devices of a user.
    """
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"[FCM] User with id {user_id} does not exist.")
        return "User not found"

    # Multi-device tokens collect karna
    tokens = []
    user_devices = user.devices.all()
    if user_devices.exists():
        tokens = [device.fcm_token for device in user_devices if device.fcm_token]
    elif getattr(user, 'fcm_token', None):
        # Fallback agar UserDevice mein nahi mila toh purane fcm_token se le lo
        tokens = [user.fcm_token]

    if not tokens:
        logger.warning(f"[PUSH] User {user.phone} has no active FCM devices.")
        return "No FCM tokens provided"
        
    try:
        # Data ko string mein convert karne ka logic
        stringified_data = {}
        if data:
            stringified_data = {str(k): str(v) for k, v in data.items()}

        # MulticastMessage ka use karke ek sath sabhi devices par bhejna
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            tokens=tokens,
            data=stringified_data 
        )
        response = messaging.send_each_for_multicast(message)
        logger.info(f"[FCM] Multicast sent to {len(tokens)} tokens. Success: {response.success_count}, Failure: {response.failure_count}")
        return f"Success: {response.success_count}, Failure: {response.failure_count}"
        
    except Exception as e:
        logger.error(f"[FCM] Error sending message to user '{user.phone}': {e}")
        return str(e)