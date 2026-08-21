"""End-to-end 4-player game: MAFIA_DISCUSSION -> NIGHT_ACTIONS -> NIGHT_RESULT
-> DISCUSSION -> VOTING -> VOTE_RESULT -> GAME_OVER.
Short timers so the whole flow finishes in ~90s.
"""
import time

import pytest

from conftest import API, create_room, join_room, get_state, wait_for_phase, roles_map


SETTINGS = {
    "max_players": 4,
    "mafia_count": 1,
    "doctor_count": 1,
    "detective_count": 1,
    "mafia_discussion_seconds": 12,
    "night_actions_seconds": 30,
    "discussion_seconds": 15,
    "voting_seconds": 30,
    "reveal_eliminated_role": True,
    "host_can_view_mafia_chat": False,
}


@pytest.fixture(scope="class")
def flow(make_user, tracker):
    host = make_user("flhost")
    others = [make_user(f"fl{i}") for i in range(1, 4)]
    room = create_room(host, SETTINGS)
    tracker["rooms"].append(room["id"])
    for u in others:
        join_room(u, room["room_code"])
    users = [host] + others
    r = host["s"].post(f"{API}/rooms/{room['id']}/start", timeout=60)
    assert r.status_code == 200, f"start failed: {r.text[:300]}"
    st = wait_for_phase(host, room["id"], "MAFIA_DISCUSSION", timeout=40, interval=1.0)
    assert st is not None, "never reached MAFIA_DISCUSSION"
    rm = roles_map(host, room["id"], users)
    return {"room": room, "host": host, "users": users, "roles": rm, "log": []}


