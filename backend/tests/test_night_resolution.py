"""Mafia target-vote resolution rules: majority wins, tie = no kill; doctor protect saves."""
import pytest

from conftest import API, create_room, join_room, get_state, wait_for_phase, roles_map


def _settings():
    return {
        "max_players": 6,
        "mafia_count": 2,
        "doctor_count": 1,
        "detective_count": 1,
        "mafia_discussion_seconds": 12,
        "night_actions_seconds": 15,
        "discussion_seconds": 60,
        "voting_seconds": 20,
        "reveal_eliminated_role": True,
        "host_can_view_mafia_chat": False,
    }


def _boot(make_user, tracker, tag):
    host = make_user(f"{tag}h")
    others = [make_user(f"{tag}{i}") for i in range(1, 6)]
    room = create_room(host, _settings())
    tracker["rooms"].append(room["id"])
    for u in others:
        join_room(u, room["room_code"])
    users = [host] + others
    r = host["s"].post(f"{API}/rooms/{room['id']}/start", timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert wait_for_phase(host, room["id"], "MAFIA_DISCUSSION", timeout=40, interval=1.0) is not None
    return {"room": room, "host": host, "users": users, "roles": roles_map(host, room["id"], users)}


@pytest.fixture(scope="class")
def tie_game(make_user, tracker):
    return _boot(make_user, tracker, "tie")


@pytest.fixture(scope="class")
def prot_game(make_user, tracker):
    return _boot(make_user, tracker, "prt")


class TestTieNoKill:
    def test_split_mafia_votes_results_in_no_kill(self, tie_game):
        rid = tie_game["room"]["id"]
        m1, m2 = tie_game["roles"]["MAFIA"]
        c1, c2 = tie_game["roles"]["CITIZEN"]
        assert m1["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                            json={"target_user_id": c1["user"]["id"]}, timeout=30).status_code == 200
        assert m2["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                            json={"target_user_id": c2["user"]["id"]}, timeout=30).status_code == 200
        d = m1["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30).json()
        assert len(d["current_votes"]) == 2
        assert {v["target_id"] for v in d["current_votes"]} == {c1["user"]["id"], c2["user"]["id"]}

        st = wait_for_phase(m1, rid, ["NIGHT_RESULT", "DISCUSSION"], timeout=60, interval=1.0)
        assert st is not None, "never reached NIGHT_RESULT"
        alive = [p for p in st["session"]["players"] if p["alive"]]
        assert len(alive) == 6, f"tie should mean no kill, alive={len(alive)}"


class TestDoctorProtectSaves:
    def test_protected_target_survives(self, prot_game):
        rid = prot_game["room"]["id"]
        m1, m2 = prot_game["roles"]["MAFIA"]
        doctor = prot_game["roles"]["DOCTOR"][0]
        victim = prot_game["roles"]["CITIZEN"][0]

        for m in (m1, m2):
            assert m["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                               json={"target_user_id": victim["user"]["id"]}, timeout=30).status_code == 200

        st = wait_for_phase(doctor, rid, "NIGHT_ACTIONS", timeout=40, interval=1.0)
        assert st is not None, "never reached NIGHT_ACTIONS"
        r = doctor["s"].post(f"{API}/rooms/{rid}/night-action",
                             json={"action_type": "PROTECT", "target_user_id": victim["user"]["id"]}, timeout=30)
        assert r.status_code == 200, r.text[:200]

        st = wait_for_phase(doctor, rid, ["NIGHT_RESULT", "DISCUSSION"], timeout=60, interval=1.0)
        assert st is not None
        players = {p["user_id"]: p for p in st["session"]["players"]}
        assert players[victim["user"]["id"]]["alive"] is True, "doctor protection did not save the target"
        assert len([p for p in st["session"]["players"] if p["alive"]]) == 6
