"""FastAPI server for the multiplayer Mafia platform."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re

from models import (
    RegisterRequest, LoginRequest, AuthResponse, UserPublic,
    CreateRoomRequest, JoinRoomRequest, RoomPublic, MafiaSettings,
    NightActionRequest, VoteRequest, MafiaMessageRequest, MafiaTargetVoteRequest,
    ConnectedAccountCreate, ConnectedAccountPublic, uid, now_iso,
)
from auth import (
    hash_password, verify_password, create_token,
    get_current_user, get_user_from_token_str,
)
from ws_manager import ws_manager
from mafia_engine import init_engine, get_engine, generate_room_code

# MongoDB
mongo_url = os.environ["MONGO_URL"]
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client[os.environ["DB_NAME"]]

# App
app = FastAPI(title="Mafia Platform")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("username", unique=True)
    await db.users.create_index("id", unique=True)
    await db.rooms.create_index("id", unique=True)
    await db.rooms.create_index("room_code", unique=True)
    await db.room_players.create_index([("room_id", 1), ("user_id", 1)], unique=True)
    await db.mafia_actions.create_index(
        [("session_id", 1), ("round_number", 1), ("actor_id", 1), ("action_type", 1)],
        unique=True,
    )
    await db.votes.create_index(
        [("session_id", 1), ("round_number", 1), ("voter_id", 1)],
        unique=True,
    )
    await db.game_messages.create_index([("room_id", 1), ("created_at", 1)])
    await db.connected_accounts.create_index([("user_id", 1), ("provider", 1)], unique=True)
    init_engine(db)
    logger.info("Startup complete.")


@app.on_event("shutdown")
async def on_shutdown():
    mongo_client.close()


# ============= Health =============
@api.get("/")
async def root():
    return {"message": "Mafia Platform API", "status": "ok"}


# ============= Auth =============
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,24}$")


@api.post("/auth/register", response_model=AuthResponse)
async def register(payload: RegisterRequest):
    if not USERNAME_RE.match(payload.username):
        raise HTTPException(400, "اسم المستخدم يجب أن يحتوي أحرف/أرقام فقط (3-24)")
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "البريد مستخدم مسبقاً")
    if await db.users.find_one({"username": payload.username}):
        raise HTTPException(400, "اسم المستخدم مأخوذ")

    user_id = uid()
    doc = {
        "id": user_id,
        "username": payload.username,
        "display_name": payload.display_name,
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": "USER",
        "status": "ACTIVE",
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    token = create_token(user_id)
    return AuthResponse(
        token=token,
        user=UserPublic(
            id=user_id, username=payload.username, display_name=payload.display_name,
            email=email, role="USER", status="ACTIVE",
        ),
    )


@api.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginRequest):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "بيانات الدخول غير صحيحة")
    if user.get("status") in ("SUSPENDED", "BANNED"):
        raise HTTPException(403, "الحساب موقوف")
    token = create_token(user["id"])
    return AuthResponse(
        token=token,
        user=UserPublic(
            id=user["id"], username=user["username"], display_name=user["display_name"],
            email=user["email"], role=user.get("role", "USER"),
            status=user.get("status", "ACTIVE"),
        ),
    )


@api.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return UserPublic(
        id=user["id"], username=user["username"], display_name=user["display_name"],
        email=user["email"], role=user.get("role", "USER"),
        status=user.get("status", "ACTIVE"),
    )


# ============= Rooms =============
async def _room_public(room: dict) -> RoomPublic:
    host = await db.users.find_one({"id": room["host_id"]}, {"_id": 0, "display_name": 1})
    count = await db.room_players.count_documents({"room_id": room["id"]})
    return RoomPublic(
        id=room["id"], room_code=room["room_code"], host_id=room["host_id"],
        host_name=host["display_name"] if host else "",
        game_type=room["game_type"], name=room["name"], status=room["status"],
        max_players=room["max_players"], settings=MafiaSettings(**room["settings"]),
        player_count=count, created_at=room["created_at"],
    )


@api.post("/rooms", response_model=RoomPublic)
async def create_room(payload: CreateRoomRequest, user=Depends(get_current_user)):
    s = payload.settings
    total_special = s.mafia_count + s.doctor_count + s.detective_count
    if total_special >= s.max_players:
        raise HTTPException(400, "مجموع أعداد الأدوار يجب أن يكون أقل من عدد اللاعبين")
    if s.mafia_count < 1:
        raise HTTPException(400, "لابد من وجود Mafia واحد على الأقل")
    if s.mafia_count * 2 >= s.max_players:
        raise HTTPException(400, "عدد Mafia كبير جداً بالنسبة لعدد اللاعبين")

    # generate unique room_code
    for _ in range(10):
        code = generate_room_code(6)
        if not await db.rooms.find_one({"room_code": code}):
            break
    else:
        raise HTTPException(500, "تعذر توليد كود غرفة")

    room_id = uid()
    room = {
        "id": room_id,
        "room_code": code,
        "host_id": user["id"],
        "game_type": payload.game_type,
        "name": payload.name,
        "status": "LOBBY",
        "max_players": s.max_players,
        "settings": s.model_dump(),
        "created_at": now_iso(),
        "started_at": None,
        "ended_at": None,
    }
    await db.rooms.insert_one(room)

    # Host auto-joins as player
    await db.room_players.insert_one({
        "id": uid(),
        "room_id": room_id,
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "status": "IN_LOBBY",
        "connection_status": "ONLINE",
        "joined_at": now_iso(),
        "eliminated_at": None,
    })

    return await _room_public(room)


@api.get("/rooms/mine")
async def get_my_active_room(user=Depends(get_current_user)):
    # find room where user is either host or a player and not FINISHED/CANCELLED
    membership = await db.room_players.find_one({"user_id": user["id"]})
    if not membership:
        return {"room": None}
    room = await db.rooms.find_one({"id": membership["room_id"]}, {"_id": 0})
    if not room or room["status"] in ("FINISHED", "CANCELLED"):
        return {"room": None}
    return {"room": (await _room_public(room)).model_dump()}


@api.post("/rooms/join", response_model=RoomPublic)
async def join_room(payload: JoinRoomRequest, user=Depends(get_current_user)):
    code = payload.room_code.strip().upper()
    room = await db.rooms.find_one({"room_code": code}, {"_id": 0})
    if not room:
        raise HTTPException(404, "الغرفة غير موجودة")
    if room["status"] != "LOBBY":
        raise HTTPException(400, "هذه اللعبة بدأت بالفعل ولا يمكن الانضمام الآن")

    existing = await db.room_players.find_one({"room_id": room["id"], "user_id": user["id"]})
    if existing:
        return await _room_public(room)

    count = await db.room_players.count_documents({"room_id": room["id"]})
    if count >= room["max_players"]:
        raise HTTPException(400, "الغرفة ممتلئة")

    await db.room_players.insert_one({
        "id": uid(),
        "room_id": room["id"],
        "user_id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "status": "IN_LOBBY",
        "connection_status": "ONLINE",
        "joined_at": now_iso(),
        "eliminated_at": None,
    })

    # Broadcast update
    await ws_manager.broadcast_room(room["id"], {
        "type": "PLAYER_JOINED",
        "user": {
            "user_id": user["id"],
            "display_name": user["display_name"],
            "username": user["username"],
        },
        "players": await _lobby_players(room["id"], room["host_id"]),
    })
    return await _room_public(room)


async def _lobby_players(room_id: str, host_id: str):
    players = await db.room_players.find({"room_id": room_id}, {"_id": 0}).to_list(1000)
    return [
        {
            "user_id": p["user_id"],
            "display_name": p["display_name"],
            "username": p["username"],
            "connection_status": "ONLINE" if ws_manager.is_online(p["user_id"]) else "OFFLINE",
            "is_host": p["user_id"] == host_id,
            "alive": True,
        }
        for p in players
    ]


@api.get("/rooms/{room_id}")
async def get_room(room_id: str, user=Depends(get_current_user)):
    room = await db.rooms.find_one({"id": room_id}, {"_id": 0})
    if not room:
        raise HTTPException(404, "الغرفة غير موجودة")
    # must be a member
    membership = await db.room_players.find_one({"room_id": room_id, "user_id": user["id"]})
    if not membership and room["host_id"] != user["id"]:
        raise HTTPException(403, "لست عضواً في الغرفة")
    public = (await _room_public(room)).model_dump()
    public["players"] = await _lobby_players(room_id, room["host_id"])
    return public


@api.post("/rooms/{room_id}/start")
async def start_game(room_id: str, user=Depends(get_current_user)):
    ok, msg = await get_engine().start_game(room_id, user["id"])
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


@api.post("/rooms/{room_id}/leave")
async def leave_room(room_id: str, user=Depends(get_current_user)):
    room = await db.rooms.find_one({"id": room_id})
    if not room:
        raise HTTPException(404, "الغرفة غير موجودة")
    if room["status"] != "LOBBY":
        raise HTTPException(400, "لا يمكن مغادرة اللعبة أثناء التشغيل")
    if room["host_id"] == user["id"]:
        # host cancels room
        await db.rooms.update_one({"id": room_id}, {"$set": {"status": "CANCELLED", "ended_at": now_iso()}})
        await db.room_players.delete_many({"room_id": room_id})
        await ws_manager.broadcast_room(room_id, {"type": "ROOM_CANCELLED"})
    else:
        await db.room_players.delete_one({"room_id": room_id, "user_id": user["id"]})
        await ws_manager.broadcast_room(room_id, {
            "type": "PLAYER_LEFT",
            "user_id": user["id"],
            "players": await _lobby_players(room_id, room["host_id"]),
        })
    return {"ok": True}


# ============= Game State (secure) =============
@api.get("/rooms/{room_id}/state")
async def game_state(room_id: str, user=Depends(get_current_user)):
    room = await db.rooms.find_one({"id": room_id}, {"_id": 0})
    if not room:
        raise HTTPException(404, "الغرفة غير موجودة")
    # Membership check (same as get_room)
    membership = await db.room_players.find_one({"room_id": room_id, "user_id": user["id"]})
    if not membership and room["host_id"] != user["id"]:
        raise HTTPException(403, "لست عضواً في الغرفة")
    session = await db.game_sessions.find_one({"room_id": room_id}, {"_id": 0})
    my_role = None
    my_alive = True
    mafia_partners = []
    if session:
        for p in session["players"]:
            if p["user_id"] == user["id"]:
                my_role = p["role"]
                my_alive = p["alive"]
                break
        if my_role == "MAFIA":
            mafia_partners = [
                {"user_id": p["user_id"], "display_name": p["display_name"]}
                for p in session["players"] if p["role"] == "MAFIA" and p["user_id"] != user["id"]
            ]
        # public players
        public_players = [
            {
                "user_id": p["user_id"],
                "display_name": p["display_name"],
                "username": p["username"],
                "alive": p["alive"],
                "connection_status": "ONLINE" if ws_manager.is_online(p["user_id"]) else "OFFLINE",
                "is_host": p["user_id"] == session["host_id"],
                "role": p["role"] if session.get("current_phase") == "GAME_OVER" else None,
            }
            for p in session["players"]
        ]
        # my private night action already submitted?
        my_action = None
        if my_role in ("MAFIA", "DOCTOR", "DETECTIVE") and my_alive:
            my_action = await db.mafia_actions.find_one({
                "session_id": session["id"],
                "round_number": session["round_number"],
                "actor_id": user["id"],
            }, {"_id": 0})
        my_vote = None
        if my_alive:
            my_vote = await db.votes.find_one({
                "session_id": session["id"],
                "round_number": session["round_number"],
                "voter_id": user["id"],
            }, {"_id": 0})
        return {
            "room": (await _room_public(room)).model_dump(),
            "session": {
                "current_phase": session["current_phase"],
                "round_number": session["round_number"],
                "phase_started_at": session.get("phase_started_at"),
                "phase_ends_at": session.get("phase_ends_at"),
                "winner": session.get("winner"),
                "players": public_players,
            },
            "me": {
                "user_id": user["id"],
                "role": my_role,
                "alive": my_alive,
                "mafia_partners": mafia_partners,
                "night_action": my_action,
                "vote": my_vote,
            },
        }
    return {
        "room": (await _room_public(room)).model_dump(),
        "session": None,
        "me": {"user_id": user["id"], "role": None, "alive": True},
    }


@api.post("/rooms/{room_id}/night-action")
async def night_action(room_id: str, payload: NightActionRequest, user=Depends(get_current_user)):
    ok, msg = await get_engine().submit_night_action(room_id, user["id"], payload.action_type, payload.target_user_id)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


@api.post("/rooms/{room_id}/vote")
async def cast_vote(room_id: str, payload: VoteRequest, user=Depends(get_current_user)):
    ok, msg = await get_engine().submit_vote(room_id, user["id"], payload.target_user_id)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


# ============= Mafia Private Chat & Target Vote =============
@api.get("/rooms/{room_id}/mafia-state")
async def mafia_state(room_id: str, user=Depends(get_current_user)):
    state = await get_engine().get_mafia_private_state(room_id, user["id"])
    if state is None:
        raise HTTPException(403, "غير مسموح لك بالوصول لهذه الغرفة السرية")
    return state


@api.post("/rooms/{room_id}/mafia-message")
async def send_mafia_message(room_id: str, payload: MafiaMessageRequest, user=Depends(get_current_user)):
    ok, msg = await get_engine().send_mafia_message(room_id, user["id"], payload.message)
    if not ok:
        raise HTTPException(403, msg)
    return {"ok": True, "message": msg}


@api.post("/rooms/{room_id}/mafia-target-vote")
async def submit_mafia_target(room_id: str, payload: MafiaTargetVoteRequest, user=Depends(get_current_user)):
    ok, msg = await get_engine().submit_mafia_target_vote(room_id, user["id"], payload.target_user_id)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


# ============= Connected Accounts =============
def _account_public(doc: dict) -> ConnectedAccountPublic:
    return ConnectedAccountPublic(
        id=doc["id"],
        provider=doc["provider"],
        provider_username=doc["provider_username"],
        display_name=doc.get("display_name"),
        avatar_url=doc.get("avatar_url"),
        channel_url=doc.get("channel_url"),
        connected_at=doc["connected_at"],
    )


PROVIDER_BASE_URL = {
    "twitch": "https://www.twitch.tv/",
    "youtube": "https://www.youtube.com/@",
    "tiktok": "https://www.tiktok.com/@",
    "kick": "https://kick.com/",
}


@api.get("/users/me/connected-accounts")
async def list_connected(user=Depends(get_current_user)):
    docs = await db.connected_accounts.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
    return {"accounts": [_account_public(d).model_dump() for d in docs]}


@api.post("/users/me/connected-accounts", response_model=ConnectedAccountPublic)
async def add_connected(payload: ConnectedAccountCreate, user=Depends(get_current_user)):
    handle = payload.provider_username.strip().lstrip("@")
    if not handle:
        raise HTTPException(400, "اسم القناة مطلوب")
    channel_url = payload.channel_url or (PROVIDER_BASE_URL.get(payload.provider, "") + handle)
    doc = {
        "id": uid(),
        "user_id": user["id"],
        "provider": payload.provider,
        "provider_username": handle,
        "provider_account_id": None,
        "display_name": payload.display_name or handle,
        "avatar_url": None,
        "channel_url": channel_url,
        "access_token_encrypted": None,
        "refresh_token_encrypted": None,
        "token_expires_at": None,
        "connected_at": now_iso(),
        "updated_at": now_iso(),
    }
    try:
        await db.connected_accounts.insert_one(doc)
    except Exception:
        raise HTTPException(400, "لديك حساب مربوط بالفعل بهذه المنصة — احذفه أولاً")
    return _account_public(doc)


@api.delete("/users/me/connected-accounts/{account_id}")
async def delete_connected(account_id: str, user=Depends(get_current_user)):
    res = await db.connected_accounts.delete_one({"id": account_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "الحساب غير موجود")
    return {"ok": True}


# ============= WebSocket =============
@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    user = await get_user_from_token_str(token)
    if not user:
        await websocket.close(code=4401)
        return
    user_id = user["id"]
    await ws_manager.connect(user_id, websocket)
    room_id_current = None
    try:
        # send hello
        await websocket.send_json({"type": "CONNECTED", "user_id": user_id})
        while True:
            msg = await websocket.receive_json()
            mtype = msg.get("type")
            if mtype == "SUBSCRIBE_ROOM":
                room_id = msg.get("room_id")
                if not room_id:
                    continue
                # verify user is member
                membership = await db.room_players.find_one({"room_id": room_id, "user_id": user_id})
                room = await db.rooms.find_one({"id": room_id})
                if not membership and (not room or room["host_id"] != user_id):
                    await websocket.send_json({"type": "ERROR", "message": "غير مسموح لك بمشاهدة هذه الغرفة"})
                    continue
                await ws_manager.subscribe(user_id, room_id)
                room_id_current = room_id
                # notify others player is online
                await ws_manager.broadcast_room(room_id, {
                    "type": "PLAYER_ONLINE",
                    "user_id": user_id,
                    "players": await _lobby_players(room_id, room["host_id"]),
                })
            elif mtype == "PING":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WS error {user_id}: {e}")
    finally:
        room_left = await ws_manager.disconnect(user_id)
        if room_left:
            room = await db.rooms.find_one({"id": room_left})
            if room:
                await ws_manager.broadcast_room(room_left, {
                    "type": "PLAYER_OFFLINE",
                    "user_id": user_id,
                    "players": await _lobby_players(room_left, room["host_id"]),
                })


# ============= Mount =============
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
