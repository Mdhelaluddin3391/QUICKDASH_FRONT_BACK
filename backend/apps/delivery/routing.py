# backend/apps/delivery/routing.py

from django.urls import re_path, path  # Dhyan dein: yahan 'path' ko bhi import kiya hai
from .consumers import LiveTrackingConsumer
from apps.orders.consumers import AdminNotificationConsumer # Naya Admin Consumer yahan import karein

websocket_urlpatterns = [
    # Purana route: Real-time order tracking ke liye
    re_path(
        r"ws/orders/(?P<order_id>\d+)/$",
        LiveTrackingConsumer.as_asgi(),
    ),
    
    # NAYA ROUTE: Admin sound notification ke liye
    path('ws/admin-notifications/', AdminNotificationConsumer.as_asgi()),
]