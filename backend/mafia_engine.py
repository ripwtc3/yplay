"""
MafiaGameEngine: server-authoritative game state machine.
Phases: LOBBY -> ROLE_ASSIGNMENT -> NIGHT -> NIGHT_RESULT -> DISCUSSION -> VOTING -> VOTE_RESULT -> CHECK_WIN -> (NIGHT | GAME_OVER)
Roles: MAFIA, CITIZEN, DOCTOR, DETECTIVE
"""
import asyncio
import random
import string
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import Counter

from ws_manager import ws_manager
from models import now_iso

logger = logging.getLogger(__name__)


ROLES = ["MAFIA", "CITIZEN", "DOCTOR", "DETECTIVE"]


def generate_room_code(length: int = 6) -> str:
    # Avoid ambiguous chars 0/O, 1/I/L
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(random.choices(alphabet, k=length))


class MafiaEngine:
    """Runs mafia game logic for a single room. Kept per-room in memory + persisted to Mongo."""

    def __init__(self, db):
        self.db = db
        self._tasks: Dict[str, asyncio.Task] = {}  # room_id -> phase task

    # ---------- helpers ----------
    async def _get_session(self, room_id: str):
        return await self.db.game_sessions.find_one({"room_id": room_id}, {"_id": 0})

    async def _get_room(self, room_id: str):
        return await self.db.rooms.find_one({"id": room_id}, {"_id": 0})

    async def _public_players(self, room_id: str) -> List[dict]:
        session = await self._get_session(room_id)
        if not session:
            return []
        result = []
        for p in session.get("players", []):
            result.append({
                "user_id": p["user_id"],
                "display_name": p["display_name"],
                "username": p["username"],
                "alive": p["alive"],
                "connection_status": "ONLINE" if ws_manager.is_online(p["user_id"]) else "OFFLINE",
                "is_host": p["user_id"] == session.get("host_id"),
                "eliminated_at": p.get("eliminated_at"),
            })
        return result

    async def _get_role(self, session: dict, user_id: str) -> Optional[str]:
        for p in session.get("players", []):
            if p["user_id"] == user_id:
                return p.get("role")
        return None

    async def _is_alive(self, session: dict, user_id: str) -> bool:
        for p in session.get("players", []):
            if p["user_id"] == user_id:
                return p.get("alive", False)
        return False

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

        # Assign roles
        shuffled = players.copy()
        random.shuffle(shuffled)
        assigned = []
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
            "history": [],
        }
        await self.db.game_sessions.insert_one(session)
        await self.db.rooms.update_one(
            {"id": room_id},
            {"$set": {"status": "ACTIVE", "started_at": now_iso()}},
        )

        # Broadcast game started + private roles
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

        # Show role for a few seconds, then start night
        await asyncio.sleep(5)
        await self._start_phase(room_id, "NIGHT")
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
            "NIGHT": settings["night_seconds"],
            "DISCUSSION": settings["discussion_seconds"],
            "VOTING": settings["voting_seconds"],
            "NIGHT_RESULT": 5,
            "VOTE_RESULT": 5,
        }
        duration = duration_map.get(phase, 5)

        round_number = session["round_number"]
        if phase == "NIGHT":
            round_number += 1

        now = datetime.now(timezone.utc)
        ends_at = (now.timestamp() + duration)

        await self.db.game_sessions.update_one(
            {"room_id": room_id},
            {"$set": {
                "current_phase": phase,
                "round_number": round_number,
                "phase_started_at": now.isoformat(),
                "phase_ends_at": datetime.fromtimestamp(ends_at, tz=timezone.utc).isoformat(),
            }},
        )

        await ws_manager.broadcast_room(room_id, {
            "type": "PHASE_STARTED",
            "phase": phase,
            "round_number": round_number,
            "duration_seconds": duration,
            "phase_ends_at_ts": ends_at,
            "players": await self._public_players(room_id),
        })

        # schedule phase end
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
        if phase == "NIGHT":
            await self._resolve_night(room_id)
        elif phase == "NIGHT_RESULT":
            # check win, then discussion
            if not await self._check_win(room_id):
                await self._start_phase(room_id, "DISCUSSION")
        elif phase == "DISCUSSION":
            await self._start_phase(room_id, "VOTING")
        elif phase == "VOTING":
            await self._resolve_voting(room_id)
        elif phase == "VOTE_RESULT":
            if not await self._check_win(room_id):
                await self._start_phase(room_id, "NIGHT")

    # ---------- Night Actions ----------
    async def submit_night_action(self, room_id: str, user_id: str, action_type: str, target_id: str) -> Tuple[bool, str]:
        session = await self._get_session(room_id)
        if not session:
            return False, "الجلسة غير موجودة"
        if session["current_phase"] != "NIGHT":
            return False, "ليس وقت الحركة الليلية"

        role = await self._get_role(session, user_id)
        if not role:
            return False, "لست في اللعبة"
        if not await self._is_alive(session, user_id):
            return False, "أنت خارج اللعبة"

        allowed = {
            "MAFIA": "KILL",
            "DOCTOR": "PROTECT",
            "DETECTIVE": "INVESTIGATE",
        }
        if allowed.get(role) != action_type:
            return False, "حركة غير مسموحة لدورك"

        if not await self._is_alive(session, target_id):
            return False, "الهدف غير حي"

        # prevent duplicate action same round
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
            target_role = await self._get_role(session, target_id)
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

        # Send private result for Detective
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

        # Determine mafia target: majority vote among mafia actions
        kills = [a for a in actions if a["action_type"] == "KILL"]
        protects = [a["target_id"] for a in actions if a["action_type"] == "PROTECT"]

        target_id = None
        if kills:
            counter = Counter([a["target_id"] for a in kills])
            top = counter.most_common()
            if len(top) == 1 or top[0][1] > top[1][1]:
                target_id = top[0][0]
            # tie -> no kill (deterministic rule)

        eliminated_user = None
        if target_id and target_id not in protects:
            # Eliminate
            for p in session["players"]:
                if p["user_id"] == target_id:
                    p["alive"] = False
                    p["eliminated_at"] = now_iso()
                    eliminated_user = p
                    break
            await self.db.game_sessions.update_one(
                {"room_id": room_id}, {"$set": {"players": session["players"]}}
            )

        reveal = session.get("reveal_eliminated_role", False)
        payload = {
            "type": "NIGHT_RESULT",
            "round_number": round_num,
            "eliminated": None if not eliminated_user else {
                "user_id": eliminated_user["user_id"],
                "display_name": eliminated_user["display_name"],
                "role": eliminated_user["role"] if reveal else None,
            },
            "players": await self._public_players(room_id),
        }
        await ws_manager.broadcast_room(room_id, payload)
        await self._start_phase(room_id, "NIGHT_RESULT")

    # ---------- Voting ----------
    async def submit_vote(self, room_id: str, user_id: str, target_id: str) -> Tuple[bool, str]:
        session = await self._get_session(room_id)
        if not session:
            return False, "الجلسة غير موجودة"
        if session["current_phase"] != "VOTING":
            return False, "ليس وقت التصويت"
        if not await self._is_alive(session, user_id):
            return False, "أنت خارج اللعبة"
        if not await self._is_alive(session, target_id):
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

        await ws_manager.broadcast_room(room_id, {
            "type": "VOTE_SUBMITTED",
            "voter_id": user_id,
        })
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
        vote_results = []
        for p in session["players"]:
            if p["alive"]:
                vote_results.append({
                    "user_id": p["user_id"],
                    "display_name": p["display_name"],
                    "votes": counts.get(p["user_id"], 0),
                })

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
                {"$set": {
                    "current_phase": "GAME_OVER",
                    "winner": winner,
                    "ended_at": now_iso(),
                }},
            )
            await self.db.rooms.update_one(
                {"id": room_id}, {"$set": {"status": "FINISHED", "ended_at": now_iso()}}
            )
            # reveal all roles
            final_players = [
                {
                    "user_id": p["user_id"],
                    "display_name": p["display_name"],
                    "role": p["role"],
                    "alive": p["alive"],
                }
                for p in session["players"]
            ]
            await ws_manager.broadcast_room(room_id, {
                "type": "GAME_OVER",
                "winner": winner,
                "players": final_players,
                "round_number": session["round_number"],
            })
            return True
        return False


# Singleton engine (bound to db later in server.py)
_engine: Optional[MafiaEngine] = None


def init_engine(db) -> MafiaEngine:
    global _engine
    _engine = MafiaEngine(db)
    return _engine


def get_engine() -> MafiaEngine:
    if _engine is None:
        raise RuntimeError("Engine not initialized")
    return _engine
