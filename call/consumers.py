# call/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class CallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Safely get username from URL route
        username = self.scope.get('url_route', {}).get('kwargs', {}).get('username')
        if not username:
            # Reject connection if username not provided
            await self.close()
            return

        self.my_name = username
        await self.channel_layer.group_add(self.my_name, self.channel_name)
        await self.accept()

        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'data': {'message': f"Connected as {self.my_name}"}
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "my_name"):
            await self.channel_layer.group_discard(
                self.my_name,
                self.channel_name
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        eventType = text_data_json.get('type')
        data = text_data_json.get('data', {})

        if eventType == 'call':
            # Send call request to target user
            target_user = data.get('name')
            if target_user:
                await self.channel_layer.group_send(
                    target_user,
                    {
                        'type': 'call_received',
                        'data': {
                            'caller': self.my_name,
                            'rtcMessage': data.get('rtcMessage')
                        }
                    }
                )

        elif eventType == 'answer_call':
            caller = data.get('caller')
            if caller:
                await self.channel_layer.group_send(
                    caller,
                    {
                        'type': 'call_answered',
                        'data': {
                            'rtcMessage': data.get('rtcMessage')
                        }
                    }
                )

        elif eventType == 'ICEcandidate':
            target_user = data.get('user')
            if target_user:
                await self.channel_layer.group_send(
                    target_user,
                    {
                        'type': 'ICEcandidate',
                        'data': {
                            'rtcMessage': data.get('rtcMessage')
                        }
                    }
                )

    # Event handlers for sending data to WebSocket
    async def call_received(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call_received',
            'data': event['data']
        }))

    async def call_answered(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call_answered',
            'data': event['data']
        }))

    async def ICEcandidate(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ICEcandidate',
            'data': event['data']
        }))
