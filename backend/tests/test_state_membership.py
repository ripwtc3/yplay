"""Ad-hoc security probe: is GET /rooms/{id}/state membership-protected?"""
from conftest import API, create_room, join_room, wait_for_phase


SETTINGS = {
    "max_players": 4, "mafia_count": 1, "doctor_count": 1, "detective_count": 1,
    "mafia_discussion_seconds": 180, "night_actions_seconds": 180,
    "discussion_seconds": 30, "voting_seconds": 20,
    "reveal_eliminated_role": False, "host_can_view_mafia_chat": False,
}


class TestStateMembership:
    def test_outsider_cannot_read_game_state(self, make_user, tracker):
        host = make_user("sech")
        others = [make_user(f"sec{i}") for i in range(1, 4)]
        room = create_room(host, SETTINGS)
        tracker["rooms"].append(room["id"])
        for u in others:
            join_room(u, room["room_code"])
        r = host["s"].post(f"{API}/rooms/{room['id']}/start", timeout=60)
        assert r.status_code == 200
        assert wait_for_phase(host, room["id"], "MAFIA_DISCUSSION", timeout=40) is not None

        outsider = make_user("secout")
        r = outsider["s"].get(f"{API}/rooms/{room['id']}/state", timeout=30)
        print(f"outsider /state -> {r.status_code}")
        if r.status_code == 200:
            print("LEAKED BODY KEYS:", list(r.json().keys()))
            print("session:", r.json().get("session"))
        assert r.status_code in (403, 404), (
            f"SECURITY: non-member can read /rooms/{{id}}/state (got {r.status_code})"
        )
