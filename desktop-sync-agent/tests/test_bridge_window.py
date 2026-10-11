"""The window's logic that does not need a window: the health sentence, settings, the companies list and what
the web page is allowed to call."""
import time
from types import SimpleNamespace

import pytest

import bridge_core as core
import webview_app
from config import AgentConfig, load_config

BASE = {"status": "ONLINE", "last_sync_status": "Up-to-date", "last_sync_time": None, "last_sync_timestr": "Never",
        "auth_halt_reason": "", "auth_halt_message": "", "active_company_name": "Demo Traders", "cloud_message": ""}


@pytest.mark.parametrize("over, kind, action", [
    ({"last_sync_time": None}, "idle", "sync"),
    ({"last_sync_time": time.time() - 600}, "idle", "sync"),
    ({"last_sync_time": time.time()}, "ok", "sync"),
    ({"last_sync_time": time.time(), "last_sync_status": "Up-to-date | 'X' is not open in Tally"}, "warn", "sync"),
    ({"last_sync_time": time.time(), "last_sync_status": "Sync failed: timeout"}, "warn", "sync"),
    ({"status": "SYNCING"}, "sync", "sync"),
    ({"status": "PAUSED"}, "paused", "resume"),
    ({"status": "TALLY OFFLINE"}, "error", "retry"),
    ({"status": "CLOUD OFFLINE"}, "error", "retry"),
    ({"status": "SIGNED OUT", "auth_halt_reason": "admin_revoke", "auth_halt_message": "Signed out by an administrator."}, "error", "signin"),
])
def test_health_shows_the_most_urgent_state(over, kind, action):
    health = core.health_from_status({**BASE, **over})
    assert (health["kind"], health["action"]) == (kind, action)
    assert health["title"]


def test_a_sign_out_outranks_everything_else():
    health = core.health_from_status({**BASE, "status": "SYNCING", "auth_halt_reason": "blocked"})
    assert health["action"] == "signin" and "blocked" in health["title"]


def test_log_lines_lose_their_emoji_but_keep_their_meaning():
    assert core.log_line("✅ Synced 3 vouchers", "INFO") == ("Synced 3 vouchers", "success")
    assert core.log_line("❌ Push failed", "INFO") == ("Push failed", "error")
    assert core.log_line("⚠️ Tally is slow", "WARNING") == ("Tally is slow", "warning")
    assert core.log_line("plain", "INFO") == ("plain", "info")


def test_split_tally_url():
    assert core.split_tally_url("http://192.168.1.20:9001/") == ("192.168.1.20", "9001")
    assert core.split_tally_url("") == ("127.0.0.1", "9000")


class FakeAgent:
    def __init__(self):
        self.reloaded = 0
        self.cloud = SimpleNamespace(device_mode=True)
        self.tally = SimpleNamespace(get_open_companies=lambda: [])
        self._linked = []

    def reload_config(self, config=None):
        self.reloaded += 1

    def linked_companies(self):
        return self._linked


@pytest.fixture
def host(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(core, "install_startup", lambda *a, **k: calls.append("install"))
    monkeypatch.setattr(core, "uninstall_startup", lambda *a, **k: calls.append("uninstall"))
    return SimpleNamespace(config=AgentConfig(), config_file=str(tmp_path / "agent_config.json"), agent=FakeAgent(), startup=calls)


def test_settings_are_saved_and_the_agent_reloaded(host):
    ok, message = core.apply_settings(host, {"tally_host": " tallypc ", "tally_port": "9001", "backend_url": " https://x.example ",
                                             "outbound_seconds": "0", "inbound_seconds": "2", "vouchers_per_range": "40",
                                             "auto_discover_paths": False, "force_full_sync": True, "autostart": True})
    assert (ok, message) == (True, "Saved")
    saved = load_config(host.config_file)
    assert saved.tally_url == "http://tallypc:9001" and saved.backend_url == "https://x.example"
    # Too-small intervals are raised to the floor, so the agent can't be set to hammer Tally or the server
    assert (saved.sync_interval_seconds, saved.inbound_interval_seconds, saved.vouchers_per_range) == (1, 5, 40)
    assert saved.force_full_sync is True and saved.auto_discover_paths is False
    assert host.startup == ["install"] and host.agent.reloaded == 1


def test_settings_that_are_not_numbers_change_nothing(host):
    ok, message = core.apply_settings(host, {"outbound_seconds": "soon", "inbound_seconds": "60", "vouchers_per_range": "50"})
    assert not ok and "whole numbers" in message
    assert host.agent.reloaded == 0 and host.startup == [] and host.config.sync_interval_seconds == 5


def test_companies_overview_says_how_each_company_stands():
    agent = FakeAgent()
    agent._linked = [{"guid": "g1", "name": "Old Name"}, {"guid": "g2", "name": "Closed Co"}, {"guid": "g4", "name": "Twin"}]
    open_now = [{"guid": "g1", "name": "New Name"}, {"guid": "g3", "name": "Not Linked"}, {"guid": "g4", "name": "Twin"}, {"guid": "g5", "name": "Twin"}]
    agent.tally.get_open_companies = lambda: open_now
    overview = core.companies_overview(agent)
    by_guid = {c["guid"]: c for c in overview["linked"]}
    assert by_guid["g1"]["name"] == "New Name" and by_guid["g1"]["kind"] == "ok"   # the name Tally shows now
    assert by_guid["g2"]["kind"] == "idle" and "Closed" in by_guid["g2"]["note"]
    assert by_guid["g4"]["kind"] == "warn"                                           # two open companies share its name
    assert [c["guid"] for c in overview["unlinked"]] == ["g3", "g5"]
    assert set(overview["open"]) == {"g1", "g3", "g4", "g5"}


def test_companies_overview_does_not_ask_tally_before_the_pc_is_signed_in():
    agent = FakeAgent()
    agent.cloud.device_mode = False
    agent.tally.get_open_companies = lambda: pytest.fail("Tally was asked")
    assert core.companies_overview(agent)["device_mode"] is False


# -- what the web page can call ---------------------------------------------
@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "install_startup", lambda *a, **k: None)
    monkeypatch.setattr(core, "uninstall_startup", lambda *a, **k: None)
    session = webview_app.Session(config_file=str(tmp_path / "agent_config.json"))
    session.config.backend_url = ""
    return webview_app.Api(session)


