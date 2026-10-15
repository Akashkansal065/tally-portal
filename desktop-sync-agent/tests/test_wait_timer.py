import time
import urllib.request
import pytest
from tally_client import TallyClient, TallyWaitTimer
import agent as agent_module
import bridge_core as core


def test_tally_wait_timer_ticks_and_stops():
    ticks = []

    def on_tick(label, elapsed, timeout, attempt, total_attempts, finished=False):
        ticks.append((label, int(elapsed), timeout, attempt, total_attempts, finished))

    timer = TallyWaitTimer("TestExport", timeout=10, attempt=1, total_attempts=2, callback=on_tick)
    timer.start()
    time.sleep(1.2)
    elapsed = timer.stop()

    assert elapsed >= 1.0
    # Must have had at least one in-progress tick and one final tick with finished=True
    assert any(t[0] == "TestExport" and t[5] is False for t in ticks)
    assert ticks[-1][5] is True


def test_tally_client_export_triggers_progress_callback(monkeypatch):
    events = []

    class FakeResponse:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def read(self):
            time.sleep(1.1)
            return b"<ENVELOPE><DATA></DATA></ENVELOPE>"

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResponse())

    client = TallyClient()
    client.on_wait_progress = lambda label, elapsed, timeout, attempt, total, finished=False: events.append(
        (label, int(elapsed), finished)
    )

    res = client._export("<ENVELOPE/>", "Vouchers 20250401-20250415 (1/40)", timeout=10)
    assert res is not None
    assert any(e[0].startswith("Vouchers") and e[2] is False for e in events)
    assert events[-1][2] is True


def test_agent_updates_sync_detail_and_health_presents_it(tmp_path):
    a = agent_module.DesktopSyncAgent(config_path=str(tmp_path / "c.json"))
    assert a.sync_detail == ""

    # Simulated tick during waiting
    a._on_tally_wait_progress("Vouchers 20250401–20250415 (5/40)", elapsed=14.2, timeout=120, attempt=1, total_attempts=3, finished=False)
    assert "Waiting for Tally ('Vouchers 20250401–20250415 (5/40)') · 14s (timeout 120s)" in a.sync_detail

    status = a.get_status()
    assert "Waiting for Tally" in status["sync_detail"]

    # When syncing, health_from_status uses sync_detail
    status["status"] = "SYNCING"
    health = core.health_from_status(status)
    assert "Waiting for Tally" in health["detail"]

    # Finished resets detail
    a._on_tally_wait_progress("Vouchers 20250401–20250415 (5/40)", elapsed=15.0, timeout=120, attempt=1, total_attempts=3, finished=True)
    assert a.sync_detail == ""
