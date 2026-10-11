"""The health line's dots follow Tally and the server while the agent runs (they were measured once at start), a
company the server has linked to this PC is synced even if the sign-in stopped before saving it here, and the
window's Settings never overwrite what the agent saved."""
import agent as agent_module
import bridge_core as core
import webview_app

ALPHA = {"guid": "guid-alpha", "name": "Bhrama Enterprises", "starting_from": "20250401", "fingerprint": "1|20250401"}


class Tally:
    def __init__(self, up=True):
        self.up = up

    def check_health(self):
        return self.up, "ok" if self.up else "Unreachable"

    def get_open_companies(self):
        return [dict(ALPHA)] if self.up else []


class Cloud:
    device_mode = True
    auth_halt_reason = ""
    company_guid = ""
    company_fingerprint = ""

    def __init__(self, up=True, companies=None):
        self.up, self.listed = up, 0
        self.companies = companies if companies is not None else []

    def check_health(self):
        return (True, "Connected (200)") if self.up else (False, "Unreachable at http://192.168.1.39:8000")

    def list_companies(self):
        self.listed += 1
        return self.up, (self.companies if self.up else "offline")


def make_agent(tmp_path, tally, cloud):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.tally, a.cloud = tally, cloud
    a.config.companies, a.config.company_guid = [], ""
    a.active_company_guid = ""
    return a


def test_the_dots_follow_tally_and_the_server_after_start(tmp_path):
    tally, cloud = Tally(up=False), Cloud(up=False)
    a = make_agent(tmp_path, tally, cloud)
    a.refresh_connections(force=True)
    assert (a.tally_connected, a.cloud_connected) == (False, False)

    tally.up, cloud.up = True, True                       # Tally opened, the server finished restarting
    a.refresh_connections()                               # checked a moment ago: not asked again yet
    assert (a.tally_connected, a.cloud_connected) == (False, False)
    a._connections_checked -= a.CONNECTION_CHECK_SECONDS
    a.refresh_connections()
    assert (a.tally_connected, a.cloud_connected) == (True, True)
    assert a.cloud_message == "Connected (200)"


def test_retry_checks_at_once(tmp_path):
    tally, cloud = Tally(up=False), Cloud(up=True)
    a = make_agent(tmp_path, tally, cloud)
    a.refresh_connections(force=True)
    tally.up = True

    a.refresh_connections(force=True)                     # what pressing Retry does on the next turn of the loop

    assert a.tally_connected is True


def test_a_company_the_server_links_to_this_pc_is_synced_here(tmp_path):
    cloud = Cloud(companies=[
        {"company_id": 1, "name": "Bhrama Enterprises", "tally_guid": "guid-alpha", "linked_here": True},
        {"company_id": 2, "name": "Other PC's company", "tally_guid": "guid-other", "linked_here": False},
        {"company_id": 3, "name": "Never linked", "tally_guid": None, "linked_here": False},
    ])
    a = make_agent(tmp_path, Tally(), cloud)

    assert a.adopt_server_links() == 1
    assert a.adopt_server_links() == 0                    # asking again adds nothing twice
    assert a.config.companies == [{"guid": "guid-alpha", "name": "Bhrama Enterprises"}]
    assert (a.config.company_guid, a.active_company_name) == ("guid-alpha", "Bhrama Enterprises")
    assert agent_module.load_config(a.config_path).companies == [{"guid": "guid-alpha", "name": "Bhrama Enterprises"}]

    overview = core.companies_overview(a)
    assert [r["name"] for r in overview["linked"]] == ["Bhrama Enterprises"] and overview["unlinked"] == []


def test_an_unreachable_server_changes_no_links(tmp_path):
    a = make_agent(tmp_path, Tally(), Cloud(up=False))
    a.config.companies = [{"guid": "guid-alpha", "name": "Bhrama Enterprises"}]
    assert a.adopt_server_links() == 0 and a.config.companies == [{"guid": "guid-alpha", "name": "Bhrama Enterprises"}]


def test_saving_settings_keeps_a_company_the_agent_linked(tmp_path, monkeypatch):
    """The window used to keep its own copy of the config; Save wrote that copy, without the link."""
    monkeypatch.setattr(core, "install_startup", lambda *a, **k: None)
    monkeypatch.setattr(core, "uninstall_startup", lambda *a, **k: None)
    session = webview_app.Session(config_file=str(tmp_path / "agent_config.json"))
    session.agent.config.companies = [{"guid": "guid-alpha", "name": "Bhrama Enterprises"}]   # linked by the agent

    ok, _ = core.apply_settings(session, {"tally_host": "localhost", "tally_port": "9000", "backend_url": "http://192.168.1.39:8000",
                                          "outbound_seconds": "5", "inbound_seconds": "60", "vouchers_per_range": "50"})

    assert ok and session.config is session.agent.config
    assert agent_module.load_config(session.config_file).companies == [{"guid": "guid-alpha", "name": "Bhrama Enterprises"}]
