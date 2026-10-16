"""WS-3 agent side: the list of active Tally keys goes to MyTally only when the export is whole and the open
company is the bound copy. Uses the real TallyClient against the mock Tally."""
import agent as agent_module
from tally_client import TallyClient

GUID, FINGERPRINT = "guid-sample", "10001|20260401"


class Cloud:
    auth_halt_reason = ""

    def __init__(self, accept=True):
        self.company_guid, self.company_fingerprint = GUID, FINGERPRINT
        self.sent, self.accept = [], accept

    def report_active_keys(self, payload):
        self.sent.append(payload)
        return self.accept, {"results": [{"deleted": 0}]}


def make_agent(tmp_path, mock_tally, cloud):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.tally, a.cloud = TallyClient(mock_tally.url, timeout=5), cloud
    a.active_company_guid, a.active_company_name = GUID, "Sample Co"
    a.config.full_sync_cursors = {}
    return a


def test_a_whole_export_is_sent_with_its_keys(tmp_path, mock_tally):
    cloud = Cloud()
    agent = make_agent(tmp_path, mock_tally, cloud)

    agent._maybe_report_active_keys(GUID, after_full_sync=True)

    (payload,) = cloud.sent
    assert payload["complete"] is True and payload["voucher_count_expected"] == 3
    assert [v["master_id"] for v in payload["vouchers"]] == ["101", "102", "103"]
    assert payload["vouchers"][0]["guid"] == "sample-guid-101" and payload["vouchers"][0]["alter_id"] == "5"
    assert payload["ledgers"][0] == {"name": "Sample Customer & Sons", "guid": "sample-led-1", "master_id": "11"}
    assert "stock_items" not in payload           # Tally gave no stock items: that type is left out, not sent empty
    assert len(payload["list_id"]) >= 8


def test_a_partial_export_is_never_sent(tmp_path, mock_tally):
    # the keys export has 3 vouchers but the index counted 4: something was cut off
    index = "<ENVELOPE><DATA><COLLECTION>" + "".join(
        f"<VOUCHER><DATE>2026030{n}</DATE></VOUCHER>" for n in range(1, 5)) + "</COLLECTION></DATA></ENVELOPE>"
    mock_tally.respond("MyTallyVoucherIndex", index)
    cloud = Cloud()
    make_agent(tmp_path, mock_tally, cloud)._maybe_report_active_keys(GUID, after_full_sync=True)
    assert cloud.sent == []


def test_a_failed_export_is_never_sent(tmp_path, mock_tally):
    mock_tally.respond("MyTallyVoucherKeys", "not an envelope")
    cloud = Cloud()
    make_agent(tmp_path, mock_tally, cloud)._maybe_report_active_keys(GUID, after_full_sync=True)
    assert cloud.sent == []


def test_vouchers_without_a_master_id_make_the_list_unusable(tmp_path, mock_tally):
    mock_tally.respond("MyTallyVoucherKeys", "<ENVELOPE><VOUCHER><DATE>20260301</DATE><GUID>g</GUID></VOUCHER></ENVELOPE>")
    mock_tally.respond("MyTallyVoucherIndex", "<ENVELOPE><VOUCHER><DATE>20260301</DATE></VOUCHER></ENVELOPE>")
    cloud = Cloud()
    make_agent(tmp_path, mock_tally, cloud)._maybe_report_active_keys(GUID, after_full_sync=True)
    assert cloud.sent == []


def test_a_copied_company_is_not_listed(tmp_path, mock_tally):
    cloud = Cloud()
    cloud.company_fingerprint = "10001|20250401"        # the bound copy's books begin elsewhere
    make_agent(tmp_path, mock_tally, cloud)._maybe_report_active_keys(GUID, after_full_sync=True)
    assert cloud.sent == [] and "MyTallyVoucherKeys" not in mock_tally.ids


def test_the_company_closing_mid_export_drops_the_list(tmp_path, mock_tally):
    mock_tally.respond("AllOpenCompanies", [mock_tally.fixture("AllOpenCompanies"), mock_tally.EMPTY])
    cloud = Cloud()
    make_agent(tmp_path, mock_tally, cloud)._maybe_report_active_keys(GUID, after_full_sync=True)
    assert cloud.sent == []


def test_cadence_after_a_send_waits_for_the_interval_but_a_full_sync_goes_at_once(tmp_path, mock_tally):
    cloud = Cloud()
    agent = make_agent(tmp_path, mock_tally, cloud)
    agent._maybe_report_active_keys(GUID, after_full_sync=False)     # never sent yet: due
    agent._maybe_report_active_keys(GUID, after_full_sync=False)     # just sent: not due
    assert len(cloud.sent) == 1
    agent._maybe_report_active_keys(GUID, after_full_sync=True)      # after a full sync: at once
    assert len(cloud.sent) == 2 and cloud.sent[0]["list_id"] != cloud.sent[1]["list_id"]


def test_nothing_is_sent_while_a_full_sync_is_under_way(tmp_path, mock_tally):
    cloud = Cloud()
    agent = make_agent(tmp_path, mock_tally, cloud)
    agent.config.full_sync_cursors = {GUID: {"ranges": [["20260301", "20260301", 1]], "next": 0}}
    agent._maybe_report_active_keys(GUID, after_full_sync=True)
    assert cloud.sent == []


def test_a_refused_list_is_tried_again_next_time(tmp_path, mock_tally):
    cloud = Cloud(accept=False)
    agent = make_agent(tmp_path, mock_tally, cloud)
    agent._maybe_report_active_keys(GUID, after_full_sync=False)
    agent._maybe_report_active_keys(GUID, after_full_sync=False)
    assert len(cloud.sent) == 2
