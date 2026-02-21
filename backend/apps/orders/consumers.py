import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AdminNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 1. Sabse pehle connection ko accept karein
        await self.accept()
        print("🟢 Admin WebSocket Connection Accept ho gaya!") 

        self.group_name = 'admin_notifications_group'

        try:
            # 2. Phir group me add karein
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            print("🟢 Admin WebSocket Group me add ho gaya!")
        except Exception as e:
            print("🔴 Channel Layer / Redis Error:", e)

    async def disconnect(self, close_code):
        print(f"🔴 Admin WebSocket Disconnect ho gaya, Close Code: {close_code}")
        try:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        except:
            pass

    async def send_notification(self, event):
        print("🔔 Naya order notification receive hua!")
        message_type = event.get('message', 'new_order')
        order_id = event.get('order_id', 'Unknown')

        # Browser (Admin panel) ko data bhejna
        await self.send(text_data=json.dumps({
            'type': message_type,
            'order_id': order_id
        }))