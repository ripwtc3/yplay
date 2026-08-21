"""Iteration 3 regression: newly added GET /api/users/me/stats, secrets-based room code
alphabet + role distribution, whisper 1-to-1 delivery, public chat + reactions,
and auth/WS sanity after the `database.py` extraction refactor.
"""
import asyncio
import json
import re
import time

import pytest
import requests
import websockets

from conftest import (
    API, WS_URL, register_user, create_room, join_room, get_state,
    wait_for_phase, roles_map,
)

SAFE_ALPHABET = set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
AMBIGUOUS = set("01ILO")

LOBBY_SETTINGS = {
    "max_players": 6,
    "mafia_count": 2,
    "doctor_count": 1,
    "detective_count": 1,
    "mafia_discussion_seconds": 180,
    "night_actions_seconds": 180,
    "discussion_seconds": 60,
    "voting_seconds": 60,
    "reveal_eliminated_role": True,
    "host_can_view_mafia_chat": False,
}


# ---------------- module: auth + database.py refactor sanity ----------------
class TestAuthAfterDbRefactor:
    def test_register_login_me_and_ws(self, make_user):
        u = make_user("dbref")
        assert isinstance(u["token"], str) and len(u["token"]) > 20

        # login with the same credentials
        r = requests.post(f"{API}/auth/login",
                          json={"email": u["email"], "password": "secret123"}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert data["user"]["id"] == u["user"]["id"]
        assert '"_id"' not in json.dumps(data)

        # /auth/me with the freshly issued token
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {data['token']}"})
        me = s.get(f"{API}/auth/me", timeout=30)
        assert me.status_code == 200, me.text[:300]
        assert me.json()["email"] == u["email"].lower()

        # WebSocket auth (auth.py uses `from database import db` lazily)
        async def run():
            async with websockets.connect(f"{WS_URL}?token={u['token']}") as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                return json.loads(raw)

        first = asyncio.run(run())
        assert first.get("type") == "CONNECTED", first


# ---------------- module: secrets-based room code + role distribution ----------------
class TestSecretsRandomness:
    def test_room_codes_use_safe_alphabet(self, make_user, tracker):
        host = make_user("codes")
        codes = []
        for _ in range(12):
            room = create_room(host, LOBBY_SETTINGS)
            tracker["rooms"].append(room["id"])
            codes.append(room["room_code"])
        for c in codes:
            assert len(c) == 6, f"bad length: {c}"
            assert re.fullmatch(r"[A-Z2-9]{6}", c), f"unexpected chars in {c}"
            assert not (set(c) & AMBIGUOUS), f"ambiguous chars in {c}"
            assert set(c) <= SAFE_ALPHABET, f"outside safe alphabet: {c}"
        assert len(set(codes)) == len(codes), f"duplicate codes generated: {codes}"
        # spread check: 12 codes * 6 chars should not all be the same character
        assert len({ch for c in codes for ch in c}) > 5, "suspiciously low entropy"

    def test_role_distribution_6_players(self, make_user, tracker):
        host = make_user("rd6")
        others = [make_user(f"rd6_{i}") for i in range(1, 6)]
        room = create_room(host, LOBBY_SETTINGS)
        tracker["rooms"].append(room["id"])
        for u in others:
            join_room(u, room["room_code"])
        users = [host] + others
        r = host["s"].post(f"{API}/rooms/{room['id']}/start", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert wait_for_phase(host, room["id"], "MAFIA_DISCUSSION", timeout=40) is not None
        rm = roles_map(host, room["id"], users)
        counts = {k: len(v) for k, v in rm.items()}
        assert counts.get("MAFIA") == 2, counts
        assert counts.get("DOCTOR") == 1, counts
        assert counts.get("DETECTIVE") == 1, counts
        assert counts.get("CITIZEN") == 2, counts
        assert sum(counts.values()) == 6, counts


# ---------------- module: GET /api/users/me/stats (fresh user) ----------------
class TestFreshUserStats:
    def test_fresh_user_zero_stats(self, make_user):
        u = make_user("stats0")
        r = u["s"].get(f"{API}/users/me/stats", timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["total_games"] == 0, d
        assert d["wins"] == 0 and d["losses"] == 0
        assert d["win_rate"] == 0.0
        assert isinstance(d.get("role_stats"), dict)
        for role in ("MAFIA", "CITIZEN", "DOCTOR", "DETECTIVE"):
            assert d["role_stats"][role]["played"] == 0, d["role_stats"]
        assert d.get("recent") == []
        assert '"_id"' not in json.dumps(d)

    def test_stats_requires_auth(self):
        r = requests.get(f"{API}/users/me/stats", timeout=30)
        assert r.status_code in (401, 403), r.status_code


# ---------------- module: full game -> whisper/public chat -> stats ----------------
GAME_SETTINGS = {
    "max_players": 4,
    "mafia_count": 1,
    "doctor_count": 1,
    "detective_count": 1,
    "mafia_discussion_seconds": 10,
    "night_actions_seconds": 25,
    "discussion_seconds": 30,
    "voting_seconds": 25,
    "reveal_eliminated_role": True,
    "host_can_view_mafia_chat": False,
}


@pytest.fixture(scope="class")
def game(make_user, tracker):
    host = make_user("sthost")
    others = [make_user(f"st{i}") for i in range(1, 4)]
    room = create_room(host, GAME_SETTINGS)
    tracker["rooms"].append(room["id"])
    for u in others:
        join_room(u, room["room_code"])
    users = [host] + others
    r = host["s"].post(f"{API}/rooms/{room['id']}/start", timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert wait_for_phase(host, room["id"], "MAFIA_DISCUSSION", timeout=40, interval=1.0) is not None
    return {"room": room, "host": host, "users": users,
            "roles": roles_map(host, room["id"], users)}


async def _collect(ws, seconds=4.0):
    out = []
    loop = asyncio.get_event_loop()
    end = loop.time() + seconds
    while loop.time() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, end - loop.time()))
            out.append(json.loads(raw))
        except (asyncio.TimeoutError, Exception):
            break
    return out


async def _open(user, room_id):
    ws = await websockets.connect(f"{WS_URL}?token={user['token']}")
    await asyncio.wait_for(ws.recv(), timeout=10)  # CONNECTED
    await ws.send(json.dumps({"type": "SUBSCRIBE_ROOM", "room_id": room_id}))
    await asyncio.sleep(0.6)
    try:
        while True:
            await asyncio.wait_for(ws.recv(), timeout=0.3)
    except Exception:
        pass
    return ws


class TestChatWhisperAndStatsAfterGame:
    def test_whisper_public_chat_and_stats(self, game):
        rid = game["room"]["id"]
        mafia = game["roles"]["MAFIA"][0]
        doctor = game["roles"]["DOCTOR"][0]
        detective = game["roles"]["DETECTIVE"][0]
        citizen = game["roles"]["CITIZEN"][0]

        # mafia targets the citizen so 3 stay alive for chat tests
        r = mafia["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                            json={"target_user_id": citizen["user"]["id"]}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert wait_for_phase(mafia, rid, "NIGHT_ACTIONS", timeout=40, interval=1.0) is not None
        r = doctor["s"].post(f"{API}/rooms/{rid}/night-action",
                             json={"action_type": "PROTECT", "target_user_id": doctor["user"]["id"]}, timeout=30)
        assert r.status_code == 200, r.text[:200]

        # whisper is day-only
        r = mafia["s"].post(f"{API}/rooms/{rid}/whisper",
                            json={"target_user_id": doctor["user"]["id"], "message": "TEST_night_whisper"}, timeout=30)
        assert r.status_code == 403, f"whisper allowed at night: {r.status_code}"

        st = wait_for_phase(mafia, rid, ["NIGHT_RESULT", "DISCUSSION"], timeout=60, interval=1.0)
        assert st is not None, "never reached day"
        players = {p["user_id"]: p for p in st["session"]["players"]}
        assert players[citizen["user"]["id"]]["alive"] is False

        # ---------- whisper + public chat + reaction with WS listeners ----------
        async def chat_flow():
            ws_m = await _open(mafia, rid)
            ws_d = await _open(doctor, rid)
            ws_det = await _open(detective, rid)
            try:
                # whisper mafia -> doctor
                r = await asyncio.to_thread(
                    mafia["s"].post, f"{API}/rooms/{rid}/whisper",
                    json={"target_user_id": doctor["user"]["id"], "message": "TEST_secret_whisper"}, timeout=30)
                assert r.status_code == 200, r.text[:200]
                got_m, got_d, got_det = await asyncio.gather(
                    _collect(ws_m, 3.5), _collect(ws_d, 3.5), _collect(ws_det, 3.5))
                w_m = [e for e in got_m if e.get("type") == "WHISPER_MESSAGE"]
                w_d = [e for e in got_d if e.get("type") == "WHISPER_MESSAGE"]
                w_det = [e for e in got_det if e.get("type") == "WHISPER_MESSAGE"]
                assert w_m, "sender did not receive WHISPER_MESSAGE"
                assert w_d, "target did not receive WHISPER_MESSAGE"
                assert not w_det, f"whisper leaked to third party: {w_det}"

                # public message broadcast
                r = await asyncio.to_thread(
                    detective["s"].post, f"{API}/rooms/{rid}/message",
                    json={"message": "TEST_public_hello"}, timeout=30)
                assert r.status_code == 200, r.text[:200]
                got_m, got_d = await asyncio.gather(_collect(ws_m, 3.0), _collect(ws_d, 3.0))
                assert any(e.get("type") == "PUBLIC_MESSAGE" for e in got_m), got_m
                assert any(e.get("type") == "PUBLIC_MESSAGE" for e in got_d), got_d

                # typing relay
                await ws_m.send(json.dumps({"type": "TYPING_START", "room_id": rid, "channel": "PUBLIC"}))
                got_d = await _collect(ws_d, 3.0)
                assert any("TYPING" in str(e.get("type", "")) for e in got_d), got_d
            finally:
                for w in (ws_m, ws_d, ws_det):
                    await w.close()

        asyncio.run(chat_flow())

        # whisper listing scoped to caller
        r = doctor["s"].get(f"{API}/rooms/{rid}/whispers", timeout=30)
        assert r.status_code == 200, r.text[:200]
        ws_list = r.json()["whispers"]
        assert any(w["message"] == "TEST_secret_whisper" for w in ws_list), ws_list
        r = detective["s"].get(f"{API}/rooms/{rid}/whispers", timeout=30)
        assert r.status_code == 200
        assert r.json()["whispers"] == [], "third party sees whispers they are not part of"

        # public messages list + reaction toggle
        r = doctor["s"].get(f"{API}/rooms/{rid}/messages", timeout=30)
        assert r.status_code == 200, r.text[:200]
        msgs = r.json()["messages"]
        target = next((m for m in msgs if m["message"] == "TEST_public_hello"), None)
        assert target is not None, msgs
        r = doctor["s"].post(f"{API}/rooms/{rid}/messages/{target['id']}/react",
                             json={"emoji": "👍"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert "👍" in json.dumps(r.json()["reactions"], ensure_ascii=False), r.json()
        r = doctor["s"].post(f"{API}/rooms/{rid}/messages/{target['id']}/react",
                             json={"emoji": "👍"}, timeout=30)
        assert r.status_code == 200
        reacts = r.json()["reactions"]
        assert not reacts.get("👍"), f"toggle-off failed: {reacts}"

        # ---------- lynch the mafia -> GAME_OVER ----------
        assert wait_for_phase(mafia, rid, "VOTING", timeout=70, interval=1.0) is not None
        for u in (doctor, detective):
            r = u["s"].post(f"{API}/rooms/{rid}/vote",
                            json={"target_user_id": mafia["user"]["id"]}, timeout=30)
            assert r.status_code == 200, r.text[:200]
        st = wait_for_phase(mafia, rid, "GAME_OVER", timeout=90, interval=1.5)
        assert st is not None, "never reached GAME_OVER"
        assert st["session"]["winner"] == "CITIZENS", st["session"]["winner"]

        time.sleep(1.5)

        # ---------- stats after one finished game ----------
        for u, role, won in ((mafia, "MAFIA", False), (doctor, "DOCTOR", True),
                             (detective, "DETECTIVE", True), (citizen, "CITIZEN", True)):
            r = u["s"].get(f"{API}/users/me/stats", timeout=30)
            assert r.status_code == 200, r.text[:300]
            d = r.json()
            assert d["total_games"] == 1, f"{role}: {d}"
            assert d["wins"] == (1 if won else 0), f"{role}: {d}"
            assert d["losses"] == (0 if won else 1), f"{role}: {d}"
            assert d["role_stats"][role]["played"] == 1, f"{role}: {d['role_stats']}"
            assert d["role_stats"][role]["won"] == (1 if won else 0), f"{role}: {d['role_stats']}"
            assert len(d["recent"]) == 1, d["recent"]
            rec = d["recent"][0]
            assert rec["room_id"] == rid
            assert rec["role"] == role
            assert rec["won"] is won
            assert rec["ended_at"], rec
            assert '"_id"' not in json.dumps(d)
