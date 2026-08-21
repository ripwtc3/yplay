"""WebSocket private-channel isolation: MAFIA_MESSAGE / MAFIA_TARGET_VOTE must reach
only the mafia sub-channel, never citizens/doctor/detective sockets.
"""
import asyncio
import json

import pytest
import websockets

from conftest import API, WS_URL, create_room, join_room, wait_for_phase, roles_map


SETTINGS = {
    "max_players": 4,
    "mafia_count": 1,
    "doctor_count": 1,
    "detective_count": 1,
    "mafia_discussion_seconds": 180,
    "night_actions_seconds": 180,
    "discussion_seconds": 30,
    "voting_seconds": 20,
    "reveal_eliminated_role": False,
    "host_can_view_mafia_chat": False,
}


@pytest.fixture(scope="class")
def ws_game(make_user, tracker):
    host = make_user("wsh")
    others = [make_user(f"ws{i}") for i in range(1, 4)]
    room = create_room(host, SETTINGS)
    tracker["rooms"].append(room["id"])
    for u in others:
        join_room(u, room["room_code"])
    users = [host] + others
    r = host["s"].post(f"{API}/rooms/{room['id']}/start", timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert wait_for_phase(host, room["id"], "MAFIA_DISCUSSION", timeout=40) is not None
    return {"room": room, "host": host, "users": users, "roles": roles_map(host, room["id"], users)}


async def _drain(ws, seconds=3.0):
    """Collect all messages arriving within `seconds`."""
    out = []
    loop = asyncio.get_event_loop()
    end = loop.time() + seconds
    while loop.time() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, end - loop.time()))
            out.append(json.loads(raw))
        except asyncio.TimeoutError:
            break
        except Exception:
            break
    return out


class TestWebSocketMafiaPrivacy:
    def test_invalid_token_rejected(self):
        async def run():
            try:
                async with websockets.connect(f"{WS_URL}?token=bogus") as ws:
                    await ws.recv()
                return "opened"
            except Exception as e:
                return f"closed:{e}"
        res = asyncio.run(run())
        assert res.startswith("closed"), res

    def test_mafia_events_only_reach_mafia_sockets(self, ws_game):
        rid = ws_game["room"]["id"]
        mafia = ws_game["roles"]["MAFIA"][0]
        non_mafia = [u for u in ws_game["users"] if u["user"]["id"] != mafia["user"]["id"]]
        target = non_mafia[0]

        async def run():
            conns = {}
            try:
                for u in ws_game["users"]:
                    ws = await websockets.connect(f"{WS_URL}?token={u['token']}")
                    hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    assert hello["type"] == "CONNECTED", hello
                    await ws.send(json.dumps({"type": "SUBSCRIBE_ROOM", "room_id": rid}))
                    conns[u["user"]["id"]] = ws
                await asyncio.sleep(1.5)
                # flush subscribe/PLAYER_ONLINE noise
                for ws in conns.values():
                    await _drain(ws, 1.0)

                # mafia posts a private message + target vote over HTTP
                loop = asyncio.get_event_loop()
                r1 = await loop.run_in_executor(None, lambda: mafia["s"].post(
                    f"{API}/rooms/{rid}/mafia-message", json={"message": "TEST_ws_secret"}, timeout=30))
                assert r1.status_code == 200, r1.text[:200]
                r2 = await loop.run_in_executor(None, lambda: mafia["s"].post(
                    f"{API}/rooms/{rid}/mafia-target-vote",
                    json={"target_user_id": target["user"]["id"]}, timeout=30))
                assert r2.status_code == 200, r2.text[:200]

                collected = {}
                for uid, ws in conns.items():
                    collected[uid] = await _drain(ws, 3.0)
                return collected
            finally:
                for ws in conns.values():
                    try:
                        await ws.close()
                    except Exception:
                        pass

        collected = asyncio.run(run())
        mid = mafia["user"]["id"]
        mafia_types = [m["type"] for m in collected[mid]]
        assert "MAFIA_MESSAGE" in mafia_types, f"mafia socket missed MAFIA_MESSAGE: {mafia_types}"
        assert "MAFIA_TARGET_VOTE" in mafia_types, f"mafia socket missed MAFIA_TARGET_VOTE: {mafia_types}"
        secret_seen = [m for m in collected[mid]
                       if m["type"] == "MAFIA_MESSAGE" and m["message"]["message"] == "TEST_ws_secret"]
        assert secret_seen, "mafia did not receive the message payload"

        for u in non_mafia:
            uid = u["user"]["id"]
            types = [m["type"] for m in collected[uid]]
            assert "MAFIA_MESSAGE" not in types, f"LEAK: {uid} got MAFIA_MESSAGE ({types})"
            assert "MAFIA_TARGET_VOTE" not in types, f"LEAK: {uid} got MAFIA_TARGET_VOTE ({types})"
            assert "TEST_ws_secret" not in json.dumps(collected[uid]), f"LEAK: secret text on {uid} socket"

    def test_non_member_cannot_subscribe_to_room(self, ws_game, make_user):
        rid = ws_game["room"]["id"]
        outsider = make_user("wsout")

        async def run():
            async with websockets.connect(f"{WS_URL}?token={outsider['token']}") as ws:
                hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                assert hello["type"] == "CONNECTED"
                await ws.send(json.dumps({"type": "SUBSCRIBE_ROOM", "room_id": rid}))
                msgs = await _drain(ws, 3.0)
                return msgs

        msgs = asyncio.run(run())
        assert any(m["type"] == "ERROR" for m in msgs), f"outsider subscribe not rejected: {msgs}"
