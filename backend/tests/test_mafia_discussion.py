"""MAFIA_DISCUSSION phase: private mafia state, private chat, target voting, and security.

Room uses max timers (180s) so all assertions run inside a single MAFIA_DISCUSSION window.
6 players / 2 MAFIA so 'cannot target teammate' can be tested with a real teammate.
"""
import pytest

from conftest import API, create_room, join_room, get_state, wait_for_phase, roles_map


SETTINGS = {
    "max_players": 6,
    "mafia_count": 2,
    "doctor_count": 1,
    "detective_count": 1,
    "mafia_discussion_seconds": 180,
    "night_actions_seconds": 180,
    "discussion_seconds": 30,
    "voting_seconds": 20,
    "reveal_eliminated_role": True,
    "host_can_view_mafia_chat": False,
}


@pytest.fixture(scope="class")
def game(make_user, tracker):
    host = make_user("mdhost")
    others = [make_user(f"md{i}") for i in range(1, 6)]
    room = create_room(host, SETTINGS)
    tracker["rooms"].append(room["id"])
    for u in others:
        join_room(u, room["room_code"])
    users = [host] + others

    r = host["s"].post(f"{API}/rooms/{room['id']}/start", timeout=60)
    assert r.status_code == 200, f"start failed {r.status_code}: {r.text[:300]}"

    st = wait_for_phase(host, room["id"], "MAFIA_DISCUSSION", timeout=40)
    assert st is not None, "game never reached MAFIA_DISCUSSION"
    rm = roles_map(host, room["id"], users)
    return {"room": room, "host": host, "users": users, "roles": rm}


