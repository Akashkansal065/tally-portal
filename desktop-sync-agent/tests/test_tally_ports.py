"""WS-12: guided Tally port detection. Nothing changes the configured URL until the person accepts."""
import agent as agent_module
import bridge_core
import tally_ports as tp

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
