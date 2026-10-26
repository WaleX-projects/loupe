import json
import asyncio
from typing import Dict
from fastapi import WebSocket
from app.services.redis_client import redis_client

class ConnectionManager:
    def __init__(self):
        # Maps project_id -> active WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}
        # Stores pending human-in-the-loop responses
        self.pending_inputs: Dict[str, str] = {}

    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[project_id] = websocket

    def disconnect(self, project_id: str):
        self.active_connections.pop(project_id, None)

    async def send_event(self, project_id: str, event_type: str, data: dict):
        """Publishes event to Redis channel so any worker or server instance can broadcast it."""
        payload = json.dumps({"type": event_type, "data": data},default=str)
        
        await redis_client.publish(f"project:{project_id}:events", payload)

    async def listen_to_redis(self, project_id: str, websocket: WebSocket):
        """Subscribes to the project's Redis channel and forwards events to the WebSocket."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"project:{project_id}:events")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])
        except asyncio.CancelledError:
            await pubsub.unsubscribe(f"project:{project_id}:events")

    async def handle_incoming_message(self, project_id: str, raw_message: str):
        """Handles human-in-the-loop responses from the client."""
        try:
            msg = json.loads(raw_message)
            action = msg.get("action")
            content = msg.get("content")

            if action in ["approve", "cancel", "user_input"]:
                self.pending_inputs[project_id] = content
        except Exception as e:
            print(f"Error handling WS message for project {project_id}: {e}")

manager = ConnectionManager()