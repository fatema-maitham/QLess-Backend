# controllers/realtime.py
from typing import Optional

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from config.environment import JWT_SECRET
from database import SessionLocal
from models.queue import QueueModel
from models.user import UserModel
from realtime.queue_updates import manager, queue_message

router = APIRouter(tags=["Real-time"])


def user_from_token(db, token: Optional[str]):
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return db.query(UserModel).filter(UserModel.id == payload.get("sub"), UserModel.is_active.is_(True)).first()


@router.websocket("/ws/queues/{queue_id}")
async def queue_socket(websocket: WebSocket, queue_id: int, token: Optional[str] = None):
    with SessionLocal() as db:
        user = user_from_token(db, token)
        queue = db.query(QueueModel).filter(QueueModel.id == queue_id).first()

        if not user or not queue:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        first_message = queue_message(db, queue, "connected")

    await manager.connect(queue_id, websocket)
    await websocket.send_json(first_message)

    try:
        # Keep the connection open. We don't expect messages from the browser.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(queue_id, websocket)