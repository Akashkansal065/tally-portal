"""WS-12: guided Tally port detection. Nothing changes the configured URL until the person accepts."""
import agent as agent_module
import bridge_core
import tally_ports as tp
from tally_client import TallyClient

LINKED = "guid-linked"


def test_server_port_is_read_from_tally_ini():
    assert tp.read_server_port("[Tally]\r\nServerPort=9001\r\nOther=1") == 9001
    assert tp.read_server_port("serverport = 9010") == 9010
    for bad in ("", "ServerPort=", "ServerPort=abc", "ServerPort=99999999", "NoPortHere=1"):
        assert tp.read_server_port(bad) is None


def test_candidates_put_the_ini_port_first_and_skip_the_current_one():
    ports = tp.candidate_ports(9000, ["a.ini"], read_text=lambda p: "ServerPort=9003")
    assert ports[0] == 9003 and 9000 not in ports and ports.count(9003) == 1
    assert ports[1:] == [9001, 9002, 9004, 9005, 9999]


def test_an_offer_needs_a_port_that_answers_with_a_linked_company():
    answers = {"http://127.0.0.1:9001": [{"name": "Other Co", "guid": "guid-other"}],
               "http://127.0.0.1:9002": [{"name": "Alpha", "guid": LINKED}]}
    offer = tp.find_port_offer("http://127.0.0.1:9000", [LINKED], lambda url: answers.get(url, []), [])
    assert offer == {"url": "http://127.0.0.1:9002", "port": 9002, "company": "Alpha"}


def test_no_offer_when_nothing_linked_matches_or_probes_fail():
    assert tp.find_port_offer("http://127.0.0.1:9000", [LINKED], lambda url: [{"name": "X", "guid": "guid-x"}], []) is None
    assert tp.find_port_offer("http://127.0.0.1:9000", [], lambda url: [{"name": "A", "guid": LINKED}], []) is None

    def boom(url):
        raise OSError("refused")
    assert tp.find_port_offer("http://127.0.0.1:9000", [LINKED], boom, []) is None


def test_running_or_not_only_words_the_message():
    assert tp.tally_is_running(lambda: "tally.exe    1234 Console  1   250,000 K") is True
    assert tp.tally_is_running(lambda: "INFO: No tasks are running which match the specified criteria.") is False

    def broken():
        raise OSError
    assert tp.tally_is_running(broken) is None
    assert "isn't running" in tp.diagnosis_text("http://127.0.0.1:9000", False)
    assert "port 9000" in tp.diagnosis_text("http://127.0.0.1:9000", True) and "Connectivity" in tp.diagnosis_text("http://127.0.0.1:9000", True)


def make_agent(tmp_path, monkeypatch, offer=None):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.config.tally_url = "http://127.0.0.1:9000"
    a.config.companies = [{"guid": LINKED, "name": "Alpha"}]
    monkeypatch.setattr(tp, "tally_is_running", lambda runner=None: True)
    monkeypatch.setattr(tp, "find_port_offer", lambda *a, **k: offer)
    return a


def test_the_url_is_not_changed_until_the_offer_is_accepted(tmp_path, monkeypatch):
    offer = {"url": "http://127.0.0.1:9002", "port": 9002, "company": "Alpha"}
    a = make_agent(tmp_path, monkeypatch, offer)
    a.config.auto_switch_tally_port = False
    a._diagnose_tally()
    assert a.tally_port_offer == offer and a.config.tally_url == "http://127.0.0.1:9000"
    status = a.get_status()
    assert status["tally_port_offer"] == offer and "running" in status["tally_diagnosis"]
    status.update({"status": "TALLY OFFLINE"})
    health = bridge_core.health_from_status(status)
    assert health["action"] == "use_port" and "9002" in health["title"]
    assert a.config.tally_url == "http://127.0.0.1:9000"


