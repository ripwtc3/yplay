"""
MafiaGameEngine: server-authoritative game state machine.

Phases:
  LOBBY -> ROLE_ASSIGNMENT -> MAFIA_DISCUSSION -> NIGHT_ACTIONS -> NIGHT_RESULT
   -> DISCUSSION -> VOTING -> VOTE_RESULT -> CHECK_WIN -> (MAFIA_DISCUSSION | GAME_OVER)

During MAFIA_DISCUSSION:
  - Alive mafia can chat privately (broadcast via mafia sub-channel only)
  - Alive mafia can vote a KILL target (upsertable)
  - Doctor/Detective/Citizen see 'Night ongoing, wait...'
During NIGHT_ACTIONS:
  - Mafia can still change/confirm KILL target
  - Doctor submits PROTECT
  - Detective submits INVESTIGATE
"""
import asyncio
import random
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Set
from collections import Counter

from ws_manager import ws_manager
from models import now_iso

logger = logging.getLogger(__name__)


ROLES = ["MAFIA", "CITIZEN", "DOCTOR", "DETECTIVE"]


def generate_room_code(length: int = 6) -> str:
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(alphabet, k=length))


class MafiaEngine:
    def __init__(self, db):
        self.db = db
        self._tasks: Dict[str, asyncio.Task] = {}

    # ---------- helpers ----------
    async def _get_session(self, room_id: str):
        return await self.db.game_sessions.find_one({"room_id": room_id}, {"_id": 0})

    async def _get_room(self, room_id: str):
        return await self.db.rooms.find_one({"id": room_id}, {"_id": 0})

    async def _public_players(self, room_id: str) -> List[dict]:
        session = await self._get_session(room_id)
        if not session:
            return []
        return [
            {
                "user_id": p["user_id"],
                "display_name": p["display_name"],
                "username": p["username"],
                "alive": p["alive"],
                "connection_status": "ONLINE" if ws_manager.is_online(p["user_id"]) else "OFFLINE",
                "is_host": p["user_id"] == session.get("host_id"),
                "eliminated_at": p.get("eliminated_at"),
            }
            for p in session.get("players", [])
        ]

    def _get_role(self, session: dict, user_id: str) -> Optional[str]:
        for p in session.get("players", []):
            if p["user_id"] == user_id:
                return p.get("role")
        return None

    def _is_alive(self, session: dict, user_id: str) -> bool:
        for p in session.get("players", []):
            if p["user_id"] == user_id:
                return p.get("alive", False)
        return False

    def _refresh_mafia_channel(self, room_id: str, session: dict):
        """Sync ws_manager.mafia_channel with alive mafia (and host if allowed)."""
        alive_mafia = {p["user_id"] for p in session["players"] if p["alive"] and p["role"] == "MAFIA"}
        if session.get("settings", {}).get("host_can_view_mafia_chat"):
            alive_mafia.add(session["host_id"])
        ws_manager.set_mafia_members(room_id, alive_mafia)

    # ---------- Start Game / Assign Roles ----------
    async def start_game(self, room_id: str, host_id: str) -> Tuple[bool, str]:
        room = await self._get_room(room_id)
        if not room:
            return False, "الغرفة غير موجودة"
        if room["host_id"] != host_id:
            return False, "لست صاحب الغرفة"
        if room["status"] != "LOBBY":
            return False, "لا يمكن بدء اللعبة الآن"

        players = await self.db.room_players.find({"room_id": room_id}, {"_id": 0}).to_list(1000)
        if len(players) < room["max_players"]:
            return False, f"بانتظار {room['max_players'] - len(players)} لاعبين"

        settings = room["settings"]
        needed = settings["mafia_count"] + settings["doctor_count"] + settings["detective_count"]
        if needed >= len(players):
            return False, "توزيع الأدوار غير صحيح"

        shuffled = players.copy()
        random.shuffle(shuffled)
        idx = 0
        for _ in range(settings["mafia_count"]):
            shuffled[idx]["role"] = "MAFIA"; idx += 1
        for _ in range(settings["doctor_count"]):
            shuffled[idx]["role"] = "DOCTOR"; idx += 1
        for _ in range(settings["detective_count"]):
            shuffled[idx]["role"] = "DETECTIVE"; idx += 1
        while idx < len(shuffled):
            shuffled[idx]["role"] = "CITIZEN"; idx += 1

        game_players = [
            {
                "user_id": p["user_id"],
                "username": p["username"],
                "display_name": p["display_name"],
                "role": p["role"],
                "alive": True,
                "eliminated_at": None,
            }
            for p in shuffled
        ]

        session = {
            "id": f"session_{room_id}",
            "room_id": room_id,
            "host_id": host_id,
            "current_phase": "ROLE_ASSIGNMENT",
            "round_number": 0,
            "phase_started_at": now_iso(),
            "phase_ends_at": None,
            "players": game_players,
            "settings": settings,
            "reveal_eliminated_role": settings.get("reveal_eliminated_role", False),
            "winner": None,
            "started_at": now_iso(),
            "ended_at": None,
        }
        await self.db.game_sessions.insert_one(session)
        await self.db.rooms.update_one(
            {"id": room_id},
            {"$set": {"status": "ACTIVE", "started_at": now_iso()}},
        )

        # Set mafia channel
        self._refresh_mafia_channel(room_id, session)

        await ws_manager.broadcast_room(room_id, {
            "type": "GAME_STARTED",
            "players": await self._public_players(room_id),
        })
        for p in game_players:
            await ws_manager.send_to_user(p["user_id"], {
                "type": "ROLE_ASSIGNED_PRIVATE",
                "role": p["role"],
                "user_id": p["user_id"],
                "mafia_partners": [
                    {"user_id": mp["user_id"], "display_name": mp["display_name"]}
                    for mp in game_players if mp["role"] == "MAFIA" and mp["user_id"] != p["user_id"]
                ] if p["role"] == "MAFIA" else [],
            })

        await asyncio.sleep(5)
        await self._start_phase(room_id, "MAFIA_DISCUSSION")
        return True, "بدأت اللعبة"

    # ---------- Phase Management ----------
    async def _start_phase(self, room_id: str, phase: str):
        session = await self._get_session(room_id)
        if not session:
            return
        if session.get("current_phase") == "GAME_OVER":
            return

        settings = session["settings"]
        duration_map = {
            "MAFIA_DISCUSSION": settings.get("mafia_discussion_seconds", 20),
            "NIGHT_ACTIONS": settings.get("night_actions_seconds", settings.get("night_seconds", 30)),
            "DISCUSSION": settings["discussion_seconds"],
            "VOTING": settings["voting_seconds"],
            "NIGHT_RESULT": 5,
            "VOTE_RESULT": 5,
        }
        duration = duration_map.get(phase, 5)

        round_number = session["round_number"]
        if phase == "MAFIA_DISCUSSION":
            round_number += 1

        now = datetime.now(timezone.utc)
        ends_ts = now.timestamp() + duration

        await self.db.game_sessions.update_one(
            {"room_id": room_id},
            {"$set": {
                "current_phase": phase,
                "round_number": round_number,
                "phase_started_at": now.isoformat(),
                "phase_ends_at": datetime.fromtimestamp(ends_ts, tz=timezone.utc).isoformat(),
            }},
        )

        payload = {
            "type": "PHASE_STARTED",
            "phase": phase,
            "round_number": round_number,
            "duration_seconds": duration,
            "phase_ends_at_ts": ends_ts,
            "players": await self._public_players(room_id),
        }
        await ws_manager.broadcast_room(room_id, payload)

        old_task = self._tasks.get(room_id)
        if old_task and not old_task.done():
            old_task.cancel()
        self._tasks[room_id] = asyncio.create_task(self._phase_timer(room_id, phase, duration))

    async def _phase_timer(self, room_id: str, phase: str, duration: int):
        try:
            await asyncio.sleep(duration)
            await self._end_phase(room_id, phase)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"phase_timer error: {e}")

    async def _end_phase(self, room_id: str, phase: str):
        session = await self._get_session(room_id)
        if not session or session.get("current_phase") != phase:
            return
        if phase == "MAFIA_DISCUSSION":
            await self._start_phase(room_id, "NIGHT_ACTIONS")
        elif phase == "NIGHT_ACTIONS":
            await self._resolve_night(room_id)
        elif phase == "NIGHT_RESULT":
            if not await self._check_win(room_id):
                await self._start_phase(room_id, "DISCUSSION")
        elif phase == "DISCUSSION":
            await self._start_phase(room_id, "VOTING")
        elif phase == "VOTING":
            await self._resolve_voting(room_id)
        elif phase == "VOTE_RESULT":
            if not await self._check_win(room_id):
                await self._start_phase(room_id, "MAFIA_DISCUSSION")

    # ---------- Mafia Chat ----------
    async def send_mafia_message(self, room_id: str, user_id: str, message: str) -> Tuple[bool, str]:
        session = await self._get_session(room_id)
        if not session:
            return False, "الجلسة غير موجودة"
        if session["current_phase"] not in ("MAFIA_DISCUSSION", "NIGHT_ACTIONS"):
            return False, "المحادثة السرية غير مسموحة الآن"

        role = self._get_role(session, user_id)
        alive = self._is_alive(session, user_id)
        if role != "MAFIA" or not alive:
            # Also allow host if setting enabled
            if not (user_id == session["host_id"] and session["settings"].get("host_can_view_mafia_chat")):
                return False, "غير مسموح لك بالكتابة في هذه الغرفة"

        sender = next((p for p in session["players"] if p["user_id"] == user_id), None)
        sender_name = sender["display_name"] if sender else "Host"

        doc = {
            "id": f"msg_{session['id']}_{session['round_number']}_{user_id}_{now_iso()}",
            "session_id": session["id"],
            "room_id": room_id,
            "round_number": session["round_number"],
            "sender_user_id": user_id,
            "sender_display_name": sender_name,
            "channel_type": "MAFIA",
            "message": message.strip()[:500],
            "created_at": now_iso(),
        }
        await self.db.game_messages.insert_one(doc)

        # Broadcast to mafia channel only
        await ws_manager.broadcast_mafia(room_id, {
            "type": "MAFIA_MESSAGE",
            "message": {
                "id": doc["id"],
                "sender_user_id": user_id,
                "sender_display_name": sender_name,
                "message": doc["message"],
                "round_number": doc["round_number"],
                "created_at": doc["created_at"],
            },
        })
        return True, "تم الإرسال"

    async def list_mafia_messages(self, room_id: str, user_id: str) -> Tuple[bool, List[dict]]:
        session = await self._get_session(room_id)
        if not session:
            return False, []
        role = self._get_role(session, user_id)
        alive = self._is_alive(session, user_id)
        is_host_viewer = user_id == session["host_id"] and session["settings"].get("host_can_view_mafia_chat")
        if not ((role == "MAFIA" and alive) or is_host_viewer):
            return False, []
        msgs = await self.db.game_messages.find(
            {"room_id": room_id, "channel_type": "MAFIA"},
            {"_id": 0},
        ).sort("created_at", 1).to_list(1000)
        return True, msgs

    # ---------- Public Chat (Day Discussion) ----------
    async def send_public_message(self, room_id: str, user_id: str, message: str) -> Tuple[bool, str]:
        session = await self._get_session(room_id)
        if not session:
            return False, "الجلسة غير موجودة"
        if session["current_phase"] not in ("DISCUSSION", "VOTING", "NIGHT_RESULT", "VOTE_RESULT"):
            return False, "لا يمكن الكتابة في هذه المرحلة"

        # Membership + alive check
        role = self._get_role(session, user_id)
        alive = self._is_alive(session, user_id)
        is_host = user_id == session["host_id"]
        if not role and not is_host:
            return False, "لست في اللعبة"
        # Eliminated players cannot post
        if role and not alive:
            return False, "خرجت من اللعبة — يمكنك المشاهدة فقط"

        sender = next((p for p in session["players"] if p["user_id"] == user_id), None)
        sender_name = sender["display_name"] if sender else "Host"

        doc = {
            "id": f"pmsg_{session['id']}_{session['round_number']}_{user_id}_{now_iso()}",
            "session_id": session["id"],
            "room_id": room_id,
            "round_number": session["round_number"],
            "sender_user_id": user_id,
            "sender_display_name": sender_name,
            "channel_type": "PUBLIC",
            "message": message.strip()[:500],
            "created_at": now_iso(),
        }
        await self.db.game_messages.insert_one(doc)

        # Broadcast to all room subscribers
        await ws_manager.broadcast_room(room_id, {
            "type": "PUBLIC_MESSAGE",
            "message": {
                "id": doc["id"],
                "sender_user_id": user_id,
                "sender_display_name": sender_name,
                "message": doc["message"],
                "round_number": doc["round_number"],
                "created_at": doc["created_at"],
            },
        })
        return True, "تم الإرسال"

    async def list_public_messages(self, room_id: str, user_id: str) -> Tuple[bool, List[dict]]:
        session = await self._get_session(room_id)
        if not session:
            return False, []
        # Must be a member (player or host)
        role = self._get_role(session, user_id)
        is_host = user_id == session["host_id"]
        if not role and not is_host:
            return False, []
        msgs = await self.db.game_messages.find(
            {"room_id": room_id, "channel_type": "PUBLIC"},
            {"_id": 0},
        ).sort("created_at", 1).to_list(1000)
        return True, [
            {
                "id": m["id"],
                "sender_user_id": m["sender_user_id"],
                "sender_display_name": m["sender_display_name"],
                "message": m["message"],
                "round_number": m["round_number"],
                "created_at": m["created_at"],
            }
            for m in msgs
        ]

    # ---------- Mafia Target Voting ----------
    async def submit_mafia_target_vote(self, room_id: str, user_id: str, target_id: str) -> Tuple[bool, str]:
        session = await self._get_session(room_id)
        if not session:
            return False, "الجلسة غير موجودة"
        if session["current_phase"] not in ("MAFIA_DISCUSSION", "NIGHT_ACTIONS"):
            return False, "ليس وقت اختيار الضحية"
        role = self._get_role(session, user_id)
        if role != "MAFIA":
            return False, "حركة غير مسموحة لدورك"
        if not self._is_alive(session, user_id):
            return False, "أنت خارج اللعبة"
        target_role = self._get_role(session, target_id)
        if not self._is_alive(session, target_id):
            return False, "الهدف غير حي"
        if target_role == "MAFIA":
            return False, "لا يمكن استهداف زميل Mafia"

        # Upsert kill vote
        await self.db.mafia_actions.update_one(
            {
                "session_id": session["id"],
                "round_number": session["round_number"],
                "actor_id": user_id,
                "action_type": "KILL",
            },
            {"$set": {
                "target_id": target_id,
                "room_id": room_id,
                "result": None,
                "created_at": now_iso(),
            }, "$setOnInsert": {
                "id": f"act_{session['id']}_{session['round_number']}_{user_id}_KILL",
            }},
            upsert=True,
        )

        # Broadcast to mafia only that a teammate updated their vote (without revealing the target to non-voter)
        # We do reveal within the mafia team (they're a team, needs coordination)
        await ws_manager.broadcast_mafia(room_id, {
            "type": "MAFIA_TARGET_VOTE",
            "voter_id": user_id,
            "target_id": target_id,
            "round_number": session["round_number"],
        })
        return True, "تم تسجيل اختيارك"

    async def get_mafia_private_state(self, room_id: str, user_id: str) -> Optional[dict]:
        session = await self._get_session(room_id)
        if not session:
            return None
        role = self._get_role(session, user_id)
        alive = self._is_alive(session, user_id)
        is_host_viewer = user_id == session["host_id"] and session["settings"].get("host_can_view_mafia_chat")
        if not ((role == "MAFIA" and alive) or is_host_viewer):
            return None

        teammates = [
            {"user_id": p["user_id"], "display_name": p["display_name"], "alive": p["alive"]}
            for p in session["players"] if p["role"] == "MAFIA"
        ]
        available_targets = [
            {"user_id": p["user_id"], "display_name": p["display_name"]}
            for p in session["players"] if p["alive"] and p["role"] != "MAFIA"
        ]
        # current votes
        votes = await self.db.mafia_actions.find({
            "session_id": session["id"],
            "round_number": session["round_number"],
            "action_type": "KILL",
        }, {"_id": 0}).to_list(100)
        # my vote
        my_vote = next((v for v in votes if v["actor_id"] == user_id), None)

        # only send messages when in MAFIA_DISCUSSION or NIGHT_ACTIONS
        msgs = []
        if session["current_phase"] in ("MAFIA_DISCUSSION", "NIGHT_ACTIONS", "NIGHT_RESULT"):
            msgs_docs = await self.db.game_messages.find(
                {"room_id": room_id, "channel_type": "MAFIA"},
                {"_id": 0},
            ).sort("created_at", 1).to_list(500)
            msgs = [{
                "id": m["id"],
                "sender_user_id": m["sender_user_id"],
                "sender_display_name": m["sender_display_name"],
                "message": m["message"],
                "round_number": m["round_number"],
                "created_at": m["created_at"],
            } for m in msgs_docs]

        return {
            "teammates": teammates,
            "available_targets": available_targets,
            "my_target_vote": my_vote["target_id"] if my_vote else None,
            "current_votes": [
                {"voter_id": v["actor_id"], "target_id": v["target_id"]}
                for v in votes
            ],
            "messages": msgs,
            "phase_ends_at": session.get("phase_ends_at"),
            "current_phase": session.get("current_phase"),
            "is_viewer": is_host_viewer,  # host observer mode
        }

    # ---------- Night Actions (Doctor/Detective) ----------
    async def submit_night_action(self, room_id: str, user_id: str, action_type: str, target_id: str) -> Tuple[bool, str]:
        session = await self._get_session(room_id)
        if not session:
            return False, "الجلسة غير موجودة"
        # Mafia KILL is now handled via submit_mafia_target_vote and allowed in both phases
        if action_type == "KILL":
            return await self.submit_mafia_target_vote(room_id, user_id, target_id)

        if session["current_phase"] != "NIGHT_ACTIONS":
            return False, "ليس وقت الحركة الليلية"

        role = self._get_role(session, user_id)
        if not role:
            return False, "لست في اللعبة"
        if not self._is_alive(session, user_id):
            return False, "أنت خارج اللعبة"

        allowed = {"DOCTOR": "PROTECT", "DETECTIVE": "INVESTIGATE"}
        if allowed.get(role) != action_type:
            return False, "حركة غير مسموحة لدورك"

        if not self._is_alive(session, target_id):
            return False, "الهدف غير حي"

        existing = await self.db.mafia_actions.find_one({
            "session_id": session["id"],
            "round_number": session["round_number"],
            "actor_id": user_id,
            "action_type": action_type,
        })
        if existing:
            return False, "لقد قمت بحركتك بالفعل"

        result = None
        if action_type == "INVESTIGATE":
            target_role = self._get_role(session, target_id)
            result = "MAFIA" if target_role == "MAFIA" else "NOT_MAFIA"

        await self.db.mafia_actions.insert_one({
            "id": f"act_{session['id']}_{session['round_number']}_{user_id}_{action_type}",
            "session_id": session["id"],
            "room_id": room_id,
            "round_number": session["round_number"],
            "actor_id": user_id,
            "action_type": action_type,
            "target_id": target_id,
            "result": result,
            "created_at": now_iso(),
        })

        if action_type == "INVESTIGATE":
            target = next((p for p in session["players"] if p["user_id"] == target_id), None)
            await ws_manager.send_to_user(user_id, {
                "type": "INVESTIGATION_RESULT",
                "target_id": target_id,
                "target_name": target["display_name"] if target else "",
                "result": result,
                "round_number": session["round_number"],
            })
        else:
            await ws_manager.send_to_user(user_id, {
                "type": "NIGHT_ACTION_CONFIRMED",
                "action_type": action_type,
                "target_id": target_id,
            })
        return True, "تم تسجيل حركتك"

    async def _resolve_night(self, room_id: str):
        session = await self._get_session(room_id)
        if not session:
            return
        round_num = session["round_number"]
        actions = await self.db.mafia_actions.find({
            "session_id": session["id"],
            "round_number": round_num,
        }, {"_id": 0}).to_list(1000)

        kills = [a for a in actions if a["action_type"] == "KILL"]
        protects = [a["target_id"] for a in actions if a["action_type"] == "PROTECT"]

        target_id = None
        if kills:
            counter = Counter([a["target_id"] for a in kills])
            top = counter.most_common()
            if len(top) == 1 or top[0][1] > top[1][1]:
                target_id = top[0][0]

        eliminated_user = None
        if target_id and target_id not in protects:
            for p in session["players"]:
                if p["user_id"] == target_id:
                    p["alive"] = False
                    p["eliminated_at"] = now_iso()
                    eliminated_user = p
                    break
            await self.db.game_sessions.update_one(
                {"room_id": room_id}, {"$set": {"players": session["players"]}}
            )
            # refresh mafia channel if a mafia was eliminated
            self._refresh_mafia_channel(room_id, session)

        reveal = session.get("reveal_eliminated_role", False)
        await ws_manager.broadcast_room(room_id, {
            "type": "NIGHT_RESULT",
            "round_number": round_num,
            "eliminated": None if not eliminated_user else {
                "user_id": eliminated_user["user_id"],
                "display_name": eliminated_user["display_name"],
                "role": eliminated_user["role"] if reveal else None,
            },
            "players": await self._public_players(room_id),
        })
        await self._start_phase(room_id, "NIGHT_RESULT")

    # ---------- Voting ----------
    async def submit_vote(self, room_id: str, user_id: str, target_id: str) -> Tuple[bool, str]:
        session = await self._get_session(room_id)
        if not session:
            return False, "الجلسة غير موجودة"
        if session["current_phase"] != "VOTING":
            return False, "ليس وقت التصويت"
        if not self._is_alive(session, user_id):
            return False, "أنت خارج اللعبة"
        if not self._is_alive(session, target_id):
            return False, "الهدف خارج اللعبة"

        existing = await self.db.votes.find_one({
            "session_id": session["id"],
            "round_number": session["round_number"],
            "voter_id": user_id,
        })
        if existing:
            return False, "لقد صوّت بالفعل"

        await self.db.votes.insert_one({
            "id": f"vote_{session['id']}_{session['round_number']}_{user_id}",
            "session_id": session["id"],
            "room_id": room_id,
            "round_number": session["round_number"],
            "voter_id": user_id,
            "target_id": target_id,
            "created_at": now_iso(),
        })

        await ws_manager.broadcast_room(room_id, {"type": "VOTE_SUBMITTED", "voter_id": user_id})
        return True, "تم التصويت"

    async def _resolve_voting(self, room_id: str):
        session = await self._get_session(room_id)
        if not session:
            return
        votes = await self.db.votes.find({
            "session_id": session["id"],
            "round_number": session["round_number"],
        }, {"_id": 0}).to_list(1000)

        counts = Counter([v["target_id"] for v in votes])
        eliminated_user = None
        vote_results = [
            {"user_id": p["user_id"], "display_name": p["display_name"], "votes": counts.get(p["user_id"], 0)}
            for p in session["players"] if p["alive"]
        ]

        if counts:
            top = counts.most_common()
            if len(top) == 1 or top[0][1] > top[1][1]:
                target_id = top[0][0]
                for p in session["players"]:
                    if p["user_id"] == target_id:
                        p["alive"] = False
                        p["eliminated_at"] = now_iso()
                        eliminated_user = p
                        break
                await self.db.game_sessions.update_one(
                    {"room_id": room_id}, {"$set": {"players": session["players"]}}
                )
                self._refresh_mafia_channel(room_id, session)

        reveal = session.get("reveal_eliminated_role", False)
        await ws_manager.broadcast_room(room_id, {
            "type": "VOTE_RESULT",
            "round_number": session["round_number"],
            "vote_counts": vote_results,
            "eliminated": None if not eliminated_user else {
                "user_id": eliminated_user["user_id"],
                "display_name": eliminated_user["display_name"],
                "role": eliminated_user["role"] if reveal else None,
            },
            "players": await self._public_players(room_id),
        })
        await self._start_phase(room_id, "VOTE_RESULT")

    # ---------- Win Condition ----------
    async def _check_win(self, room_id: str) -> bool:
        session = await self._get_session(room_id)
        if not session:
            return True
        alive_mafia = sum(1 for p in session["players"] if p["alive"] and p["role"] == "MAFIA")
        alive_non_mafia = sum(1 for p in session["players"] if p["alive"] and p["role"] != "MAFIA")

        winner = None
        if alive_mafia == 0:
            winner = "CITIZENS"
        elif alive_mafia >= alive_non_mafia:
            winner = "MAFIA"

        if winner:
            await self.db.game_sessions.update_one(
                {"room_id": room_id},
                {"$set": {"current_phase": "GAME_OVER", "winner": winner, "ended_at": now_iso()}},
            )
            await self.db.rooms.update_one(
                {"id": room_id}, {"$set": {"status": "FINISHED", "ended_at": now_iso()}}
            )
            final_players = [
                {"user_id": p["user_id"], "display_name": p["display_name"],
                 "role": p["role"], "alive": p["alive"]}
                for p in session["players"]
            ]
            await ws_manager.broadcast_room(room_id, {
                "type": "GAME_OVER",
                "winner": winner,
                "players": final_players,
                "round_number": session["round_number"],
            })
            # clear mafia channel
            ws_manager.set_mafia_members(room_id, set())
            return True
        return False


_engine: Optional[MafiaEngine] = None


def init_engine(db) -> MafiaEngine:
    global _engine
    _engine = MafiaEngine(db)
    return _engine


def get_engine() -> MafiaEngine:
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    return _engine
