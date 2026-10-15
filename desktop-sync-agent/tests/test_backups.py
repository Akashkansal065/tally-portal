"""Backups made by the agent: whole or not at all, kept by the same rule as the server, uploaded in chunks that
carry on after a dropped connection, and restores that write nothing unless every safeguard holds."""
import hashlib
import json
import math
import zipfile
from datetime import datetime, timedelta

import pytest

import backups as B

COMPANY = {"guid": "guid-alpha", "name": "Alpha & Co", "state": "open", "fingerprint": "1|20250401", "starting_from": "20250401"}
MASTERS = {
    "Group": '<GROUP NAME="Sundry Debtors" RESERVEDNAME="Sundry Debtors"><PARENT>Current Assets</PARENT></GROUP>'
             '<GROUP NAME="Current Assets" ACTION="Create"><PARENT/></GROUP>',
    "Ledger": '<LEDGER NAME="Cash" ACTION="Create"><PARENT>Cash-in-Hand</PARENT>'
              '<UDF:SALESMAN.LIST DESC="`Salesman`" ISLIST="YES" TYPE="String"><UDF:SALESMAN DESC="`Salesman`">Ravi</UDF:SALESMAN></UDF:SALESMAN.LIST>'
              '<BILLALLOCATIONS.LIST><NAME>Opening</NAME></BILLALLOCATIONS.LIST></LEDGER>',
    "Unit": '<UNIT NAME="Nos"><ISSIMPLEUNIT>Yes</ISSIMPLEUNIT></UNIT>',
}


def envelope(body: str, cmpinfo: str = "") -> str:
    return f"<ENVELOPE><BODY><DATA><COLLECTION>{body}</COLLECTION></DATA></BODY>{cmpinfo}</ENVELOPE>"


def voucher(number: int, day: str) -> str:
    return (f'<VOUCHER REMOTEID="guid-v{number}" VCHTYPE="Sales" ACTION="Create"><DATE>{day}</DATE>'
            f"<VOUCHERNUMBER>{number}</VOUCHERNUMBER><ALLLEDGERENTRIES.LIST><BANKALLOCATIONS.LIST><DATE>19990101</DATE>"
            f"</BANKALLOCATIONS.LIST></ALLLEDGERENTRIES.LIST></VOUCHER>")


class FakeTally:
    """Masters by type, vouchers as (number, date). honours: which range requests it applies."""

    def __init__(self, vouchers, honours=("sv", "filter")):
        self.vouchers, self.honours = list(vouchers), honours
        self.masters = dict(MASTERS)
        self.silent = set()          # Tally types (or "Voucher") that get no answer
        self.drop_vouchers = 0       # leave this many vouchers out of every export
        self.imports = []            # envelopes received by import_batch
        self.import_reply = "<RESPONSE><CREATED>0</CREATED><ALTERED>{n}</ALTERED><ERRORS>0</ERRORS></RESPONSE>"
        self.answering = True

    def _voucher_request(self, company, label, fetch, date_from="20000101", date_to="20991231", filter_on_date=False):
        return json.dumps({"vouchers": True, "from": date_from, "to": date_to, "method": "filter" if filter_on_date else "sv",
                           "whole": date_from == "20000101" and date_to == "20991231"})

    def _export(self, request, label, timeout=120, retries=2):
        if request.startswith("{"):
            asked = json.loads(request)
            if "Voucher" in self.silent:
                return None
            chosen = self.vouchers if asked["whole"] or asked["method"] not in self.honours else \
                [(n, d) for n, d in self.vouchers if asked["from"] <= d <= asked["to"]]
            chosen = chosen[self.drop_vouchers:]
            return envelope("".join(voucher(n, d) for n, d in chosen), "<CMPINFO><VOUCHER>99</VOUCHER></CMPINFO>")
        tally_type = request.split("<TYPE>")[2].split("</TYPE>")[0]
        if tally_type in self.silent:
            return None
        return envelope(self.masters.get(tally_type, ""))

    def export_voucher_index(self, company):
        return [d for _, d in self.vouchers]

    def import_batch(self, env, timeout=120):
        if not self.answering:
            return False, "HTTP/Network Error: refused"
        self.imports.append(env)
        return True, self.import_reply.format(n=env.count("<TALLYMESSAGE"))


