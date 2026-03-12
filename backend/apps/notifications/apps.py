import os
import json
from django.apps import AppConfig
from django.conf import settings
import firebase_admin
from firebase_admin import credentials

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'

    def ready(self):
        # 🔥 YAHAN FIREBASE INITIALIZE HO RAHA HAI
        if not firebase_admin._apps:
            firebase_creds_env = os.getenv('FIREBASE_JSON_CREDENTIALS')
            if firebase_creds_env:
                cred_dict = json.loads(firebase_creds_env)
                cred = credentials.Certificate(cred_dict)
            else:
                firebase_key_path = os.path.join(settings.BASE_DIR, 'firebase-key.json')
                cred = credentials.Certificate(firebase_key_path)
                
            firebase_admin.initialize_app(cred)