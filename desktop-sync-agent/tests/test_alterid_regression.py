"""P0.2: Tally's AlterIDs can fall below the server's watermarks (a restore of an older backup, a repair). The
change probe is compared with those watermarks, and when a counter is lower the company gets a full sync."""
import agent as agent_module
from tally_client import TallyClient

GUID, NAME = "guid-sample", "Sample Co"


def probe_reply(mst, vch):
    return (f'<ENVELOPE><BODY><DATA><COLLECTION><COMPANY NAME="{NAME}"><GUID>{GUID}</GUID>'
            f"<ALTMSTID> {mst}</ALTMSTID><ALTVCHID> {vch}</ALTVCHID></COMPANY></COLLECTION></DATA></BODY></ENVELOPE>")


class Cloud:
    auth_halt_reason = ""
    company_fingerprint = "10001|20260401"

    def __init__(self, watermarks=(5, 5)):
        self.company_guid = GUID
        self.watermarks = watermarks
        self.pushes = []        # (force, scope)
        self.events = []

    def get_last_alter_id(self):
        return self.watermarks

    def push_inbound_xml(self, xml, company_name=None, force=False, scope=None):
        self.pushes.append((force, scope))
        return True, {"imported_vouchers": 1}

    def report_sync_event(self, kind, detail=None):
        self.events.append((kind, detail))
        return True

    def report_state(self, reports):
        return True

    def report_active_keys(self, payload):
        return True, {"results": []}

    def get_server_counts(self):
        return None


def make(tmp_path, mock_tally, watermarks=(5, 5)):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    a.tally, a.cloud = TallyClient(mock_tally.url, timeout=5), Cloud(watermarks)
    a.config.companies = [{"guid": GUID, "name": NAME}]
    a.config.company_guid, a.config.company_name = GUID, NAME
    a.active_company_guid, a.active_company_name = GUID, NAME
    a.tally_connected = True
    return a


def test_a_probe_below_the_server_watermark_starts_a_full_sync(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", probe_reply(100, 100))   # the restored copy
    a = make(tmp_path, mock_tally, watermarks=(500, 500))              # what the server learned before the restore
    a.sync_inbound_cycle(is_incremental=True)
    assert a.cloud.events and a.cloud.events[0][0] == "alterid_regression"
    detail = a.cloud.events[0][1]
    assert (detail["alt_vch_id"], detail["voucher_watermark"]) == (100, 500)
    assert a.cloud.pushes and all(force for force, _ in a.cloud.pushes)   # forced: lower AlterIDs must overwrite
    assert any(i.startswith("Export") for i in mock_tally.ids)
    assert "full" in (a.cloud.pushes[0][1] or "")                         # not an "alter>500" delta window


def test_only_one_side_below_its_watermark_is_enough(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", probe_reply(900, 100))
    a = make(tmp_path, mock_tally, watermarks=(500, 500))
    a.sync_inbound_cycle(is_incremental=True)
    assert [e[0] for e in a.cloud.events] == ["alterid_regression"]


def test_counters_at_or_above_the_watermarks_are_no_regression(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", probe_reply(500, 640))
    a = make(tmp_path, mock_tally, watermarks=(500, 500))
    a.sync_inbound_cycle(is_incremental=True)
    assert a.cloud.events == []
    assert a.cloud.pushes and not any(force for force, _ in a.cloud.pushes)   # an ordinary delta pass


def test_no_probe_reading_gives_no_verdict(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", "garbage")
    a = make(tmp_path, mock_tally, watermarks=(500, 500))
    a.sync_inbound_cycle(is_incremental=True)
    assert a.cloud.events == []


def test_the_regression_is_handled_once_not_every_cycle(tmp_path, mock_tally):
    """The server's watermark is the highest AlterID it stores, which can stay high after the full sync (rows
    Tally no longer has). The agent keeps its own ceiling so the same restore does not trigger a full sync forever."""
    mock_tally.respond("MyTallyChangeProbe", [probe_reply(100, 100), probe_reply(100, 100), probe_reply(100, 103)])
    a = make(tmp_path, mock_tally, watermarks=(500, 500))
    a.sync_inbound_cycle(is_incremental=True)
    assert len(a.cloud.events) == 1 and a.config.alter_ceilings == {GUID: [100, 100]}
    pushes_after_full = len(a.cloud.pushes)
    a.sync_inbound_cycle(is_incremental=True)           # server still says 500, Tally says 100: nothing new
    assert len(a.cloud.events) == 1
    a.sync_inbound_cycle(is_incremental=True)           # two vouchers keyed: pulled from the ceiling, not from 500
    assert len(a.cloud.events) == 1
    delta = [body for rid, body in mock_tally.requests if rid == "ExportVouchers"][-1]
    assert "100" in delta and "500" not in delta
    assert len(a.cloud.pushes) > pushes_after_full
    assert a.config.alter_ceilings == {GUID: [100, 103]}


def test_the_ceiling_goes_once_the_server_has_come_down(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", probe_reply(100, 100))
    a = make(tmp_path, mock_tally, watermarks=(500, 500))
    a.sync_inbound_cycle(is_incremental=True)
    a.cloud.watermarks = (90, 100)                      # the stale rows are gone
    a.sync_inbound_cycle(is_incremental=True)
    assert a.config.alter_ceilings == {}


def test_a_restore_that_finishes_asks_for_a_full_sync(tmp_path, mock_tally):
    a = make(tmp_path, mock_tally)
    a._on_restore(True)
    assert a.restoring and not a.force_full_sync_next
    a._on_restore(False)
    assert not a.restoring and a.force_full_sync_next and a.immediate_sync_requested
    a.sync_inbound_cycle(is_incremental=True)
    assert a.cloud.pushes and all(force for force, _ in a.cloud.pushes)
    assert not a.force_full_sync_next


def test_a_failed_full_sync_is_retried_forced_until_it_finishes(tmp_path, mock_tally):
    mock_tally.respond("MyTallyChangeProbe", probe_reply(100, 100))
    a = make(tmp_path, mock_tally, watermarks=(500, 500))
    mock_tally.respond("ExportVouchers", "not an envelope")            # the full sync fails on its vouchers
    a.sync_inbound_cycle(is_incremental=True)
    assert a.config.forced_full_syncs == [GUID]
    mock_tally.respond("ExportVouchers", mock_tally.EMPTY)
    a.cloud.pushes.clear()
    a.sync_inbound_cycle(is_incremental=True)                          # the regression is not detected again, but the sync is owed
    assert len(a.cloud.events) == 1
    assert a.cloud.pushes and all(force for force, _ in a.cloud.pushes)
    assert a.config.forced_full_syncs == []                            # done: later cycles are ordinary deltas
    a.cloud.pushes.clear()
    a.sync_inbound_cycle(is_incremental=True)
    assert not any(force for force, _ in a.cloud.pushes)
