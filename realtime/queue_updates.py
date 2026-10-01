# realtime/queue_updates.py
from collections import defaultdict

import anyio
from fastapi import WebSocket
from sqlalchemy.orm import Session

from models.queue import QueueModel
from models.queue_entry import QueueEntryModel


class QueueConnectionManager:
    """Keeps track of who is watching each queue."""

    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, queue_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections[queue_id].add(websocket)

    def disconnect(self, queue_id: int, websocket: WebSocket):
        watchers = self.connections.get(queue_id)
        if watchers is None:
            return
        watchers.discard(websocket)
        if not watchers:
            self.connections.pop(queue_id, None)

    async def broadcast(self, queue_id: int, message: dict):
        dead = []
        for websocket in list(self.connections.get(queue_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(queue_id, websocket)


manager = QueueConnectionManager()


def queue_message(db: Session, queue: QueueModel, event: str, **extra) -> dict:
    """Build the message sent to everyone watching a queue."""
    waiting = (
        db.query(QueueEntryModel)
        .filter(QueueEntryModel.queue_id == queue.id, QueueEntryModel.status == "waiting")
        .count()
    )
    return {
        "type": event,
        "queue_id": queue.id,
        "queue_status": queue.status,
        "current_number": queue.current_number,
        "waiting_count": waiting,
        **extra,
    }


def broadcast(queue_id: int, message: dict):
    """Call this from normal routes, after db.commit()."""
    try:
        anyio.from_thread.run(manager.broadcast, queue_id, message)
    except RuntimeError:
        # Not running inside a FastAPI request (e.g. a script), so nobody to tell
        pass