class TestMafiaDiscussion:
    # ---- phase transition ----
    def test_phase_is_mafia_discussion(self, game):
        st = get_state(game["host"], game["room"]["id"])
        assert st["session"]["current_phase"] == "MAFIA_DISCUSSION"
        assert st["session"]["round_number"] == 1
        assert st["session"]["phase_ends_at"]

    def test_role_distribution(self, game):
        rm = game["roles"]
        assert len(rm.get("MAFIA", [])) == 2
        assert len(rm.get("DOCTOR", [])) == 1
        assert len(rm.get("DETECTIVE", [])) == 1
        assert len(rm.get("CITIZEN", [])) == 2

    # ---- /mafia-state authorization ----
    def test_mafia_can_read_private_state(self, game):
        mafia = game["roles"]["MAFIA"][0]
        r = mafia["s"].get(f"{API}/rooms/{game['room']['id']}/mafia-state", timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        d = r.json()
        assert len(d["teammates"]) == 2
        target_ids = {t["user_id"] for t in d["available_targets"]}
        mafia_ids = {m["user"]["id"] for m in game["roles"]["MAFIA"]}
        assert len(d["available_targets"]) == 4
        assert not (target_ids & mafia_ids), "available_targets leaked a mafia member"
        assert d["phase_ends_at"]
        assert d["current_phase"] == "MAFIA_DISCUSSION"
        assert d["is_viewer"] is False
        assert isinstance(d["messages"], list)

    def test_non_mafia_forbidden_from_mafia_state(self, game):
        for role in ("CITIZEN", "DOCTOR", "DETECTIVE"):
            for u in game["roles"].get(role, []):
                r = u["s"].get(f"{API}/rooms/{game['room']['id']}/mafia-state", timeout=30)
                assert r.status_code == 403, f"{role} got {r.status_code}"
                detail = r.json().get("detail", "")
                assert isinstance(detail, str) and detail, f"{role} missing detail"
                assert any("\u0600" <= ch <= "\u06ff" for ch in detail), f"detail not Arabic: {detail}"

    # ---- mafia chat ----
    def test_mafia_message_flow(self, game):
        rid = game["room"]["id"]
        m1, m2 = game["roles"]["MAFIA"]
        r = m1["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": "TEST_hello_team"}, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        r = m2["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": "TEST_reply_ok"}, timeout=30)
        assert r.status_code == 200

        for m in (m1, m2):
            d = m["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30).json()
            texts = [x["message"] for x in d["messages"]]
            assert "TEST_hello_team" in texts
            assert "TEST_reply_ok" in texts
            senders = {x["sender_user_id"] for x in d["messages"]}
            assert m1["user"]["id"] in senders and m2["user"]["id"] in senders
            assert all(x["round_number"] == 1 for x in d["messages"])

    def test_non_mafia_cannot_send_mafia_message(self, game):
        rid = game["room"]["id"]
        for role in ("CITIZEN", "DOCTOR", "DETECTIVE"):
            u = game["roles"][role][0]
            r = u["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": "TEST_intruder"}, timeout=30)
            assert r.status_code == 403, f"{role} got {r.status_code}"
        d = game["roles"]["MAFIA"][0]["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30).json()
        assert "TEST_intruder" not in [x["message"] for x in d["messages"]]

    def test_message_validation(self, game):
        rid = game["room"]["id"]
        m1 = game["roles"]["MAFIA"][0]
        assert m1["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": ""}, timeout=30).status_code == 422
        assert m1["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": "x" * 501}, timeout=30).status_code == 422

    # ---- target voting ----
    def test_target_vote_valid_and_upsertable(self, game):
        rid = game["room"]["id"]
        m1 = game["roles"]["MAFIA"][0]
        a = game["roles"]["CITIZEN"][0]
        b = game["roles"]["DOCTOR"][0]

        r = m1["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                         json={"target_user_id": a["user"]["id"]}, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        d = m1["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30).json()
        assert d["my_target_vote"] == a["user"]["id"]

        r = m1["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                         json={"target_user_id": b["user"]["id"]}, timeout=30)
        assert r.status_code == 200
        d = m1["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30).json()
        assert d["my_target_vote"] == b["user"]["id"], "target vote not upserted"
        mine = [v for v in d["current_votes"] if v["voter_id"] == m1["user"]["id"]]
        assert len(mine) == 1, f"duplicate vote rows: {mine}"

    def test_cannot_target_mafia_teammate(self, game):
        rid = game["room"]["id"]
        m1, m2 = game["roles"]["MAFIA"]
        r = m1["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                         json={"target_user_id": m2["user"]["id"]}, timeout=30)
        assert r.status_code == 400, f"{r.status_code}: {r.text[:200]}"
        assert "لا يمكن استهداف زميل Mafia" in r.json()["detail"]

    def test_cannot_target_self(self, game):
        rid = game["room"]["id"]
        m1 = game["roles"]["MAFIA"][0]
        r = m1["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                         json={"target_user_id": m1["user"]["id"]}, timeout=30)
        assert r.status_code == 400

    def test_non_mafia_cannot_target_vote(self, game):
        rid = game["room"]["id"]
        victim = game["roles"]["CITIZEN"][0]["user"]["id"]
        for role in ("CITIZEN", "DOCTOR", "DETECTIVE"):
            u = game["roles"][role][0]
            r = u["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                            json={"target_user_id": victim}, timeout=30)
            assert r.status_code == 400, f"{role} got {r.status_code}"

    def test_target_vote_unknown_target(self, game):
        rid = game["room"]["id"]
        m1 = game["roles"]["MAFIA"][0]
        r = m1["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                         json={"target_user_id": "does-not-exist"}, timeout=30)
        assert r.status_code == 400

    # ---- night action timing ----
    def test_doctor_protect_rejected_during_mafia_discussion(self, game):
        rid = game["room"]["id"]
        doc = game["roles"]["DOCTOR"][0]
        r = doc["s"].post(f"{API}/rooms/{rid}/night-action",
                          json={"action_type": "PROTECT", "target_user_id": doc["user"]["id"]}, timeout=30)
        assert r.status_code == 400, f"{r.status_code}: {r.text[:200]}"
        assert "ليس وقت الحركة الليلية" in r.json()["detail"]

    def test_detective_investigate_rejected_during_mafia_discussion(self, game):
        rid = game["room"]["id"]
        det = game["roles"]["DETECTIVE"][0]
        target = game["roles"]["CITIZEN"][0]["user"]["id"]
        r = det["s"].post(f"{API}/rooms/{rid}/night-action",
                          json={"action_type": "INVESTIGATE", "target_user_id": target}, timeout=30)
        assert r.status_code == 400
        assert "ليس وقت الحركة الليلية" in r.json()["detail"]

    # ---- /state leakage ----
    def test_state_does_not_leak_roles_or_mafia_data(self, game):
        rid = game["room"]["id"]
        for u in game["users"]:
            st = get_state(u, rid)
            assert all(p["role"] is None for p in st["session"]["players"]), "roles leaked via /state"
            my_role = st["me"]["role"]
            if my_role == "MAFIA":
                assert len(st["me"]["mafia_partners"]) == 1
            else:
                assert st["me"]["mafia_partners"] == [], f"{my_role} got mafia_partners"
            assert "TEST_hello_team" not in str(st), "mafia chat leaked into /state"

    def test_non_member_cannot_read_state_or_mafia_state(self, game, make_user):
        rid = game["room"]["id"]
        outsider = make_user("mdout")
        r = outsider["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30)
        assert r.status_code == 403
        r = outsider["s"].get(f"{API}/rooms/{rid}", timeout=30)
        assert r.status_code == 403