class FakeCloud:
    """The server's upload rules (backend/app/routers/backups.py): chunks in order, resume from next_chunk, kept
    only when the checksum matches."""

    def __init__(self):
        self.stored = {}             # key -> bytes
        self.uploads = {}            # key -> {"entry", "chunk", "data"}
        self.chunk_calls = []
        self.fail_chunk_once = None  # index whose first sending is lost
        self.down = False
        self.jobs = {"backups": [], "restores": []}
        self.failed, self.finished, self.started = [], [], []
        self.download_bytes = None

    def backup_jobs(self):
        return (not self.down), (self.jobs if not self.down else "offline")

    def backup_announce(self, entry, chunk_size):
        if self.down:
            return 0, "offline"
        if entry["key"] in self.stored:
            return 200, {"status": "stored", "next_chunk": math.ceil(entry["size"] / chunk_size)}
        up = self.uploads.setdefault(entry["key"], {"entry": entry, "chunk": chunk_size, "data": b""})
        return 200, {"status": "uploading", "next_chunk": self._next(up)}

    def backup_chunk(self, key, index, data):
        self.chunk_calls.append((key, index))
        if self.fail_chunk_once == index:
            self.fail_chunk_once = None
            return 0, "connection reset", {}
        up = self.uploads[key]
        following = self._next(up)
        if index > following:
            return 409, "send it first", {"x-next-chunk": str(following)}
        if index == following:
            up["data"] += data
        return 200, {"next_chunk": self._next(up)}, {}

    @staticmethod
    def _next(up):
        if len(up["data"]) >= up["entry"]["size"]:
            return math.ceil(up["entry"]["size"] / up["chunk"])
        return len(up["data"]) // up["chunk"]

    def backup_complete(self, key):
        up = self.uploads[key]
        if hashlib.sha256(up["data"]).hexdigest() != up["entry"]["sha256"]:
            up["data"] = b""
            return 422, "checksum", {"x-next-chunk": "0"}
        self.stored[key] = up["data"]
        return 200, {"status": "stored"}, {}

    def backup_failed(self, key, error):
        self.failed.append((key, error))
        return True

    def backup_download(self, key, dest):
        with open(dest, "wb") as f:
            f.write(self.download_bytes if self.download_bytes is not None else self.stored[key])
        return True, ""

    def restore_start(self, restore_id, pre_key):
        self.started.append((restore_id, pre_key))
        return 200, {"status": "running"}

    def restore_finish(self, restore_id, ok, summary, error):
        self.finished.append((restore_id, ok, summary, error))
        return True


def many_vouchers(n=120):
    return [(i, f"202504{(i % 28) + 1:02d}") for i in range(n)]


def scheduler(tmp_path, tally, cloud, companies=None, interval=60):
    return B.BackupScheduler(tally, B.LocalBackups(str(tmp_path)), companies=lambda: companies or [dict(COMPANY)],
                             cloud_for=lambda company: cloud, interval_minutes=interval)


# ── What a backup holds ──────────────────────────────────────────────────────

