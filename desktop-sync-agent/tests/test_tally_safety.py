"""Requests to Tally take turns, only a timed-out Create is looked up before it's resent, and the agent follows
its company by GUID."""
import urllib.request

import agent as agent_module
import tally_client
from tally_client import NETWORK_ERROR_PREFIX, TallyClient

VOUCHER_XML = ('<ENVELOPE><STATICVARIABLES><SVCURRENTCOMPANY>Alpha</SVCURRENTCOMPANY></STATICVARIABLES>'
               '<VOUCHER REMOTEID="MYTALLY-VCH-7" ACTION="Create"><DATE>20261006</DATE></VOUCHER></ENVELOPE>')
TIMED_OUT = (False, f"{NETWORK_ERROR_PREFIX}: timed out")
REJECTED = (False, "Tally reported 1 error(s), 0 exception(s)")


def test_lock_is_held_until_the_response_is_read(monkeypatch):
    held_while_reading = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            held_while_reading.append(tally_client._TALLY_LOCK.locked())
            return b"<ENVELOPE></ENVELOPE>"

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResponse())
    ok, _ = TallyClient().check_health()
    assert ok and held_while_reading == [True]
    assert not tally_client._TALLY_LOCK.locked()


class OutboundTally:
    def __init__(self, reply, found=None, open_companies=None):
        self.reply, self.found = reply, found
        self.open_companies = open_companies or [{"name": "Alpha", "guid": "guid-alpha"}]
        self.lookups = []

    def get_open_companies(self):
        return self.open_companies

    def send_xml(self, xml):
        return self.reply

    def find_voucher_by_remote_id(self, company, remote_id, date_yyyymmdd=None):
        self.lookups.append((remote_id, date_yyyymmdd))
        return self.found


class OutboundCloud:
    auth_halt_reason = ""
    company_guid = ""

    def report_state(self, reports):
        self.reports = reports
        return True

    def __init__(self, action="Create"):
        self.task = {"sync_id": 1, "record_type": "Voucher", "record_id": 7, "action": action, "xml_payload": VOUCHER_XML}
        self.fetches, self.acked = 0, []

    def fetch_outbound_queue(self):
        self.fetches += 1
        return [self.task], None

    def acknowledge_queue(self, ids):
        self.acked.extend(ids)
        return True


def make_agent(tmp_path, tally, cloud):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.tally, a.cloud = tally, cloud
    a.active_company_name = "Alpha"
    return a


def test_timed_out_create_found_in_tally_is_acknowledged(tmp_path):
    tally, cloud = OutboundTally(TIMED_OUT, found={"guid": "g-1"}), OutboundCloud()
    assert make_agent(tmp_path, tally, cloud).sync_outbound_cycle() == 1
    assert cloud.acked == [1]
    assert tally.lookups == [("MYTALLY-VCH-7", "20261006")]  # looked up on the voucher's own date


def test_timed_out_create_not_in_tally_is_left_to_resend(tmp_path):
    tally, cloud = OutboundTally(TIMED_OUT, found=None), OutboundCloud()
    assert make_agent(tmp_path, tally, cloud).sync_outbound_cycle() == 0
    assert cloud.acked == []


def test_rejected_create_is_not_looked_up(tmp_path):
    # Tally answered and refused it: an older copy with the same REMOTEID proves nothing
    tally, cloud = OutboundTally(REJECTED, found={"guid": "g-1"}), OutboundCloud()
    make_agent(tmp_path, tally, cloud).sync_outbound_cycle()
    assert tally.lookups == [] and cloud.acked == []


def test_failed_delete_alter_or_cancel_is_never_acknowledged(tmp_path):
    # The voucher exists in Tally whether or not these went through, so finding it proves nothing
    for action in ("Delete", "Alter", "Cancel"):
        tally, cloud = OutboundTally(TIMED_OUT, found={"guid": "g-1"}), OutboundCloud(action)
        make_agent(tmp_path, tally, cloud).sync_outbound_cycle()
        assert tally.lookups == [] and cloud.acked == [], action


def test_pinned_company_pauses_when_only_another_company_is_open(tmp_path):
    # Same name, different GUID: a restored copy or another company, not the one being synced
    tally = OutboundTally(TIMED_OUT, open_companies=[{"name": "Alpha", "guid": "guid-other"}])
    cloud = OutboundCloud()
    a = make_agent(tmp_path, tally, cloud)
    a.active_company_guid = "guid-alpha"
    assert a.sync_outbound_cycle() == 0
    assert a.company_paused and cloud.fetches == 0


def test_choosing_another_company_drops_the_old_pin(tmp_path):
    a = make_agent(tmp_path, OutboundTally(TIMED_OUT), OutboundCloud())
    a.active_company_guid, a.company_paused = "guid-alpha", True
    a.config.company_name, a.config.company_guid = "Beta", ""   # what the GUI's Save does for a new company
    a.reload_config(a.config)
    assert (a.active_company_name, a.active_company_guid, a.company_paused) == ("Beta", "", False)