class TestFullGameFlow:
    def test_full_round_to_game_over(self, flow):
        rid = flow["room"]["id"]
        mafia = flow["roles"]["MAFIA"][0]
        doctor = flow["roles"]["DOCTOR"][0]
        detective = flow["roles"]["DETECTIVE"][0]
        citizen = flow["roles"]["CITIZEN"][0]
        print(f"roles: mafia={mafia['user']['display_name']} doctor={doctor['user']['display_name']} "
              f"det={detective['user']['display_name']} cit={citizen['user']['display_name']}")

        # ---- MAFIA_DISCUSSION: chat + pick target ----
        r = mafia["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": "TEST_kill_citizen"}, timeout=30)
        assert r.status_code == 200
        r = mafia["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                            json={"target_user_id": detective["user"]["id"]}, timeout=30)
        assert r.status_code == 200

        # ---- NIGHT_ACTIONS ----
        st = wait_for_phase(mafia, rid, "NIGHT_ACTIONS", timeout=40, interval=1.0)
        assert st is not None, "never reached NIGHT_ACTIONS"
        print("phase NIGHT_ACTIONS reached")

        # mafia may still change target during NIGHT_ACTIONS
        r = mafia["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                            json={"target_user_id": citizen["user"]["id"]}, timeout=30)
        assert r.status_code == 200, f"target change in NIGHT_ACTIONS failed: {r.text[:200]}"
        d = mafia["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30).json()
        assert d["my_target_vote"] == citizen["user"]["id"]
        assert d["current_phase"] == "NIGHT_ACTIONS"

        # mafia chat still allowed during NIGHT_ACTIONS
        r = mafia["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": "TEST_night_msg"}, timeout=30)
        assert r.status_code == 200

        # doctor protects self
        r = doctor["s"].post(f"{API}/rooms/{rid}/night-action",
                             json={"action_type": "PROTECT", "target_user_id": doctor["user"]["id"]}, timeout=30)
        assert r.status_code == 200, f"PROTECT failed: {r.text[:200]}"
        # duplicate protect -> 400
        r2 = doctor["s"].post(f"{API}/rooms/{rid}/night-action",
                              json={"action_type": "PROTECT", "target_user_id": doctor["user"]["id"]}, timeout=30)
        assert r2.status_code == 400

        # detective investigates the mafia -> MAFIA
        r = detective["s"].post(f"{API}/rooms/{rid}/night-action",
                                json={"action_type": "INVESTIGATE", "target_user_id": mafia["user"]["id"]}, timeout=30)
        assert r.status_code == 200, f"INVESTIGATE failed: {r.text[:200]}"
        st = get_state(detective, rid)
        assert st["me"]["night_action"]["result"] == "MAFIA", st["me"]["night_action"]

        # citizen has no night action
        r = citizen["s"].post(f"{API}/rooms/{rid}/night-action",
                              json={"action_type": "PROTECT", "target_user_id": doctor["user"]["id"]}, timeout=30)
        assert r.status_code == 400

        # ---- NIGHT_RESULT ----
        st = wait_for_phase(mafia, rid, ["NIGHT_RESULT", "DISCUSSION"], timeout=45, interval=1.0)
        assert st is not None, "never reached NIGHT_RESULT"
        print(f"phase after night: {st['session']['current_phase']}")
        players = {p["user_id"]: p for p in st["session"]["players"]}
        assert players[citizen["user"]["id"]]["alive"] is False, "mafia target was not eliminated"
        assert players[doctor["user"]["id"]]["alive"] is True
        assert players[detective["user"]["id"]]["alive"] is True

        # dead citizen cannot access mafia-state / vote
        r = citizen["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30)
        assert r.status_code == 403

        # ---- DISCUSSION ----
        st = wait_for_phase(mafia, rid, "DISCUSSION", timeout=30, interval=1.0)
        assert st is not None, "never reached DISCUSSION"
        # mafia chat closed outside night phases
        r = mafia["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": "TEST_day"}, timeout=30)
        assert r.status_code == 403, f"mafia chat allowed during DISCUSSION: {r.status_code}"
        r = mafia["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                            json={"target_user_id": doctor["user"]["id"]}, timeout=30)
        assert r.status_code == 400, "target vote allowed during DISCUSSION"

        # ---- VOTING: all alive lynch the mafia ----
        st = wait_for_phase(mafia, rid, "VOTING", timeout=40, interval=1.0)
        assert st is not None, "never reached VOTING"
        print("phase VOTING reached")
        for u in (doctor, detective):
            r = u["s"].post(f"{API}/rooms/{rid}/vote", json={"target_user_id": mafia["user"]["id"]}, timeout=30)
            assert r.status_code == 200, f"vote failed: {r.text[:200]}"
        r = mafia["s"].post(f"{API}/rooms/{rid}/vote", json={"target_user_id": doctor["user"]["id"]}, timeout=30)
        assert r.status_code == 200
        # dead player cannot vote
        r = citizen["s"].post(f"{API}/rooms/{rid}/vote", json={"target_user_id": mafia["user"]["id"]}, timeout=30)
        assert r.status_code == 400

        # ---- VOTE_RESULT -> GAME_OVER ----
        st = wait_for_phase(mafia, rid, "GAME_OVER", timeout=70, interval=1.5)
        assert st is not None, "never reached GAME_OVER"
        sess = st["session"]
        assert sess["winner"] == "CITIZENS", f"winner={sess['winner']}"
        revealed = {p["user_id"]: p["role"] for p in sess["players"]}
        assert all(v is not None for v in revealed.values()), "roles not revealed at GAME_OVER"
        assert revealed[mafia["user"]["id"]] == "MAFIA"
        assert revealed[doctor["user"]["id"]] == "DOCTOR"
        assert revealed[detective["user"]["id"]] == "DETECTIVE"
        assert revealed[citizen["user"]["id"]] == "CITIZEN"
        assert st["room"]["status"] == "FINISHED"

        # after GAME_OVER mafia private channel closed
        r = mafia["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30)
        assert r.status_code == 403, f"mafia-state still open after GAME_OVER: {r.status_code}"
