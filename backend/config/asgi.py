import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack

# 1. Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 2. Initialize Django setup FIRST
django.setup()

# 3. Import routing AFTER django.setup() is called
import apps.delivery.routing

# 4. Define the ASGI application
application = ProtocolTypeRouter({
    "http": get_asgi_application(),

    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                apps.delivery.routing.websocket_urlpatterns
            )
        )
    ),
})