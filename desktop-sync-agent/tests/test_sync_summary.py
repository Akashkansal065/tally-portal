"""The tiles show what the server holds, not a running sum of every sync, and a sync ends with a summary of
every kind of record."""
import json
import logging

from tests.test_inbound_watermark import FakeCloud, FakeTally, make_agent


class CountingCloud(FakeCloud):
    """Reports the counts a real import would, and holds 44 vouchers and 53 ledgers however often it is sent them."""

    def push_inbound_xml(self, xml, company_name=None, force=False):
        label = json.loads(xml)["label"]
        return True, {"status": "success", "errors": [],
                      **{"Ledgers": {"imported_ledgers": 53}, "CostCentres": {"imported_cost_centres": 5},
                         "Vouchers": {"imported_vouchers": 44}}[label]}

    def get_server_counts(self):
        return {"vouchers": 44, "ledgers": 53, "stock_items": 19}


RECORDS = {"Ledgers": [1], "CostCentres": [2], "Vouchers": [3]}


def test_tiles_show_the_servers_totals_after_repeated_syncs(tmp_path, caplog):
    a = make_agent(tmp_path / "c.json", FakeTally(RECORDS), CountingCloud([]))
    with caplog.at_level(logging.INFO, logger="MyTallySyncAgent"):
        a.sync_inbound_cycle(is_incremental=False)
        a.sync_inbound_cycle(is_incremental=False)          # the same records again

    status = a.get_status()
    assert (status["total_vouchers"], status["total_ledgers"], status["total_items"]) == (44, 53, 19)
    log = caplog.text
    assert "'CostCentres' Synced" in log and "Cost centres: 5" in log     # every kind is named, not four
    assert "Sync summary for 'Alpha'" in log and "Server now holds:  44 vouchers, 53 ledgers, 19 stock items" in log


def test_an_older_server_falls_back_to_what_was_sent(tmp_path):
    cloud = CountingCloud([])
    cloud.get_server_counts = lambda: None
    a = make_agent(tmp_path / "c.json", FakeTally(RECORDS), cloud)
    a.sync_inbound_cycle(is_incremental=False)
    assert a.get_status()["total_vouchers"] == 44
