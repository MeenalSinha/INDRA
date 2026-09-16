"""
WebSocket fan-out. Each connected browser gets its own subscriber queue on
the in-process bus (realtime/pubsub.py) and a dedicated forwarding task, so
one slow client can't block others. Reconnect is handled client-side
(frontend/js/ws.js retries with backoff) -- the spec requires WebSockets to
reconnect gracefully.
"""
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from . import pubsub


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    queue = pubsub.subscribe()
    try:
        while True:
            message = await queue.get()
            await websocket.send_text(json.dumps(message))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        pubsub.unsubscribe(queue)
        manager.disconnect(websocket)
