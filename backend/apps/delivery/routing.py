
from django.urls import re_path, path 
from .consumers import LiveTrackingConsumer
from apps.orders.consumers import AdminNotificationConsumer 

websocket_urlpatterns = [
    re_path(
        r"ws/orders/(?P<order_id>\d+)/$",
        LiveTrackingConsumer.as_asgi(),
    ),
    
    path('ws/admin-notifications/', AdminNotificationConsumer.as_asgi()),
]