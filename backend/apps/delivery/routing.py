# apps/delivery/routing.py
from django.urls import re_path
from .consumers import LiveTrackingConsumer

websocket_urlpatterns = [
    # Route for real-time order tracking
    # Matches: ws/orders/123/
    re_path(
        r"ws/orders/(?P<order_id>\d+)/$",
        LiveTrackingConsumer.as_asgi(),
    ),
]