import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'

    def ready(self):
        # Firebase initialization is now handled globally in config/settings.py
        try:
            import apps.notifications.signals
        except ImportError as e:
            logger.error(f"Failed to import notification signals: {e}")