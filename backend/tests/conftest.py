"""Shared fixtures and helpers for Mafia platform backend tests."""
import os
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

_frontend_env = dotenv_values("/app/frontend/.env")
_base = os.environ.get("REACT_APP_BACKEND_URL") or _frontend_env.get("REACT_APP_BACKEND_URL")
if not _base:
    raise RuntimeError("REACT_APP_BACKEND_URL missing from env and /app/frontend/.env")
BASE_URL = _base.rstrip("/")
API = f"{BASE_URL}/api"
WS_URL = API.replace("https://", "wss://").replace("http://", "ws://") + "/ws"

_backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or _backend_env.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or _backend_env.get("DB_NAME")

TEST_PREFIX = "TEST_"


# ---------------- helpers ----------------
def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def register_user(tag: str) -> dict:
    """Register a brand-new user; returns {token, user, session}."""
    suffix = uuid.uuid4().hex[:10]
    username = f"t_{tag}_{suffix}"[:24]
    payload = {
        "username": username,
        "display_name": f"{TEST_PREFIX}{tag}",
        "email": f"{TEST_PREFIX.lower()}{tag}_{suffix}@qa-test.com",
        "password": "secret123",
    }
    r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"register failed {r.status_code}: {r.text[:400]}")
    data = r.json()
    assert "token" in data and "user" in data
    s = new_session()
    s.headers.update({"Authorization": f"Bearer {data['token']}"})
    return {"token": data["token"], "user": data["user"], "s": s, "email": payload["email"]}


def get_state(user: dict, room_id: str) -> dict:
    r = user["s"].get(f"{API}/rooms/{room_id}/state", timeout=30)
    assert r.status_code == 200, f"/state failed {r.status_code}: {r.text[:300]}"
    return r.json()


def wait_for_phase(user: dict, room_id: str, phases, timeout: float = 60.0, interval: float = 1.5):
    """Poll /state until current_phase is in `phases`. Returns the state or None."""
    if isinstance(phases, str):
        phases = [phases]
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        st = get_state(user, room_id)
        sess = st.get("session")
        if sess:
            last = sess.get("current_phase")
            if last in phases:
                return st
        time.sleep(interval)
    return None


def create_room(host: dict, settings: dict, name=None) -> dict:
    body = {"name": name or f"{TEST_PREFIX}room_{uuid.uuid4().hex[:6]}", "game_type": "mafia", "settings": settings}
    r = host["s"].post(f"{API}/rooms", json=body, timeout=30)
    assert r.status_code == 200, f"create_room failed {r.status_code}: {r.text[:400]}"
    return r.json()


def join_room(user: dict, room_code: str):
    r = user["s"].post(f"{API}/rooms/join", json={"room_code": room_code}, timeout=30)
    assert r.status_code == 200, f"join failed {r.status_code}: {r.text[:300]}"
    return r.json()


def roles_map(host: dict, room_id: str, users: list) -> dict:
    """Map role -> list of user dicts, using each user's own /state me.role."""
    out = {}
    for u in users:
        st = get_state(u, room_id)
        role = st["me"]["role"]
        out.setdefault(role, []).append(u)
    return out


def mongo_cleanup(emails, room_ids):
    if not MONGO_URL or not DB_NAME:
        return
    cli = MongoClient(MONGO_URL)
    db = cli[DB_NAME]
    users = list(db.users.find({"email": {"$in": [e.lower() for e in emails]}}, {"id": 1}))
    uids = [u["id"] for u in users]
    db.users.delete_many({"email": {"$in": [e.lower() for e in emails]}})
    db.connected_accounts.delete_many({"user_id": {"$in": uids}})
    if room_ids:
        db.rooms.delete_many({"id": {"$in": room_ids}})
        db.room_players.delete_many({"room_id": {"$in": room_ids}})
        db.game_messages.delete_many({"room_id": {"$in": room_ids}})
        db.mafia_actions.delete_many({"room_id": {"$in": room_ids}})
        db.votes.delete_many({"room_id": {"$in": room_ids}})
        db.game_sessions.delete_many({"room_id": {"$in": room_ids}})
    cli.close()


@pytest.fixture(scope="class")
def tracker():
    """Track created emails/rooms; cleaned up after the class."""
    data = {"emails": [], "rooms": []}
    yield data
    try:
        mongo_cleanup(data["emails"], data["rooms"])
    except Exception as e:  # pragma: no cover
        print(f"cleanup warning: {e}")


@pytest.fixture(scope="class")
def make_user(tracker):
    def _make(tag):
        u = register_user(tag)
        tracker["emails"].append(u["email"])
        return u
    return _make
