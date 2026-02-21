import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AdminNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Jab bhi admin panel load hoga, yeh WebSocket connect hoga
        self.group_name = 'admin_notifications_group'

        # Admin ko group me add karna
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Disconnect hone par group se hatana
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Signal se jo data aayega, usko frontend me bhejna
    async def send_notification(self, event):
        message_type = event['message']
        order_id = event['order_id']

        # Browser (Admin panel) ko data JSON format me bhejna
        await self.send(text_data=json.dumps({
            'type': message_type,
            'order_id': order_id
        }))