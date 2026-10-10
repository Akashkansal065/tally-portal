"""A failed inbound collection is re-pulled later instead of falling behind the server's AlterID watermark."""
import json

import agent as agent_module


class FakeTally:
    def __init__(self, records):
        self.records = records
        self.fail_export = set()
        self.last_export_failures = []

    def check_health(self):
        return True, "ok"

    def get_open_companies(self):
        return [{"name": "Alpha", "guid": "guid-alpha"}]

    def export_full_collections(self, company, min_alter_id=0, min_voucher_alter_id=None):
        self.last_export_failures = []
        out = []
        for label, ids in self.records.items():
            if label in self.fail_export:
                self.last_export_failures.append(label)
                continue
            chosen = [i for i in ids if i > min_alter_id]
            if chosen:
                out.append((label, json.dumps({"label": label, "ids": chosen})))
        return out


class FakeCloud:
    """Server whose watermark is the highest AlterID it holds, like /sync/last-alter-id."""
    auth_halt_reason = ""
    company_guid = ""

    def report_state(self, reports):
        self.reports = reports
        return True

    def __init__(self, have):
        self.have = set(have)
        self.reject = set()
        self.status_error = set()
        self.record_errors = {}

    def get_last_alter_id(self):
        m = max(self.have, default=0)
        return m, m

    def push_inbound_xml(self, xml, company_name=None, force=False):
        d = json.loads(xml)
        label = d["label"]
        if label in self.reject:
            return False, {"error_type": "HTTP_500", "error": "boom", "status_code": 500}
        if label in self.status_error:
            from cloud_client import _inbound_result
            return _inbound_result({"status": "error", "message": "Company not found"}, 200, "/sync/inbound")
        bad = set(self.record_errors.get(label, []))
        self.have.update(i for i in d["ids"] if i not in bad)
        return True, {"status": "success", "errors": [f"#{i} invalid" for i in d["ids"] if i in bad]}


def make_agent(cfg_path, tally, cloud):
    a = agent_module.DesktopSyncAgent(config_path=str(cfg_path))
    a.tally, a.cloud = tally, cloud
    a.active_company_name = "Alpha"
    a.tally_connected = True
    return a


LEDGERS_FAIL = {"Ledgers": list(range(101, 106)), "Vouchers": list(range(106, 111))}


def test_failed_push_is_repulled_next_cycle(tmp_path):
    cloud = FakeCloud(range(1, 101))
    a = make_agent(tmp_path / "c.json", FakeTally(LEDGERS_FAIL), cloud)
    cloud.reject = {"Ledgers"}
    a.sync_inbound_cycle(is_incremental=True)
    assert cloud.get_last_alter_id()[0] == 110          # watermark jumped past the failed ledgers
    cloud.reject = set()
    a.sync_inbound_cycle(is_incremental=True)
    assert {101, 102, 103, 104, 105} <= cloud.have


def test_retry_point_survives_restart_and_clears(tmp_path):
    cfg = tmp_path / "c.json"
    cloud = FakeCloud(range(1, 101))
    tally = FakeTally(LEDGERS_FAIL)
    cloud.reject = {"Ledgers"}
    make_agent(cfg, tally, cloud).sync_inbound_cycle(is_incremental=True)
    assert json.load(open(cfg))["inbound_retry_floors"] == {"guid-alpha": 100}
    cloud.reject = set()
    make_agent(cfg, tally, cloud).sync_inbound_cycle(is_incremental=True)
    assert {101, 102, 103, 104, 105} <= cloud.have
    assert json.load(open(cfg))["inbound_retry_floors"] == {}


def test_export_failure_and_status_error_also_hold_the_watermark(tmp_path):
    cloud = FakeCloud(range(1, 101))
    tally = FakeTally(LEDGERS_FAIL)
    a = make_agent(tmp_path / "c.json", tally, cloud)
    tally.fail_export = {"Ledgers"}
    a.sync_inbound_cycle(is_incremental=True)
    tally.fail_export = set()
    cloud.status_error = {"Ledgers"}
    a.sync_inbound_cycle(is_incremental=True)
    cloud.status_error = set()
    a.sync_inbound_cycle(is_incremental=True)
    assert {101, 102, 103, 104, 105} <= cloud.have


def test_single_rejected_record_does_not_pin_the_agent(tmp_path):
    cfg = tmp_path / "c.json"
    cloud = FakeCloud(range(1, 101))
    cloud.record_errors = {"Vouchers": [103]}
    make_agent(cfg, FakeTally({"Vouchers": list(range(101, 111))}), cloud).sync_inbound_cycle(is_incremental=True)
    assert not json.load(open(cfg)).get("inbound_retry_floors")
