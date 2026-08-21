"""Pydantic models for the multiplayer Mafia platform."""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime, timezone
import uuid


def uid() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =========== Auth Models ===========
class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    display_name: str = Field(min_length=2, max_length=32)
    email: EmailStr
    password: str = Field(min_length=6, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    username: str
    display_name: str
    email: str
    role: str = "USER"
    status: str = "ACTIVE"


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


# =========== Room / Game Models ===========
class MafiaSettings(BaseModel):
    max_players: int = Field(ge=4, le=20)
    mafia_count: int = Field(ge=1, le=6)
    doctor_count: int = Field(ge=0, le=3)
    detective_count: int = Field(ge=0, le=3)
    mafia_discussion_seconds: int = Field(ge=10, le=180, default=20)
    night_actions_seconds: int = Field(ge=15, le=180, default=30)
    discussion_seconds: int = Field(ge=15, le=300, default=60)
    voting_seconds: int = Field(ge=15, le=180, default=30)
    reveal_eliminated_role: bool = False
    host_can_view_mafia_chat: bool = False


class CreateRoomRequest(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    game_type: Literal["mafia"] = "mafia"
    settings: MafiaSettings


class JoinRoomRequest(BaseModel):
    room_code: str = Field(min_length=4, max_length=10)


class RoomPublic(BaseModel):
    id: str
    room_code: str
    host_id: str
    host_name: str
    game_type: str
    name: str
    status: str
    max_players: int
    settings: MafiaSettings
    player_count: int
    created_at: str


class PlayerPublic(BaseModel):
    user_id: str
    display_name: str
    username: str
    connection_status: str
    alive: bool = True
    is_host: bool = False


# =========== Night Action / Vote ===========
class NightActionRequest(BaseModel):
    action_type: Literal["KILL", "PROTECT", "INVESTIGATE"]
    target_user_id: str


class VoteRequest(BaseModel):
    target_user_id: str


class MafiaMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class PublicMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class ReactionRequest(BaseModel):
    emoji: str = Field(min_length=1, max_length=8)


class MafiaTargetVoteRequest(BaseModel):
    target_user_id: str


# =========== Connected Accounts (streaming platforms) ===========
PROVIDER_LITERAL = Literal["twitch", "youtube", "tiktok", "kick"]


class ConnectedAccountCreate(BaseModel):
    provider: PROVIDER_LITERAL
    provider_username: str = Field(min_length=1, max_length=100)
    channel_url: Optional[str] = Field(default=None, max_length=500)
    display_name: Optional[str] = Field(default=None, max_length=100)


class ConnectedAccountPublic(BaseModel):
    id: str
    provider: str
    provider_username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    channel_url: Optional[str] = None
    connected_at: str