def test_a_backup_holds_every_master_and_every_voucher(tmp_path):
    tally = FakeTally(many_vouchers(120))

    entry = B.make_backup(tally, COMPANY, "hourly", "hourly-test-0001", str(tmp_path), per_range=50)

    path = tmp_path / "hourly-test-0001.zip"
    assert entry["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest() and entry["size"] == path.stat().st_size
    with zipfile.ZipFile(path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        vouchers = sum(len(B.object_blocks(zf.read(name).decode(), "VOUCHER")) for name in manifest["files"]["vouchers"])
        assert "<UDF:SALESMAN DESC" in zf.read("ledgers.xml").decode()           # kept exactly as Tally wrote it
    assert manifest["records"]["groups"] == 2 and manifest["records"]["ledgers"] == 1 and manifest["records"]["units"] == 1
    assert manifest["records"]["vouchers"] == vouchers == 120 and len(manifest["files"]["vouchers"]) > 1
    assert manifest["company"] == {"guid": "guid-alpha", "name": "Alpha & Co", "fingerprint": "1|20250401", "books_from": "20250401"}


def test_a_tally_that_ignores_date_ranges_gets_one_export(tmp_path):
    entry = B.make_backup(FakeTally(many_vouchers(120), honours=()), COMPANY, "hourly", "hourly-test-0002", str(tmp_path), per_range=50)

    with zipfile.ZipFile(tmp_path / "hourly-test-0002.zip") as zf:
        assert json.loads(zf.read("manifest.json"))["files"]["vouchers"] == ["vouchers_all.xml"]
    assert entry["records"]["vouchers"] == 120


@pytest.mark.parametrize("break_it, why", [
    (lambda t: t.silent.add("Ledger"), "did not answer the export of ledgers"),
    (lambda t: t.masters.pop("Group"), "exported no groups"),
    (lambda t: setattr(t, "drop_vouchers", 1), "vouchers"),
])
def test_a_backup_that_would_not_be_whole_is_not_kept(tmp_path, break_it, why):
    tally = FakeTally(many_vouchers(30))
    break_it(tally)

    with pytest.raises(B.BackupError, match=why):
        B.make_backup(tally, COMPANY, "hourly", "hourly-test-0003", str(tmp_path))

    assert list(tmp_path.iterdir()) == []      # no ZIP and no half-written file


def test_object_blocks_reads_only_whole_top_level_objects():
    xml = envelope('<UNIT NAME="Nos"><X/></UNIT><UNITS>9</UNITS><UNIT/><UNIT NAME="Box"></UNIT>',
                   "<CMPINFO><UNIT>44</UNIT></CMPINFO>") + '<UNIT NAME="Cut">'
    assert B.object_blocks(xml, "UNIT") == ['<UNIT NAME="Nos"><X/></UNIT>', '<UNIT NAME="Box"></UNIT>']
    assert B.with_action('<LEDGER NAME="A" ACTION="Create"><X>1</X></LEDGER>') == '<LEDGER NAME="A" ACTION="Alter"><X>1</X></LEDGER>'


# ── Which are kept ───────────────────────────────────────────────────────────

def test_keep_rule_is_the_servers():
    now = datetime(2026, 10, 11, 15, 30, tzinfo=B.IST)
    day = lambda n, hour: (now - timedelta(days=n)).replace(hour=hour, minute=0)  # noqa: E731
    backups = [
        ("today-09", day(0, 9), "hourly"), ("today-14", day(0, 14), "hourly"),
        ("yday-10", day(1, 10), "hourly"), ("yday-23", day(1, 23), "hourly"), ("yday-manual", day(1, 12), "manual"),
        ("d3-pre", day(3, 11), "pre_restore"), ("d3-18", day(3, 18), "hourly"), ("d3-08", day(3, 8), "hourly"),
        ("d7-20", day(7, 20), "hourly"), ("d8-20", day(8, 20), "hourly"),
    ]
    assert B.keys_to_keep(backups, now) == {"today-09", "today-14", "yday-23", "d3-pre", "d3-18", "d7-20"}
    assert B.keys_to_keep([("d20-09", day(20, 9), "hourly"), ("d21-09", day(21, 9), "hourly")], now) == {"d20-09"}


def test_the_pc_keeps_copies_by_the_same_rule(tmp_path):
    store, now = B.LocalBackups(str(tmp_path)), datetime(2026, 10, 11, 15, 0, tzinfo=B.IST)
    for key, days, hour in (("d9-xxxxx", 9, 10), ("d2-early", 2, 9), ("d2-later", 2, 20), ("today-01", 0, 1)):
        (tmp_path / "guid-alpha").mkdir(exist_ok=True)
        (tmp_path / "guid-alpha" / f"{key}.zip").write_bytes(b"zip")
        store.add("guid-alpha", {"key": key, "kind": "hourly", "taken_at": (now - timedelta(days=days)).replace(hour=hour).isoformat()})

    assert sorted(store.prune("guid-alpha", now)) == ["d2-early", "d9-xxxxx"]
    assert sorted(p.name for p in (tmp_path / "guid-alpha").glob("*.zip")) == ["d2-later.zip", "today-01.zip"]
    assert [e["key"] for e in store.entries("guid-alpha")] == ["d2-later", "today-01"]


# ── Uploading ────────────────────────────────────────────────────────────────

def test_an_upload_cut_off_carries_on_where_it_stopped(tmp_path):
    path = tmp_path / "big.zip"
    path.write_bytes(bytes(range(256)) * 1100)          # 281,600 bytes: five chunks of 64 KB
    entry = {"key": "hourly-test-0004", "kind": "hourly", "taken_at": B.now_ist().isoformat(), "size": path.stat().st_size,
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    cloud = FakeCloud()
    cloud.fail_chunk_once = 2

    first = B.upload(cloud, entry, str(path), chunk_size=64 * 1024)
    second = B.upload(cloud, entry, str(path), chunk_size=64 * 1024)
    third = B.upload(cloud, entry, str(path), chunk_size=64 * 1024)

    assert first[0] is False and second == (True, "stored on the server") and third == (True, "already on the server")
    assert [i for _, i in cloud.chunk_calls] == [0, 1, 2, 2, 3, 4]       # nothing sent twice that had arrived
    assert cloud.stored["hourly-test-0004"] == path.read_bytes()


# ── The schedule ─────────────────────────────────────────────────────────────

def test_hourly_backups_are_made_once_an_hour_and_kept_until_they_reach_the_server(tmp_path, monkeypatch):
    tally, cloud = FakeTally(many_vouchers(10)), FakeCloud()
    sched = scheduler(tmp_path, tally, cloud)
    cloud.down = True
    start = datetime(2026, 4, 15, 10, 0, tzinfo=B.IST)
    current = start
    monkeypatch.setattr(B, "now_ist", lambda: current)

    sched.tick(start)
    current = start + timedelta(minutes=30)
    sched.tick(current)           # not due again yet
    assert len(sched.store.entries("guid-alpha")) == 1 and not cloud.stored
    cloud.down = False
    current = start + timedelta(minutes=31)
    sched.tick(current)           # back online: the waiting one goes up
    assert len(cloud.stored) == 1 and sched.store.pending_uploads("guid-alpha") == []

    current = start + timedelta(minutes=61)
    sched.tick(current)
    assert len(sched.store.entries("guid-alpha")) == 2 and len(cloud.stored) == 2


def test_back_up_now_uses_the_key_the_app_gave_and_a_failure_is_reported(tmp_path):
    tally, cloud = FakeTally(many_vouchers(10)), FakeCloud()
    sched = scheduler(tmp_path, tally, cloud)
    sched.store.add("guid-alpha", {"key": "recent-0001", "kind": "hourly", "taken_at": B.now_ist().isoformat(), "uploaded": True})
    cloud.jobs = {"backups": [{"backup_key": "app-asked-0001", "kind": "manual"}], "restores": []}

    sched.tick(B.now_ist())
    assert "app-asked-0001" in cloud.stored

    cloud.jobs = {"backups": [{"backup_key": "app-asked-0002", "kind": "manual"}], "restores": []}
    tally.silent.add("Ledger")
    sched.tick(B.now_ist())
    assert cloud.failed == [("app-asked-0002", "Tally did not answer the export of ledgers.")]


def test_closed_companies_are_not_backed_up(tmp_path):
    tally, cloud = FakeTally(many_vouchers(5)), FakeCloud()
    sched = scheduler(tmp_path, tally, cloud, companies=[{**COMPANY, "state": "closed"}])
    sched.tick(B.now_ist())
    assert sched.store.entries("guid-alpha") == [] and not cloud.stored


# ── Restoring ────────────────────────────────────────────────────────────────

def restore_world(tmp_path):
    tally, cloud = FakeTally(many_vouchers(60)), FakeCloud()
    sched = scheduler(tmp_path, tally, cloud)
    made = sched.back_up(dict(COMPANY), cloud, "hourly", "hourly-test-0005")
    job = {"restore_id": 7, "backup_key": made["key"], "sha256": made["sha256"], "size_bytes": made["size"],
           "fingerprint": "1|20250401", "company_name": "Alpha & Co"}
    return tally, cloud, sched, job


def test_a_restore_backs_up_first_then_writes_masters_before_vouchers(tmp_path):
    tally, cloud, sched, job = restore_world(tmp_path)

    assert sched.restore(dict(COMPANY), cloud, job) is True

    (restore_id, pre_key), = cloud.started
    assert restore_id == 7 and pre_key.startswith("pre-restore-") and pre_key in cloud.stored
    reports = [e.split("<REPORTNAME>")[1].split("</REPORTNAME>")[0] for e in tally.imports]
    assert reports[-1] == "Vouchers" and set(reports[:-2]) == {"All Masters"}
    assert '<GROUP NAME="Current Assets" ACTION="Alter">' in tally.imports[0]
    assert "<UDF:SALESMAN DESC" in "".join(tally.imports) and 'ACTION="Create"' not in "".join(tally.imports)
    (_, ok, summary, error), = cloud.finished
    assert ok and error is None
    assert summary["vouchers"] == {"sent": 60, "created": 0, "altered": 60, "errors": 0} and summary["groups"]["sent"] == 2


def test_a_restore_into_another_copy_of_the_books_writes_nothing(tmp_path):
    tally, cloud, sched, job = restore_world(tmp_path)

    assert sched.restore({**COMPANY, "fingerprint": "2|20240401"}, cloud, job) is False

    assert tally.imports == [] and cloud.started == []
    assert cloud.finished[0][1] is False and "different copy of the books" in cloud.finished[0][3]


def test_no_restore_without_the_backup_before_it_on_the_server(tmp_path):
    tally, cloud, sched, job = restore_world(tmp_path)
    cloud.down = True

    assert sched.restore(dict(COMPANY), cloud, job) is False

    assert tally.imports == [] and cloud.started == []


def test_a_backup_fetched_from_the_server_must_match_its_checksum(tmp_path):
    tally, cloud, sched, job = restore_world(tmp_path)
    (tmp_path / "guid-alpha" / f"{job['backup_key']}.zip").unlink()     # not on this PC any more
    cloud.download_bytes = b"not the backup"

    assert sched.restore(dict(COMPANY), cloud, job) is False

    assert tally.imports == [] and "does not match its checksum" in cloud.finished[0][3]


def test_tally_errors_during_a_restore_are_reported(tmp_path):
    tally, cloud, sched, job = restore_world(tmp_path)
    tally.import_reply = "<RESPONSE><CREATED>0</CREATED><ALTERED>0</ALTERED><ERRORS>{n}</ERRORS><LINEERROR>Ledger 'Cash' does not exist</LINEERROR></RESPONSE>"

    assert sched.restore(dict(COMPANY), cloud, job) is False

    (_, ok, summary, error), = cloud.finished
    assert not ok and "does not exist" in error and summary["ledgers"]["errors"] == 1


def test_the_window_says_how_the_backups_stand():
    from bridge_core import backup_note
    now = datetime(2026, 10, 11, 15, 30, tzinfo=B.IST)
    assert backup_note({}) == ""
    assert backup_note({"backup": {"last_backup_at": "2026-10-11T15:05:00+05:30"}}, now) == "Last backup 3:05 pm"
    assert backup_note({"backup": {"last_backup_at": "2026-10-10T09:05:00+05:30"}}, now) == "Last backup 10 Oct, 9:05 am"
    assert backup_note({"backup": {"last_error": "Tally did not answer"}}, now) == "Last backup failed: Tally did not answer"
    assert backup_note({"backup": {"running": True, "message": "Backing up 'Alpha'…"}}, now) == "Backing up 'Alpha'…"
    assert backup_note({"backup": {"restoring": True}}, now) == "Restoring a backup into Tally…"


# ── Where this PC keeps them ─────────────────────────────────────────────────

def test_nothing_is_backed_up_until_a_folder_is_chosen(tmp_path):
    from bridge_core import backup_note
    tally, cloud = FakeTally(many_vouchers(5)), FakeCloud()
    sched = B.BackupScheduler(tally, None, companies=lambda: [dict(COMPANY)], cloud_for=lambda company: cloud)

    sched.tick(B.now_ist())

    assert not cloud.stored and sched.status["needs_folder"] is True
    assert backup_note({"backup": sched.status}) == "Backups wait: choose a folder for them in Settings"
    assert sched.change_folder(str(tmp_path / "chosen")).startswith("Backups are kept in")
    sched.tick(B.now_ist())
    assert len(cloud.stored) == 1 and list((tmp_path / "chosen" / "guid-alpha").glob("*.zip"))


def test_choosing_another_folder_moves_the_backups_already_made(tmp_path):
    tally, cloud = FakeTally(many_vouchers(5)), FakeCloud()
    sched = scheduler(tmp_path / "old", tally, cloud)
    sched.tick(B.now_ist())
    made = sched.store.entries("guid-alpha")

    message = sched.change_folder(str(tmp_path / "new"))

    assert "The backups of 1 company were moved there" in message
    assert sched.store.root == str(tmp_path / "new") and sched.store.entries("guid-alpha") == made
    assert (tmp_path / "new" / "guid-alpha" / f"{made[0]['key']}.zip").exists()
    assert not (tmp_path / "old" / "guid-alpha").exists()


def test_a_folder_change_during_a_backup_waits_for_it(tmp_path):
    tally, cloud = FakeTally(many_vouchers(5)), FakeCloud()
    sched = scheduler(tmp_path / "old", tally, cloud)
    sched.tick(B.now_ist())

    with sched._work:                      # a backup is under way
        message = sched.change_folder(str(tmp_path / "new"))
        assert "when the backup under way finishes" in message and sched.store.root == str(tmp_path / "old")
    sched.tick(B.now_ist())

    assert sched.store.root == str(tmp_path / "new") and (tmp_path / "new" / "guid-alpha").is_dir()


def test_a_folder_that_cannot_hold_backups_is_refused(tmp_path):
    in_the_way = tmp_path / "a-file"
    in_the_way.write_text("not a folder")
    assert B.folder_problem("relative/backups") == "Choose a full folder path."
    assert B.folder_problem(str(in_the_way / "backups")).startswith(f"Backups cannot be written to {in_the_way / 'backups'}")
    assert B.folder_problem(str(tmp_path / "fine")) is None


def test_the_window_and_the_agent_both_remember_the_folder(tmp_path):
    """The window keeps its own copy of the config and saves it from Settings: it must not lose the folder."""
    import bridge_core
    from config import AgentConfig, load_config

    class Agent:
        def __init__(self):
            self.config = AgentConfig()

        def set_backups_folder(self, folder):
            self.config.backups_dir = folder
            return True, f"Backups are kept in {folder}."

    class Host:
        config, config_file, agent = AgentConfig(), str(tmp_path / "agent_config.json"), Agent()

    ok, _ = bridge_core.set_backups_folder(Host, str(tmp_path / "kept"))

    assert ok and Host.config.backups_dir == str(tmp_path / "kept")
    assert load_config(Host.config_file).backups_dir == str(tmp_path / "kept")
