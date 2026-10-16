"""WS-7: one cheap request says whether Tally changed; any doubt runs the normal cycle."""
import time

import agent as agent_module
from tally_client import TallyClient, parse_change_counters

GUID, NAME = "guid-sample", "Sample Co"


def probe_reply(mst, vch, guid=GUID):
    return (f'<ENVELOPE><BODY><DATA><COLLECTION><COMPANY NAME="{NAME}"><GUID>{guid}</GUID>'
            f"<ALTMSTID> {mst}</ALTMSTID><ALTVCHID> {vch}</ALTVCHID></COMPANY></COLLECTION></DATA></BODY></ENVELOPE>")


class Cloud:
    auth_halt_reason = ""
    company_fingerprint = "10001|20260401"

    def __init__(self):
        self.company_guid = GUID
        self.pushed = []

    def get_last_alter_id(self):
        return (5, 5)

    def push_inbound_xml(self, xml, company_name=None, force=False, scope=None):
        self.pushed.append(xml)
        return True, {"imported_vouchers": 1}

    def report_state(self, reports):
        return True

    def report_active_keys(self, payload):
        return True, {"results": []}

    def get_server_counts(self):
        return None


def make(tmp_path, mock_tally):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.tally, a.cloud = TallyClient(mock_tally.url, timeout=5), Cloud()
    a.config.companies = [{"guid": GUID, "name": NAME}]
    a.config.company_guid, a.config.company_name = GUID, NAME
    a.active_company_guid, a.active_company_name = GUID, NAME
    a.tally_connected = True
    return a


def test_counters_are_read_for_exactly_one_company():
    assert parse_change_counters(probe_reply(7, 9), NAME, GUID) == (7, 9)
    two = probe_reply(1, 2).replace("</COLLECTION>", probe_reply(3, 4).split("<COLLECTION>")[1].split("</COLLECTION>")[0] + "</COLLECTION>")
    assert parse_change_counters(two, NAME) is None                      # same name twice: cannot tell
    assert parse_change_counters(probe_reply(1, 2, guid="other"), NAME, GUID) is None
    assert parse_change_counters(probe_reply("x", 2), NAME, GUID) is None   # not a number
    assert parse_change_counters(probe_reply(1, 2).replace("<ALTVCHID> 2</ALTVCHID>", ""), NAME, GUID) is None
    assert parse_change_counters(None, NAME, GUID) is None and parse_change_counters("<ENVELOPE/>", NAME, GUID) is None


def test_an_idle_company_costs_one_request(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", probe_reply(5, 5))
    a = make(tmp_path, mock_tally)
    a.sync_inbound_cycle(is_incremental=True)          # first sight: the normal pass
    first = len(mock_tally.requests)
    assert first > 1
    a.sync_inbound_cycle(is_incremental=True)          # unchanged: the probe and nothing else
    ids = [i for i, _ in mock_tally.requests[first:]]
    assert "MyTallyChangeProbe" in ids and not any(i.startswith("Export") for i in ids)
    assert a.last_sync_status.startswith("Up-to-date")


def test_only_the_side_that_rose_is_exported(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", [probe_reply(5, 5), probe_reply(5, 6)])
    a = make(tmp_path, mock_tally)
    a.sync_inbound_cycle(is_incremental=True)
    first = len(mock_tally.requests)
    a.sync_inbound_cycle(is_incremental=True)
    ids = [i for i, _ in mock_tally.requests[first:]]
    assert "ExportVouchers" in ids and "ExportLedgers" not in ids and "ExportGroups" not in ids


def test_a_failed_probe_runs_the_normal_cycle(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", [probe_reply(5, 5), "garbage"])
    a = make(tmp_path, mock_tally)
    a.sync_inbound_cycle(is_incremental=True)
    first = len(mock_tally.requests)
    a.sync_inbound_cycle(is_incremental=True)
    ids = [i for i, _ in mock_tally.requests[first:]]
    assert "ExportVouchers" in ids and "ExportLedgers" in ids


def test_the_safety_pass_runs_even_when_nothing_moved(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", probe_reply(5, 5))
    a = make(tmp_path, mock_tally)
    a.sync_inbound_cycle(is_incremental=True)
    mst, vch, _ = a._probe_seen[GUID]
    a._probe_seen[GUID] = (mst, vch, time.time() - agent_module.PROBE_SAFETY_PASS_SECONDS - 1)
    first = len(mock_tally.requests)
    a.sync_inbound_cycle(is_incremental=True)
    ids = [i for i, _ in mock_tally.requests[first:]]
    assert "ExportVouchers" in ids and "ExportLedgers" in ids


def test_a_failed_cycle_forgets_the_reading(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", probe_reply(5, 5))
    a = make(tmp_path, mock_tally)
    a.sync_inbound_cycle(is_incremental=True)
    assert GUID in a._probe_seen
    mock_tally.respond("ExportVouchers", "not an envelope")
    a._probe_seen[GUID] = (4, 4, time.time())          # counters moved, so the exports run, and one fails
    a.sync_inbound_cycle(is_incremental=True)
    assert GUID not in a._probe_seen
