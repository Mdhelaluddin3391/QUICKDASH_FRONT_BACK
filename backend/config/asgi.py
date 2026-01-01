# config/asgi.py
import os
import django
from django.core.asgi import get_asgi_application

# 1. Init Django first (Critical before importing channels)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack
import apps.delivery.routing

# 2. Application Definition
application = ProtocolTypeRouter({
    # HTTP requests -> Django
    "http": get_asgi_application(),

    # WebSocket requests -> Channels
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                apps.delivery.routing.websocket_urlpatterns
            )
        )
    ),
})