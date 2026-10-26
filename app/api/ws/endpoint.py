import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from .manager import manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])

async def authenticate_ws(token: str | None) -> str | None:
    if not token or token != "secret-test-token":
        return None
    return "authorized-user-id"

@router.websocket("/projects/{project_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    project_id: str, 
    token: str = Query(...)
):
    # 1. Authentication Handshake
    user_id = await authenticate_ws(token)
    if not user_id:
        await websocket.close(code=status.WS_4008_POLICY_VIOLATION)
        return

    # 2. Connection Registration
    await manager.connect(project_id, websocket)

    # 3. Start Redis Pub/Sub listener task for this connection
    redis_listener = asyncio.create_task(manager.listen_to_redis(project_id, websocket))
    
    try:
        # 4. Receive Loop (for client-to-server messages like approvals)
        while True:
            raw_data = await websocket.receive_text()
            await manager.handle_incoming_message(project_id, raw_data)
            
    except WebSocketDisconnect:
        redis_listener.cancel()
        manager.disconnect(project_id)