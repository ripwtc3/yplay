"""host_can_view_mafia_chat setting: host observer access to the mafia private channel."""
import pytest

from conftest import API, create_room, join_room, wait_for_phase, roles_map, get_state


def _settings(host_view: bool):
    return {
        "max_players": 4,
        "mafia_count": 1,
        "doctor_count": 1,
        "detective_count": 1,
        "mafia_discussion_seconds": 180,
        "night_actions_seconds": 180,
        "discussion_seconds": 30,
        "voting_seconds": 20,
        "reveal_eliminated_role": False,
        "host_can_view_mafia_chat": host_view,
    }


def _boot(make_user, tracker, tag, host_view):
    host = make_user(f"{tag}h")
    others = [make_user(f"{tag}{i}") for i in range(1, 4)]
    room = create_room(host, _settings(host_view))
    tracker["rooms"].append(room["id"])
    for u in others:
        join_room(u, room["room_code"])
    users = [host] + others
    r = host["s"].post(f"{API}/rooms/{room['id']}/start", timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert wait_for_phase(host, room["id"], "MAFIA_DISCUSSION", timeout=40) is not None
    return {"room": room, "host": host, "users": users, "roles": roles_map(host, room["id"], users)}


@pytest.fixture(scope="class")
def game_on(make_user, tracker):
    return _boot(make_user, tracker, "hv", True)


@pytest.fixture(scope="class")
def game_off(make_user, tracker):
    return _boot(make_user, tracker, "hn", False)


class TestHostViewerEnabled:
    def test_host_can_read_mafia_state(self, game_on):
        rid = game_on["room"]["id"]
        host = game_on["host"]
        host_role = get_state(host, rid)["me"]["role"]
        r = host["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30)
        assert r.status_code == 200, f"host role={host_role} got {r.status_code}: {r.text[:300]}"
        d = r.json()
        assert len(d["teammates"]) == 1
        # is_viewer is true whenever host_can_view_mafia_chat is on for the host account
        assert d["is_viewer"] is True, f"is_viewer={d['is_viewer']} host_role={host_role}"
        print(f"host role is {host_role}; is_viewer={d['is_viewer']}")

    def test_non_mafia_players_still_blocked(self, game_on):
        rid = game_on["room"]["id"]
        host_id = game_on["host"]["user"]["id"]
        blocked = 0
        for role in ("CITIZEN", "DOCTOR", "DETECTIVE"):
            for u in game_on["roles"].get(role, []):
                if u["user"]["id"] == host_id:
                    continue
                r = u["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30)
                assert r.status_code == 403, f"{role} got {r.status_code}"
                blocked += 1
        assert blocked >= 1

    def test_host_can_post_into_mafia_chat(self, game_on):
        rid = game_on["room"]["id"]
        host = game_on["host"]
        r = host["s"].post(f"{API}/rooms/{rid}/mafia-message", json={"message": "TEST_host_msg"}, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        mafia = game_on["roles"]["MAFIA"][0]
        d = mafia["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30).json()
        assert "TEST_host_msg" in [m["message"] for m in d["messages"]]

    def test_host_observer_cannot_target_vote_unless_mafia(self, game_on):
        rid = game_on["room"]["id"]
        host = game_on["host"]
        host_role = get_state(host, rid)["me"]["role"]
        if host_role == "MAFIA":
            pytest.skip("host was dealt MAFIA this run; covered elsewhere")
        target = game_on["roles"]["CITIZEN"][0]["user"]["id"]
        r = host["s"].post(f"{API}/rooms/{rid}/mafia-target-vote",
                           json={"target_user_id": target}, timeout=30)
        assert r.status_code == 400, f"non-mafia host could target vote: {r.status_code}"


class TestHostViewerDisabled:
    def test_non_mafia_host_blocked(self, game_off):
        rid = game_off["room"]["id"]
        host = game_off["host"]
        host_role = get_state(host, rid)["me"]["role"]
        r = host["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30)
        if host_role == "MAFIA":
            assert r.status_code == 200
            assert r.json()["is_viewer"] is False
        else:
            assert r.status_code == 403, f"host role={host_role} got {r.status_code}"

    def test_all_non_mafia_blocked(self, game_off):
        rid = game_off["room"]["id"]
        for u in game_off["users"]:
            role = get_state(u, rid)["me"]["role"]
            r = u["s"].get(f"{API}/rooms/{rid}/mafia-state", timeout=30)
            expected = 200 if role == "MAFIA" else 403
            assert r.status_code == expected, f"role={role} got {r.status_code}"
