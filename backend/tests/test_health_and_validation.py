"""Health check + MafiaSettings validation (new iteration-2 settings fields)."""
import requests

from conftest import API, create_room


BASE_SETTINGS = {
    "max_players": 4,
    "mafia_count": 1,
    "doctor_count": 1,
    "detective_count": 1,
    "mafia_discussion_seconds": 20,
    "night_actions_seconds": 30,
    "discussion_seconds": 30,
    "voting_seconds": 20,
    "reveal_eliminated_role": True,
    "host_can_view_mafia_chat": False,
}


class TestHealth:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_unauthenticated_rejected(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code == 401


class TestRoomSettingsValidation:
    """New settings: mafia_discussion_seconds, night_actions_seconds, host_can_view_mafia_chat."""

    def test_create_room_with_new_settings(self, make_user, tracker):
        host = make_user("valh")
        s = dict(BASE_SETTINGS, mafia_discussion_seconds=15, night_actions_seconds=20,
                 host_can_view_mafia_chat=True)
        room = create_room(host, s)
        tracker["rooms"].append(room["id"])
        assert room["status"] == "LOBBY"
        assert len(room["room_code"]) == 6
        assert room["settings"]["mafia_discussion_seconds"] == 15
        assert room["settings"]["night_actions_seconds"] == 20
        assert room["settings"]["host_can_view_mafia_chat"] is True
        assert room["player_count"] == 1  # host auto-joined

        # persistence check
        got = host["s"].get(f"{API}/rooms/{room['id']}", timeout=30)
        assert got.status_code == 200
        body = got.json()
        assert body["settings"]["mafia_discussion_seconds"] == 15
        assert body["settings"]["host_can_view_mafia_chat"] is True
        assert "_id" not in body

    def test_settings_defaults(self, make_user, tracker):
        host = make_user("valdef")
        s = {"max_players": 4, "mafia_count": 1, "doctor_count": 1, "detective_count": 1}
        room = create_room(host, s)
        tracker["rooms"].append(room["id"])
        assert room["settings"]["mafia_discussion_seconds"] == 20
        assert room["settings"]["night_actions_seconds"] == 30
        assert room["settings"]["host_can_view_mafia_chat"] is False

    def test_invalid_ranges_return_422(self, make_user):
        host = make_user("valbad")
        cases = [
            ("mafia_discussion_seconds", 9),
            ("mafia_discussion_seconds", 181),
            ("night_actions_seconds", 14),
            ("night_actions_seconds", 181),
            ("discussion_seconds", 14),
            ("voting_seconds", 400),
        ]
        for field, val in cases:
            s = dict(BASE_SETTINGS)
            s[field] = val
            r = host["s"].post(f"{API}/rooms", json={"name": "TEST_bad", "settings": s}, timeout=30)
            assert r.status_code == 422, f"{field}={val} -> {r.status_code} {r.text[:200]}"

    def test_invalid_role_distribution_400(self, make_user):
        host = make_user("valdist")
        s = dict(BASE_SETTINGS, max_players=4, mafia_count=2, doctor_count=1, detective_count=1)
        r = host["s"].post(f"{API}/rooms", json={"name": "TEST_bad2", "settings": s}, timeout=30)
        assert r.status_code == 400
        assert isinstance(r.json().get("detail"), str)

    def test_host_can_view_mafia_chat_bad_type_422(self, make_user):
        host = make_user("valtype")
        s = dict(BASE_SETTINGS, host_can_view_mafia_chat="maybe")
        r = host["s"].post(f"{API}/rooms", json={"name": "TEST_bad3", "settings": s}, timeout=30)
        assert r.status_code == 422