def test_accepting_switches_the_url_after_checking_it_still_answers(tmp_path, monkeypatch):
    offer = {"url": "http://127.0.0.1:9002", "port": 9002, "company": "Alpha"}
    a = make_agent(tmp_path, monkeypatch, offer)
    a.config.auto_switch_tally_port = False
    a._diagnose_tally()
    monkeypatch.setattr(agent_module, "save_config", lambda *args, **kw: None)
    monkeypatch.setattr(agent_module.TallyClient, "check_health", lambda self: (False, "down"))
    ok, _ = a.use_offered_tally_port()
    assert ok is False and a.config.tally_url == "http://127.0.0.1:9000" and a.tally_port_offer is None
    a.tally_port_offer = offer
    monkeypatch.setattr(agent_module.TallyClient, "check_health", lambda self: (True, "ok"))
    ok, _ = a.use_offered_tally_port()
    assert ok is True and a.config.tally_url == "http://127.0.0.1:9002" and a.tally_port_offer is None


def test_without_an_offer_the_health_bar_uses_the_diagnosis(tmp_path, monkeypatch):
    a = make_agent(tmp_path, monkeypatch, None)
    a._diagnose_tally()
    status = a.get_status()
    status.update({"status": "TALLY OFFLINE"})
    health = bridge_core.health_from_status(status)
    assert health["action"] == "retry" and "Connectivity" in health["detail"]


def test_the_port_is_switched_on_its_own_when_it_names_a_linked_company(tmp_path, monkeypatch):
    offer = {"url": "http://127.0.0.1:9002", "port": 9002, "company": "Alpha"}
    a = make_agent(tmp_path, monkeypatch, offer)
    monkeypatch.setattr(agent_module, "save_config", lambda *args, **kw: None)
    monkeypatch.setattr(agent_module.TallyClient, "check_health", lambda self: (True, "ok"))
    a._diagnose_tally()
    assert a.config.tally_url == "http://127.0.0.1:9002" and a.tally_port_offer is None and a.tally_connected is True


def test_it_stays_on_the_old_port_when_the_new_one_stops_answering(tmp_path, monkeypatch):
    offer = {"url": "http://127.0.0.1:9002", "port": 9002, "company": "Alpha"}
    a = make_agent(tmp_path, monkeypatch, offer)
    monkeypatch.setattr(agent_module, "save_config", lambda *args, **kw: None)
    monkeypatch.setattr(agent_module.TallyClient, "check_health", lambda self: (False, "down"))
    a._diagnose_tally()
    assert a.config.tally_url == "http://127.0.0.1:9000"


def test_find_tally_installation_from_hint(tmp_path):
    tally_exe = tmp_path / "tally.exe"
    tally_exe.write_text("binary")
    tally_ini = tmp_path / "tally.ini"
    tally_ini.write_text("[Tally]\nServerPort=9005")

    info = tp.find_tally_installation(hint=str(tally_exe))
    assert info["exe_path"] == str(tally_exe)
    assert info["install_dir"] == str(tmp_path)
    assert info["ini_path"] == str(tally_ini)


def test_find_tally_listening_ports_parses_output():
    netstat_sample = """
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       900
  TCP    127.0.0.1:9003         0.0.0.0:0              LISTENING       1234
  TCP    0.0.0.0:9004           0.0.0.0:0              LISTENING       1234
    """
    ports = tp.find_tally_listening_ports(runner=lambda: netstat_sample, target_pids=["1234"])
    assert 9003 in ports and 9004 in ports
    assert 135 not in ports


def test_launch_tally(tmp_path, monkeypatch):
    tp.forget_installation_cache()
    tally_exe = tmp_path / "tally.exe"
    tally_exe.write_text("binary")

    launched = []
    monkeypatch.setattr(tp.subprocess, "Popen", lambda args, **kw: launched.append(args))
    monkeypatch.setattr(tp, "tally_is_running", lambda: False)
    monkeypatch.setattr(tp, "is_tally_starting", lambda: False)

    ok, msg = tp.launch_tally(exe_path=str(tally_exe))
    assert ok is True and str(tally_exe) in msg
    assert len(launched) == 1 and launched[0] == [str(tally_exe)]

    # Missing file
    monkeypatch.setattr(tp, "is_tally_starting", lambda: False)
    ok, msg = tp.launch_tally(exe_path=str(tmp_path / "nonexistent.exe"))
    assert ok is False and "Could not find tally.exe" in msg


