"""The agent identifies its PC and only logs back in by itself when that's safe."""
import json

from cloud_client import CloudClient
import agent as agent_module
from config import AgentConfig, save_config


def unauthorized(reason):
    return (401, {"detail": "Session expired or revoked"}, {"X-Auth-Reason": reason} if reason else {})


def client(backend, **kw):
    return CloudClient(backend_url=backend.url, email="agent@example.com", password="pw", **kw)


def test_requests_identify_the_pc(backend):
    c = client(backend)
    assert c.authenticate("agent@example.com", "pw")[0]
    c.fetch_outbound_queue()
    for method, path, headers in backend.requests:
        assert headers["X-Client-Type"] == "sync-agent"
        assert headers["X-Device-Id"].startswith("agent-") and len(headers["X-Device-Id"]) == 38
        assert headers["User-Agent"].startswith("SnehDistSyncAgent/")


def test_expired_and_replaced_sessions_log_in_again(backend):
    for reason in ("expired", "invalid", "replaced", None):
        c = client(backend, token="old")
        logins = backend.logins
        backend.api_responses = [unauthorized(reason), (200, [{"sync_id": 1}], {})]
        items, err = c.fetch_outbound_queue()
        assert items == [{"sync_id": 1}] and err is None, reason
        assert backend.logins == logins + 1 and c.auth_halt_reason == ""


def test_admin_sign_out_halts_instead_of_logging_back_in(backend):
    halted = []
    c = client(backend, token="old", on_auth_halted=halted.append)
    backend.api_responses = [unauthorized("admin_revoke")]
    items, err = c.fetch_outbound_queue()
    assert items == [] and "administrator" in err
    assert backend.logins == 0 and c.auth_halt_reason == "admin_revoke" and halted == ["admin_revoke"]

    # Every later call stays halted without touching /auth/login
    backend.api_responses = [unauthorized("invalid"), unauthorized("invalid")]
    c.fetch_outbound_queue()
    assert c.acknowledge_queue([1]) is False
    assert backend.logins == 0


def test_each_deliberate_reason_halts(backend):
    for reason in ("admin_revoke_all", "blocked", "password_change", "deactivated", "device_limit", "self_revoke", "logout"):
        c = client(backend, token="old")
        backend.api_responses = [unauthorized(reason)]
        c.get_last_alter_id()
        assert c.auth_halt_reason == reason and backend.logins == 0, reason


def test_blocked_pc_cannot_log_in(backend):
    backend.login_response = (403, {"detail": "This device has been blocked by your administrator."}, {"X-Auth-Reason": "device_blocked"})
    c = client(backend)
    ok, detail = c.authenticate("agent@example.com", "pw")
    assert not ok and "blocked" in detail and c.auth_halt_reason == "device_blocked"


def test_halt_survives_restart_and_clears_on_new_credentials(backend, tmp_path):
    cfg_path = str(tmp_path / "agent_config.json")
    save_config(AgentConfig(backend_url=backend.url, email="agent@example.com", password="pw", auth_token="old"), cfg_path)
    a = agent_module.DesktopSyncAgent(config_path=cfg_path)
    backend.api_responses = [unauthorized("admin_revoke")]
    a.sync_outbound_cycle()
    assert a.get_status()["status"] == "SIGNED OUT"
    assert json.load(open(cfg_path))["auth_halt_reason"] == "admin_revoke"

    # After a restart (autostart), the agent must not sign back in or sync
    b = agent_module.DesktopSyncAgent(config_path=cfg_path)
    b.tally.discover_tally_host = lambda: {"connected": False, "release": ""}
    b.tally.get_open_companies = lambda: []
    calls = len(backend.requests)
    b.discover_and_report()
    assert backend.logins == 0
    assert b.sync_outbound_cycle() == 0
    b.active_company_name = "Alpha"
    b.sync_inbound_cycle(is_incremental=True)
    assert [p for _, p, _ in backend.requests[calls:] if not p.startswith("/health") and p != "/"] == []
    assert "administrator" in b.get_status()["auth_halt_message"]

    # Re-entering credentials (GUI Settings) clears it
    b.config.auth_halt_reason = ""
    save_config(b.config, cfg_path)
    c = agent_module.DesktopSyncAgent(config_path=cfg_path)
    assert c.cloud.auth_halt_reason == "" and c.cloud.authenticate("agent@example.com", "pw")[0]


def test_a_busy_server_is_told_apart_from_a_failed_push(backend):
    c = client(backend, token="t")
    backend.api_responses = [(409, {"detail": "A sync of this company is already running on the server."},
                              {"X-Sync-Reason": "sync_in_progress"})]

    ok, result = c.push_inbound_xml("<ENVELOPE/>", "Alpha")

    assert not ok and result["reason"] == "sync_in_progress" and result["status_code"] == 409
    assert len(backend.requests) == 1                                    # not sent again to the fallback address
