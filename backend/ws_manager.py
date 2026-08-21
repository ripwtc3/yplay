"""In-memory WebSocket connection manager (single-process modular monolith)."""
from fastapi import WebSocket
from typing import Dict, Set, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self):
        # user_id -> WebSocket
        self.user_sockets: Dict[str, WebSocket] = {}
        # room_id -> set of user_ids currently subscribed
        self.room_users: Dict[str, Set[str]] = {}
        # user_id -> room_id (current subscription)
        self.user_room: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            # Close any previous socket for this user
            old = self.user_sockets.get(user_id)
            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass
            self.user_sockets[user_id] = ws

    async def disconnect(self, user_id: str):
        async with self._lock:
            self.user_sockets.pop(user_id, None)
            room_id = self.user_room.pop(user_id, None)
            if room_id and room_id in self.room_users:
                self.room_users[room_id].discard(user_id)
        return room_id

    async def subscribe(self, user_id: str, room_id: str):
        async with self._lock:
            # remove from old room
            old_room = self.user_room.get(user_id)
            if old_room and old_room in self.room_users:
                self.room_users[old_room].discard(user_id)
            self.user_room[user_id] = room_id
            self.room_users.setdefault(room_id, set()).add(user_id)

    async def send_to_user(self, user_id: str, message: dict):
        ws = self.user_sockets.get(user_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"send_to_user failed {user_id}: {e}")
            return False

    async def broadcast_room(self, room_id: str, message: dict, exclude: Optional[str] = None):
        user_ids = list(self.room_users.get(room_id, set()))
        for uid in user_ids:
            if exclude and uid == exclude:
                continue
            await self.send_to_user(uid, message)

    def is_online(self, user_id: str) -> bool:
        return user_id in self.user_sockets


ws_manager = WSManager()
