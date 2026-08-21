"""Connected Accounts CRUD: /api/users/me/connected-accounts."""
from conftest import API


class TestConnectedAccounts:
    def test_full_crud_and_url_generation(self, make_user):
        u = make_user("conn")
        s = u["s"]

        # initially empty
        r = s.get(f"{API}/users/me/connected-accounts", timeout=30)
        assert r.status_code == 200
        assert r.json()["accounts"] == []

        expected = {
            "twitch": "https://www.twitch.tv/mychannel",
            "youtube": "https://www.youtube.com/@mychannel",
            "tiktok": "https://www.tiktok.com/@mychannel",
            "kick": "https://kick.com/mychannel",
        }
        created = {}
        for provider, url in expected.items():
            r = s.post(f"{API}/users/me/connected-accounts",
                       json={"provider": provider, "provider_username": "mychannel"}, timeout=30)
            assert r.status_code == 200, f"{provider}: {r.status_code} {r.text[:200]}"
            body = r.json()
            assert body["provider"] == provider
            assert body["provider_username"] == "mychannel"
            assert body["channel_url"] == url, f"{provider} url={body['channel_url']}"
            assert isinstance(body["id"], str) and body["id"]
            assert body["connected_at"]
            created[provider] = body["id"]

        # GET lists all 4 (persistence verification)
        r = s.get(f"{API}/users/me/connected-accounts", timeout=30)
        accounts = r.json()["accounts"]
        assert len(accounts) == 4
        assert {a["provider"] for a in accounts} == set(expected)
        assert all("_id" not in a for a in accounts)

        # duplicate provider -> 400
        r = s.post(f"{API}/users/me/connected-accounts",
                   json={"provider": "twitch", "provider_username": "other"}, timeout=30)
        assert r.status_code == 400, f"duplicate -> {r.status_code}"

        # DELETE removes + verify
        r = s.delete(f"{API}/users/me/connected-accounts/{created['twitch']}", timeout=30)
        assert r.status_code == 200
        r = s.get(f"{API}/users/me/connected-accounts", timeout=30)
        remaining = r.json()["accounts"]
        assert len(remaining) == 3
        assert "twitch" not in {a["provider"] for a in remaining}

        # delete again -> 404
        r = s.delete(f"{API}/users/me/connected-accounts/{created['twitch']}", timeout=30)
        assert r.status_code == 404

    def test_handle_with_at_prefix_is_stripped(self, make_user):
        u = make_user("connat")
        r = u["s"].post(f"{API}/users/me/connected-accounts",
                        json={"provider": "tiktok", "provider_username": "@handle1"}, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["provider_username"] == "handle1"
        assert body["channel_url"] == "https://www.tiktok.com/@handle1"

    def test_custom_channel_url_respected(self, make_user):
        u = make_user("connurl")
        r = u["s"].post(f"{API}/users/me/connected-accounts",
                        json={"provider": "kick", "provider_username": "abc",
                              "channel_url": "https://kick.com/custom", "display_name": "My Kick"}, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["channel_url"] == "https://kick.com/custom"
        assert body["display_name"] == "My Kick"

    def test_invalid_provider_422(self, make_user):
        u = make_user("connbad")
        r = u["s"].post(f"{API}/users/me/connected-accounts",
                        json={"provider": "facebook", "provider_username": "x"}, timeout=30)
        assert r.status_code == 422

    def test_empty_username_422(self, make_user):
        u = make_user("connempty")
        r = u["s"].post(f"{API}/users/me/connected-accounts",
                        json={"provider": "twitch", "provider_username": ""}, timeout=30)
        assert r.status_code == 422

    def test_requires_auth(self):
        import requests
        r = requests.get(f"{API}/users/me/connected-accounts", timeout=30)
        assert r.status_code == 401

    def test_accounts_are_per_user(self, make_user):
        a = make_user("connA")
        b = make_user("connB")
        r = a["s"].post(f"{API}/users/me/connected-accounts",
                        json={"provider": "twitch", "provider_username": "aaa"}, timeout=30)
        assert r.status_code == 200
        acc_id = r.json()["id"]
        # B should not see A's account
        r = b["s"].get(f"{API}/users/me/connected-accounts", timeout=30)
        assert r.json()["accounts"] == []
        # B cannot delete A's account
        r = b["s"].delete(f"{API}/users/me/connected-accounts/{acc_id}", timeout=30)
        assert r.status_code == 404
