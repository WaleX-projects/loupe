import asyncio
from .manager import manager

class EventPump:
    def __init__(self, project_id: str):
        self.project_id = project_id

    async def emit(self, event_type: str, message: str, details: dict = None):
        """Pushes real-time agent state, tool calls, or logs to the WebSocket."""
        payload = {
            "message": message,
            "details": details or {}
        }
        await manager.send_event(self.project_id, event_type, payload)

    async def wait_for_human_approval(self, prompt_summary: str) -> str:
        """Pauses agent execution until the user approves or responds via WebSocket."""
        await self.emit("approval_required", prompt_summary)
        
        # Clear any old input
        manager.pending_inputs.pop(self.project_id, None)

        # Poll until user responds
        while self.project_id not in manager.pending_inputs:
            await asyncio.sleep(0.5)

        return manager.pending_inputs.pop(self.project_id)