def test_the_page_never_sees_a_secret(api):
    api._session.config.device_token = "mta_secret-token"
    api._session.config.password = "hunter2-password"
    api._session.config.auth_token = "jwt-secret"
    api._session.config.backend_url = "https://x.example"
    seen = repr([api.boot(), api.settings(), api.state(0)])
    assert "secret" not in seen and "hunter2" not in seen
    # pywebview offers the page every attribute without a leading underscore: none of them may be data
    public = [name for name in vars(api) if not name.startswith("_")]
    assert public == []


def test_state_only_sends_log_lines_the_page_has_not_seen(api):
    api._session._on_agent_log("✅ one", "INFO")
    first = api.state(0)
    assert [line["text"] for line in first["logs"]] == ["one"] and first["logs"][0]["tag"] == "success"
    api._session._on_agent_log("two", "ERROR")
    second = api.state(first["seq"])
    assert [line["text"] for line in second["logs"]] == ["two"]
    assert api.state(second["seq"])["logs"] == []


def test_sign_in_needs_a_server_address(api):
    assert api.sign_in({"server": " ", "email": "a@b.c", "password": "x"})["ok"] is False


def test_the_page_never_sees_the_secret_behind_a_sign_in_code(api, monkeypatch):
    assert api.code_start({"server": " "})["ok"] is False
    assert api.code_check({})["status"] == "error"   # no code was ever asked for
    monkeypatch.setattr(core, "start_code_sign_in", lambda url: (True, {"code": "ABCD-2345", "poll_token": "secret", "expires_in_minutes": 10}))
    assert api.code_start({"server": "https://x.example"}) == {"ok": True, "code": "ABCD-2345", "minutes": 10}

    asked = []
    monkeypatch.setattr(core, "finish_code_sign_in", lambda host, url, token, *rest: (asked.append((url, token)), ("pending", ""))[1])
    assert api.code_check({}) == {"status": "pending"}
    assert asked == [("https://x.example", "secret")]

    monkeypatch.setattr(core, "finish_code_sign_in", lambda *a: ("error", "That code has expired. Ask for a new one."))
    assert "expired" in api.code_check({})["message"]
    assert api.code_check({})["message"] == "Ask for a new code."   # the used-up code is forgotten


def test_a_code_entered_in_the_app_signs_the_pc_in_and_links_its_company(api, monkeypatch):
    monkeypatch.setattr(core, "start_code_sign_in", lambda url: (True, {"code": "ABCD-2345", "poll_token": "secret"}))
    monkeypatch.setattr(core, "finish_code_sign_in", lambda *a: ("approved", ""))
    monkeypatch.setattr(api, "_link_active", lambda take_over: {"ok": True})
    api.code_start({"server": "https://x.example"})
    assert api.code_check({"company": "Demo Traders"}) == {"status": "done", "ok": True}


def test_linking_needs_a_company_seen_open_in_tally(api):
    result = api.link_company("guid-the-page-made-up")
    assert result["ok"] is False and "no longer open" in result["message"]


def test_theme_is_saved_and_checked(api):
    assert api.set_theme("dark")["ok"] and load_config(api._session.config_file).theme == "dark"
    assert api.set_theme("<script>")["ok"] is False
