# apps/delivery/consumers.py
import json
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from apps.orders.models import Order
from django_redis import get_redis_connection

User = get_user_model()

class LiveTrackingConsumer(AsyncWebsocketConsumer):
    """
    Real-time location tracking for Orders.
    Auth: One-time 'ticket' via Query Param (standard WS auth pattern).
    """

    async def connect(self):
        query_string = parse_qs(self.scope["query_string"].decode())
        ticket = query_string.get("ticket", [None])[0]
        
        if not ticket:
            await self.close(code=4003)
            return

        # 1. Verify & Burn Ticket (Atomic Lua)
        conn = get_redis_connection("default")
        user_id = await database_sync_to_async(conn.eval)(
            "local v = redis.call('get', KEYS[1]) redis.call('del', KEYS[1]) return v",
            1, f"ws_ticket:{ticket}"
        )
        
        if not user_id:
            await self.close(code=4003) # Invalid/Expired Ticket
            return

        try:
            # 2. Rehydrate User
            user = await database_sync_to_async(User.objects.get)(id=int(user_id))
            self.scope['user'] = user
            
            # 3. Validate Context
            self.order_id = self.scope['url_route']['kwargs']['order_id']
            self.room_group_name = f"tracking_{self.order_id}"

            if await self.can_access_job(user, self.order_id):
                await self.channel_layer.group_add(
                    self.room_group_name,
                    self.channel_name
                )
                await self.accept()
            else:
                await self.close(code=4003)
        except (User.DoesNotExist, ValueError, KeyError):
            await self.close(code=4003)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

    async def receive(self, text_data):
        # Clients don't send data here usually, mostly listen.
        # Riders push location via HTTP API (RiderLocationPingAPIView) which broadcasts here.
        pass

    async def location_broadcast(self, event):
        # Forward internal Redis message to WebSocket client
        await self.send(text_data=json.dumps({
            "type": "rider_location",
            "lat": event["lat"],
            "lng": event["lng"]
        }))

    async def order_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "status_update",
            "status": event["status"],
            "message": event["message"]
        }))

    @database_sync_to_async
    def can_access_job(self, user, order_id):
        """
        Authorization: User must be either the Customer or the Assigned Rider.
        """
        try:
            order = Order.objects.select_related('delivery__rider__user').get(id=order_id)
            
            # Check 1: Is Customer?
            if order.user == user: 
                return True
                
            # Check 2: Is Assigned Rider?
            if hasattr(order, 'delivery') and order.delivery.rider:
                return order.delivery.rider.user == user
                
            return False
        except Order.DoesNotExist:
            return False