def test_launch_tally_repeat_protection(tmp_path, monkeypatch):
    tp.forget_installation_cache()
    tally_exe = tmp_path / "tally.exe"
    tally_exe.write_text("binary")

    # 1. Reject if already running
    monkeypatch.setattr(tp, "tally_is_running", lambda: True)
    monkeypatch.setattr(tp, "is_tally_starting", lambda: False)
    ok, msg = tp.launch_tally(exe_path=str(tally_exe))
    assert ok is False and "already running" in msg

    # 2. Reject if currently starting up
    monkeypatch.setattr(tp, "tally_is_running", lambda: False)
    monkeypatch.setattr(tp, "is_tally_starting", lambda: True)
    ok, msg = tp.launch_tally(exe_path=str(tally_exe))
    assert ok is False and "starting up" in msg

    # 3. Reject if running status is unknown (None)
    monkeypatch.setattr(tp, "tally_is_running", lambda: None)
    monkeypatch.setattr(tp, "is_tally_starting", lambda: False)
    ok, msg = tp.launch_tally(exe_path=str(tally_exe))
    assert ok is False and "Could not determine" in msg


def test_find_tally_installation_caching(tmp_path, monkeypatch):
    tp.forget_installation_cache()
    # When not found, do not cache
    empty_info = tp.find_tally_installation(hint="", use_cache=True, is_running=False)
    if not empty_info["exe_path"]:
        assert tp._cached_installation is None

    tally_exe = tmp_path / "tally.exe"
    tally_exe.write_text("binary")

    call_count = [0]
    def fake_running():
        call_count[0] += 1
        return False

    monkeypatch.setattr(tp, "tally_is_running", fake_running)
    info1 = tp.find_tally_installation(hint=str(tally_exe), use_cache=True)
    assert info1["exe_path"] == str(tally_exe)
    first_calls = call_count[0]

    # Second call should use cache and only call tally_is_running if is_running not supplied
    info2 = tp.find_tally_installation(hint=str(tally_exe), use_cache=True, is_running=False)
    assert info2["exe_path"] == str(tally_exe)
    # call_count should not increase because is_running was provided
    assert call_count[0] == first_calls
    tp.forget_installation_cache()


def test_auto_detect_tally_server_discovers_company_and_port(tmp_path, monkeypatch):
    tp.forget_installation_cache()
    tally_exe = tmp_path / "tally.exe"
    tally_exe.write_text("binary")
    tally_ini = tmp_path / "tally.ini"
    tally_ini.write_text("[Tally]\nServerPort=9008")

    monkeypatch.setattr(tp, "find_tally_installation", lambda *a, **k: {
        "exe_path": str(tally_exe), "ini_path": str(tally_ini), "install_dir": str(tmp_path), "is_running": True
    })
    monkeypatch.setattr(tp, "find_tally_listening_ports", lambda: [9008])

    answers = {
        "http://127.0.0.1:9008": [{"name": "Acme Industries", "company_id": "10001", "guid": "acme-guid"}]
    }
    probe = lambda url: answers.get(url, [])
    found = tp.auto_detect_tally_server(probe=probe)
    assert found["connected"] is True
    assert found["port"] == 9008
    assert found["company_name"] == "Acme Industries"
    assert found["company_id"] == "10001"
    assert found["guid"] == "acme-guid"


def test_auto_detect_tally_server_ignores_disconnected_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(tp, "find_tally_installation", lambda *a, **k: {"exe_path": "", "ini_path": "", "install_dir": "", "is_running": False})
    monkeypatch.setattr(tp, "find_tally_listening_ports", lambda: [9000])

    # Probe returning explicitly disconnected result
    probe = lambda url: {"connected": False}
    found = tp.auto_detect_tally_server(probe=probe)
    assert found["connected"] is False


