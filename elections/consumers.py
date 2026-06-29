import json
from channels.generic.websocket import AsyncWebsocketConsumer

class DashboardConsumer(AsyncWebsocketConsumer):
    """
    Real-time WebSocket consumer for the National Dashboard.
    When results are submitted, this pushes updates to all connected clients.
    """

    async def connect(self):
        # Join the dashboard group
        self.room_group_name = 'dashboard_live'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        
        # Send welcome message
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': '🔴 Live Mode Active - Connected to War Room'
        }))

    async def disconnect(self, close_code):
        # Leave the dashboard group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        pass  # We only push from server, clients just listen

    # Receive message from Django (triggered by views)
    async def dashboard_update(self, event):
        """
        Called when the view sends a 'dashboard.update' message.
        Forwards the data to the WebSocket client.
        """
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': event['data']
        }))

    async def result_submitted(self, event):
        """
        Called when a new result is submitted.
        Sends a notification + updated stats to all connected clients.
        """
        await self.send(text_data=json.dumps({
            'type': 'result_submitted',
            'data': event['data']
        }))