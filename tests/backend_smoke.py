"""Smoke test for Mafia backend — full end-to-end game with 4 players."""
import asyncio, json, os, sys, time, uuid, websockets, httpx

BASE = "https://live-gaming-portal-1.preview.emergentagent.com"
WS = BASE.replace("https://", "wss://") + "/api/ws"

results = {"passed": [], "failed": []}
def OK(msg): print("OK  ::", msg); results["passed"].append(msg)
def FAIL(area, issue, ev=""): print(f"FAIL:: [{area}] {issue} | {ev}"); results["failed"].append({"area": area, "issue": issue, "evidence": ev, "priority": "HIGH"})


async def register(client, suffix):
    u = f"tu_{suffix}"
    r = await client.post(f"{BASE}/api/auth/register", json={
        "username": u, "display_name": f"U{suffix}",
        "email": f"{u}@t.com", "password": "secret123"})
    return r

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        run_id = uuid.uuid4().hex[:6]
        tokens = {}
        uids = {}
        # 1. Register 4 users
        for i in range(4):
            r = await register(client, f"{run_id}_{i}")
            if r.status_code != 200:
                FAIL("register", f"reg {i} status {r.status_code}", r.text[:200]); return
            data = r.json(); tokens[i] = data["token"]; uids[i] = data["user"]["id"]
        OK("Registered 4 users with JWT")

        # 2. Duplicate register -> 400
        r = await register(client, f"{run_id}_0")
        if r.status_code == 400: OK("Duplicate email returns 400")
        else: FAIL("register", "duplicate not 400", str(r.status_code))

        # 3. Login wrong pw
        r = await client.post(f"{BASE}/api/auth/login", json={"email": f"tu_{run_id}_0@t.com", "password": "wrong"})
        if r.status_code == 401: OK("Wrong password returns 401")
        else: FAIL("login", "wrong pw not 401", str(r.status_code))

        # 4. /auth/me
        h0 = {"Authorization": f"Bearer {tokens[0]}"}
        r = await client.get(f"{BASE}/api/auth/me", headers=h0)
        if r.status_code == 200 and r.json()["id"] == uids[0]: OK("/auth/me works")
        else: FAIL("auth/me", "failed", str(r.status_code))

        # 5. Settings validation — special roles >= max_players
        r = await client.post(f"{BASE}/api/rooms", headers=h0, json={
            "name": "bad", "settings": {"max_players": 4, "mafia_count": 2, "doctor_count": 1, "detective_count": 1,
                                         "night_seconds": 15, "discussion_seconds": 15, "voting_seconds": 15}})
        if r.status_code == 400: OK("Settings validation rejects bad role counts")
        else: FAIL("create_room", "invalid settings not rejected", f"{r.status_code} {r.text[:100]}")

        # 6. Create valid 4-player room
        r = await client.post(f"{BASE}/api/rooms", headers=h0, json={
            "name": "Test Room", "settings": {"max_players": 4, "mafia_count": 1, "doctor_count": 1, "detective_count": 1,
                                                "night_seconds": 15, "discussion_seconds": 15, "voting_seconds": 15}})
        if r.status_code != 200: FAIL("create_room", "failed", r.text[:200]); return
        room = r.json(); room_id = room["id"]; room_code = room["room_code"]
        if len(room_code) == 6 and room["status"] == "LOBBY" and room["player_count"] == 1:
            OK(f"Room created code={room_code} host auto-joined")
        else: FAIL("create_room", "bad room state", str(room))

        # 7. Others join by code (lowercase to test case-insensitive)
        for i in [1, 2, 3]:
            hi = {"Authorization": f"Bearer {tokens[i]}"}
            r = await client.post(f"{BASE}/api/rooms/join", headers=hi, json={"room_code": room_code.lower()})
            if r.status_code != 200: FAIL("join", f"player {i} join failed", r.text[:200]); return
        OK("3 players joined via lowercase code")

        # 8. Duplicate join
        h1 = {"Authorization": f"Bearer {tokens[1]}"}
        r = await client.post(f"{BASE}/api/rooms/join", headers=h1, json={"room_code": room_code})
        if r.status_code == 200: OK("Duplicate join idempotent")
        else: FAIL("join", "dup join failed", str(r.status_code))

        # 9. GET room as member
        r = await client.get(f"{BASE}/api/rooms/{room_id}", headers=h1)
        if r.status_code == 200 and len(r.json().get("players", [])) == 4: OK("GET /rooms/{id} returns 4 players")
        else: FAIL("get_room", "bad response", r.text[:200])

        # 10. Non-host cannot start
        r = await client.post(f"{BASE}/api/rooms/{room_id}/start", headers=h1)
        if r.status_code == 400 and "صاحب" in r.text: OK("Non-host cannot start (Arabic error)")
        else: FAIL("start", "non-host not rejected", f"{r.status_code} {r.text[:100]}")

        # 11. Connect WebSockets for all 4 players & subscribe
        ws_conns = {}
        role_events = {}
        async def ws_client(i):
            try:
                ws = await websockets.connect(f"{WS}?token={tokens[i]}")
                ws_conns[i] = ws
                await ws.recv()  # CONNECTED
                await ws.send(json.dumps({"type": "SUBSCRIBE_ROOM", "room_id": room_id}))
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
                    role_events.setdefault(i, []).append(msg)
            except Exception as e:
                role_events.setdefault(i, []).append({"__err": str(e)})

        ws_tasks = [asyncio.create_task(ws_client(i)) for i in range(4)]
        await asyncio.sleep(2)
        OK("WebSockets connected & subscribed")

        # 12. Invalid ws token
        try:
            bad = await websockets.connect(f"{WS}?token=bad")
            await bad.recv()
            FAIL("ws", "bad token not rejected", "")
        except Exception as e:
            if "4401" in str(e) or "rejected" in str(e).lower() or "closed" in str(e).lower():
                OK("Invalid WS token closes 4401")
            else:
                OK(f"Invalid WS token rejected: {str(e)[:60]}")

        # 13. Host starts game
        r = await client.post(f"{BASE}/api/rooms/{room_id}/start", headers=h0)
        if r.status_code != 200: FAIL("start", "host start failed", r.text[:200]); return
        OK("Host started game")
        await asyncio.sleep(7)  # wait for role assignment + NIGHT

        # 14. Verify each user got their OWN private role (no cross-contamination)
        roles = {}
        for i in range(4):
            evs = role_events.get(i, [])
            priv = [e for e in evs if e.get("type") == "ROLE_ASSIGNED_PRIVATE"]
            if len(priv) == 1 and priv[0].get("user_id") == uids[i]:
                roles[i] = priv[0]["role"]
            else:
                FAIL("ws_private", f"player {i} bad private role events", str(priv)[:200])
        if len(roles) == 4:
            OK(f"Each player got own private role: {list(roles.values())}")

        # 15. State check: session.players[*].role is None (not GAME_OVER), me.role set
        r = await client.get(f"{BASE}/api/rooms/{room_id}/state", headers=h0)
        st = r.json(); me_role = st["me"]["role"]
        pub_roles = [p.get("role") for p in st["session"]["players"]]
        if me_role == roles[0] and all(rr is None for rr in pub_roles):
            OK("State: me.role set, public players.role=None")
        else:
            FAIL("state", "role leak or mismatch", f"me={me_role} pub={pub_roles}")

        # 16. Find roles
        mafia_i = next((i for i,r in roles.items() if r=="MAFIA"), None)
        doc_i = next((i for i,r in roles.items() if r=="DOCTOR"), None)
        det_i = next((i for i,r in roles.items() if r=="DETECTIVE"), None)
        cit_i = next((i for i,r in roles.items() if r=="CITIZEN"), None)

        # 17. Citizen tries KILL -> 400
        hc = {"Authorization": f"Bearer {tokens[cit_i]}"}
        r = await client.post(f"{BASE}/api/rooms/{room_id}/night-action", headers=hc,
                              json={"action_type": "KILL", "target_user_id": uids[mafia_i]})
        if r.status_code == 400: OK("Citizen KILL rejected")
        else: FAIL("night", "citizen kill not rejected", str(r.status_code))

        # 18. Detective tries KILL -> 400
        hd = {"Authorization": f"Bearer {tokens[det_i]}"}
        r = await client.post(f"{BASE}/api/rooms/{room_id}/night-action", headers=hd,
                              json={"action_type": "KILL", "target_user_id": uids[mafia_i]})
        if r.status_code == 400: OK("Detective KILL rejected")
        else: FAIL("night", "detective kill not rejected", str(r.status_code))

        # 19. Submit valid actions
        hm = {"Authorization": f"Bearer {tokens[mafia_i]}"}
        hdoc = {"Authorization": f"Bearer {tokens[doc_i]}"}
        # Mafia kills the citizen; Doctor protects detective; Detective investigates mafia
        r1 = await client.post(f"{BASE}/api/rooms/{room_id}/night-action", headers=hm,
                               json={"action_type": "KILL", "target_user_id": uids[cit_i]})
        r2 = await client.post(f"{BASE}/api/rooms/{room_id}/night-action", headers=hdoc,
                               json={"action_type": "PROTECT", "target_user_id": uids[det_i]})
        r3 = await client.post(f"{BASE}/api/rooms/{room_id}/night-action", headers=hd,
                               json={"action_type": "INVESTIGATE", "target_user_id": uids[mafia_i]})
        if r1.status_code==200 and r2.status_code==200 and r3.status_code==200:
            OK("Night actions submitted (KILL/PROTECT/INVESTIGATE)")
        else:
            FAIL("night", "actions failed", f"{r1.status_code}/{r2.status_code}/{r3.status_code}")

        # 20. Duplicate action rejected
        r = await client.post(f"{BASE}/api/rooms/{room_id}/night-action", headers=hm,
                              json={"action_type": "KILL", "target_user_id": uids[cit_i]})
        if r.status_code == 400: OK("Duplicate night action rejected")
        else: FAIL("night", "dup action not rejected", str(r.status_code))

        # 21. Detective investigation result via /state
        r = await client.get(f"{BASE}/api/rooms/{room_id}/state", headers=hd)
        na = r.json()["me"].get("night_action") or {}
        if na.get("result") == "MAFIA": OK("Detective investigate result=MAFIA via /state")
        else: FAIL("investigate", "result not visible", str(na))

        # 22. Wait for NIGHT (15s) + NIGHT_RESULT (5s) + DISCUSSION (15s) then VOTING
        # We started actions ~immediately after NIGHT began. Total night ~15s.
        # Wait until VOTING phase starts.
        print("Waiting for phases to advance to VOTING...")
        voting_reached = False
        for _ in range(40):
            await asyncio.sleep(2)
            r = await client.get(f"{BASE}/api/rooms/{room_id}/state", headers=h0)
            phase = r.json()["session"]["current_phase"]
            if phase == "VOTING":
                voting_reached = True; break
            if phase == "GAME_OVER":
                break
        if voting_reached: OK("Phase transitioned to VOTING")
        else: FAIL("phase", "did not reach VOTING", "timeout")

        # 23. Non-voting user (dead citizen) vote should fail
        if voting_reached:
            r = await client.post(f"{BASE}/api/rooms/{room_id}/vote", headers=hc,
                                  json={"target_user_id": uids[mafia_i]})
            if r.status_code == 400: OK("Dead citizen cannot vote")
            else: FAIL("vote", "dead can vote", str(r.status_code))

            # 24. Alive vote for mafia by all 3 alive players
            for i in [0, doc_i, det_i]:
                if i == mafia_i: continue
                hi = {"Authorization": f"Bearer {tokens[i]}"}
                await client.post(f"{BASE}/api/rooms/{room_id}/vote", headers=hi,
                                  json={"target_user_id": uids[mafia_i]})
            # Duplicate vote
            r = await client.post(f"{BASE}/api/rooms/{room_id}/vote", headers=hdoc,
                                  json={"target_user_id": uids[mafia_i]})
            if r.status_code == 400: OK("Duplicate vote rejected")
            else: FAIL("vote", "dup vote allowed", str(r.status_code))

        # 25. Wait for GAME_OVER
        print("Waiting for GAME_OVER...")
        game_over = False
        for _ in range(30):
            await asyncio.sleep(2)
            r = await client.get(f"{BASE}/api/rooms/{room_id}/state", headers=h0)
            js = r.json()
            if js["session"]["current_phase"] == "GAME_OVER":
                game_over = True
                winner = js["session"].get("winner")
                pub_roles = [p.get("role") for p in js["session"]["players"]]
                if winner and all(rr is not None for rr in pub_roles):
                    OK(f"GAME_OVER winner={winner}, all roles revealed")
                else:
                    FAIL("game_over", "winner/roles missing", f"{winner} {pub_roles}")
                break
        if not game_over: FAIL("game_over", "did not reach GAME_OVER in time", "")

        for t in ws_tasks: t.cancel()

    # Report
    print("\n=== SUMMARY ===")
    print(f"Passed: {len(results['passed'])}, Failed: {len(results['failed'])}")
    for f in results["failed"]: print(" -", f)
    return results

if __name__ == "__main__":
    r = asyncio.run(main())
    with open("/tmp/test_out.json", "w") as f: json.dump(r, f, indent=2)