def test_detect_tally_returns_company_id_and_port(monkeypatch):
    fake_discovery = {
        "connected": True,
        "company_name": "Bharat Traders",
        "company_id": "10005",
        "guid": "bt-guid",
        "port": 9002,
        "url": "http://127.0.0.1:9002",
        "exe_path": "C:\\TallyPrime\\tally.exe",
    }
    monkeypatch.setattr(bridge_core.tally_ports, "auto_detect_tally_server", lambda *a, **k: fake_discovery)
    # Force direct url to fail so auto_detect is used
    monkeypatch.setattr(bridge_core.TallyClient, "discover_tally_host", lambda self: {"connected": False})

    res = bridge_core.detect_tally("http://127.0.0.1:9000")
    assert res["kind"] == "ok"
    assert res["company"] == "Bharat Traders"
    assert res["company_id"] == "10005"
    assert res["port"] == 9002
    assert "Bharat Traders" in res["text"]
    assert "10005" in res["text"]
    assert "9002" in res["text"]
    assert "Switched Tally address" in res["text"]


def test_test_connection_returns_tally_url(monkeypatch):
    fake_discovery = {
        "connected": True,
        "company_name": "Bharat Traders",
        "company_id": "10005",
        "guid": "bt-guid",
        "port": 9002,
        "url": "http://127.0.0.1:9002",
    }
    monkeypatch.setattr(bridge_core.tally_ports, "auto_detect_tally_server", lambda *a, **k: fake_discovery)
    monkeypatch.setattr(bridge_core.TallyClient, "discover_tally_host", lambda self: {"connected": False})
    monkeypatch.setattr(bridge_core.CloudClient, "check_health", lambda self: (True, "OK"))

    res = bridge_core.test_connection(backend_url="http://cloud", email="", password="", tally_url="http://127.0.0.1:9000")
    assert res["tally_url"] == "http://127.0.0.1:9002"
    assert "connected on http://127.0.0.1:9002" in res["text"]
    assert res["kind"] == "ok"


def test_discover_tally_host_multi_company_isolation(monkeypatch):
    xml_with_two_companies = """<ENVELOPE>
      <BODY>
        <DATA>
          <COLLECTION>
            <COMPANY NAME="Company A">
              <CMPNAME>Company A</CMPNAME>
              <CMPNUMBER>10001</CMPNUMBER>
              <CMPGUID>guid-aaa</CMPGUID>
              <APPPATH>C:\\Tally\\</APPPATH>
              <NUMBER>99999</NUMBER>
              <GUID>unrelated-guid</GUID>
            </COMPANY>
            <COMPANY NAME="Company B">
              <CMPNAME>Company B</CMPNAME>
              <CMPNUMBER>10002</CMPNUMBER>
              <CMPGUID>guid-bbb</CMPGUID>
            </COMPANY>
          </COLLECTION>
        </DATA>
      </BODY>
    </ENVELOPE>"""

    class DummyResp:
        def read(self):
            return xml_with_two_companies.encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    client = TallyClient(tally_url="http://127.0.0.1:9000")
    monkeypatch.setattr(client, "_urlopen", lambda *a, **k: DummyResp())

    res = client.discover_tally_host()
    assert res["connected"] is True
    assert res["company_name"] == "Company A"
    assert res["company_id"] == "10001"
    assert res["guid"] == "guid-aaa"
    # Bare NUMBER / GUID tags and company B tags must NOT have overwritten Company A
    assert res["company_id"] != "99999"
    assert res["company_id"] != "10002"
    assert res["guid"] != "unrelated-guid"
    assert res["guid"] != "guid-bbb"


def test_match_open_company():
    cmps = [
        {"name": "Company A", "guid": "guid-a"},
        {"name": "Company B", "guid": "guid-b"},
    ]
    assert tp.match_open_company(cmps, {"guid": "guid-b"})["name"] == "Company B"
    assert tp.match_open_company(cmps, {"company_name": "Company B"})["guid"] == "guid-b"
    assert tp.match_open_company(cmps, {"guid": "guid-c"})["name"] == "Company A"
    assert tp.match_open_company([], {"guid": "guid-a"}) == {}


def test_auto_detect_tally_server_unknown_running_cannot_launch(monkeypatch):
    monkeypatch.setattr(tp, "find_tally_installation", lambda *a, **k: {
        "exe_path": "C:\\Tally\\tally.exe", "ini_path": "", "install_dir": "", "is_running": None
    })
    monkeypatch.setattr(tp, "find_tally_listening_ports", lambda: [])
    found = tp.auto_detect_tally_server(probe=lambda url: {"connected": False})
    assert found["connected"] is False
    assert found["can_launch"] is False


