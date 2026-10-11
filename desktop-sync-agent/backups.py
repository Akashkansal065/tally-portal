"""Backups of the Tally companies this PC syncs.

Every hour (and when someone presses "Back up now" in the app) the agent exports each open, linked company from
Tally into a ZIP: one XML file per kind of master, the vouchers in date ranges, and a manifest. The ZIP is kept
on this PC and uploaded to the server in chunks (backend/app/routers/backups.py); an upload that was cut off
carries on where it stopped. How many are kept is the same rule here and on the server (keys_to_keep).

A backup is only kept if it is whole: a kind of master Tally would not export, or fewer vouchers than Tally
lists for the company, fails the backup instead of storing a partial one.

A restore writes a stored backup back into the same company: each master and voucher is sent as Tally exported
it, with ACTION="Alter". It refuses a different copy of the books (the fingerprint), and stores a backup of the
company as it is before it writes anything, which is the way back. It brings back what the backup holds; it does
not remove what was added since.
"""
import hashlib
import json
import logging
import math
import os
import re
import secrets
import shutil
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from tally_client import VOUCHER_RANGE_METHODS, escape_xml, voucher_dates

logger = logging.getLogger("Backups")

IST = timezone(timedelta(hours=5, minutes=30))
FORMAT_VERSION = 1
CHUNK_BYTES = 4 * 1024 * 1024
KEEP_DAYS = 7
CHECK_EVERY_SECONDS = 30
VOUCHERS_PER_RANGE = 500
RESTORE_BATCH = 50

# What a backup holds, in the order a restore writes it back (a ledger needs its group and currency first):
# (file key, Tally type, tag of one object in the export, what to fetch, label)
ENTITIES = [
    ("groups", "Group", "GROUP", "*", "Groups"),
    ("currencies", "Currency", "CURRENCY", "*", "Currencies"),
    ("ledgers", "Ledger", "LEDGER", "*,LEDGSTREGDETAILS.LIST,LEDMAILINGDETAILS.LIST,BILLALLOCATIONS.LIST", "Ledgers"),
    ("cost_categories", "CostCategory", "COSTCATEGORY", "*", "Cost categories"),
    ("cost_centres", "CostCentre", "COSTCENTRE", "*", "Cost centres"),
    ("units", "Unit", "UNIT", "*", "Units"),
    ("attendance_types", "AttendanceType", "ATTENDANCETYPE", "*", "Attendance types"),
    ("stock_groups", "StockGroup", "STOCKGROUP", "*", "Stock groups"),
    ("stock_categories", "StockCategory", "STOCKCATEGORY", "*", "Stock categories"),
    ("godowns", "Godown", "GODOWN", "*", "Godowns"),
    ("stock_items", "StockItem", "STOCKITEM", "*,BATCHALLOCATIONS.LIST,MULTICOMPONENTLIST.LIST", "Stock items"),
    ("voucher_types", "VoucherType", "VOUCHERTYPE", "*", "Voucher types"),
]
VOUCHER_FETCH = ("*,ALLLEDGERENTRIES.LIST,INVENTORYENTRIES.LIST,ALLINVENTORYENTRIES.LIST,BILLALLOCATIONS.LIST,"
                 "BANKALLOCATIONS.LIST,BATCHALLOCATIONS.LIST,EWAYBILLDETAILS.LIST,COSTCENTREALLOCATIONS.LIST")
_COUNT = re.compile(r"<(CREATED|ALTERED|DELETED|IGNORED|ERRORS|EXCEPTIONS|CANCELLED)>\s*(\d+)\s*</\1>")


class BackupError(Exception):
    """A backup or restore that could not be done whole. The message is shown to people."""


def now_ist() -> datetime:
    return datetime.now(IST)


def new_key(kind: str, at: Optional[datetime] = None) -> str:
    return f"{kind.replace('_', '-')}-{(at or now_ist()).strftime('%Y%m%d-%H%M')}-{secrets.token_hex(4)}"


def keys_to_keep(backups: Iterable[Tuple[str, datetime, str]], now: datetime) -> Set[str]:
    """Which of (key, taken_at, kind) to keep: all of today's, the last of each of the previous KEEP_DAYS days,
    every pre-restore backup of those days, and always the newest. The same rule as the server's
    (backend/app/services/backups.py); days are calendar days in IST."""
    today = now.astimezone(IST).date()
    keep: Set[str] = set()
    last_of_day: Dict[Any, Tuple[str, datetime]] = {}
    newest: Optional[Tuple[str, datetime]] = None
    for key, taken_at, kind in backups:
        taken_at = taken_at.astimezone(IST)
        if newest is None or taken_at > newest[1]:
            newest = (key, taken_at)
        age = (today - taken_at.date()).days
        if age <= 0:
            keep.add(key)
        elif age <= KEEP_DAYS:
            if kind == "pre_restore":
                keep.add(key)
            elif taken_at.date() not in last_of_day or taken_at > last_of_day[taken_at.date()][1]:
                last_of_day[taken_at.date()] = (key, taken_at)
    keep.update(key for key, _ in last_of_day.values())
    if newest is not None:
        keep.add(newest[0])
    return keep


# ── Reading Tally's XML as text ──────────────────────────────────────────────
# Kept as text, not parsed: Tally exports can carry characters an XML parser refuses, and a restore must send
# each object back exactly as Tally wrote it (UDF: fields included).

def _without_cmpinfo(xml: str) -> str:
    # Tally ends an export with a CMPINFO block of counts, written as <LEDGER>44</LEDGER> and the like
    start = xml.find("<CMPINFO>")
    if start < 0:
        return xml
    end = xml.find("</CMPINFO>", start)
    return xml[:start] + (xml[end + len("</CMPINFO>"):] if end >= 0 else "")


def object_blocks(xml: str, tag: str) -> List[str]:
    """Every object of this tag in an export (<LEDGER NAME="Cash">...</LEDGER>), as Tally wrote it."""
    xml = _without_cmpinfo(xml)
    opener = re.compile(rf"<{tag}(?=[\s>/])")
    closer = f"</{tag}>"
    blocks, pos = [], 0
    while True:
        found = opener.search(xml, pos)
        if found is None:
            return blocks
        head_end = xml.find(">", found.end())
        if head_end < 0:
            return blocks
        if xml[head_end - 1] == "/":     # <TAG/> holds nothing
            pos = head_end + 1
            continue
        depth, scan = 1, head_end + 1
        while depth:
            inner = opener.search(xml, scan)
            close = xml.find(closer, scan)
            if close < 0:
                return blocks            # cut off: the last object is not whole
            if inner is not None and inner.start() < close:
                depth, scan = depth + 1, inner.end()
            else:
                depth, scan = depth - 1, close + len(closer)
        blocks.append(xml[found.start():scan])
        pos = scan


def with_action(block: str, action: str = "Alter") -> str:
    """The object with ACTION set on its opening tag, replacing the one Tally exported."""
    head_end = block.find(">")
    head = re.sub(r'\sACTION="[^"]*"', "", block[:head_end])
    return f'{head} ACTION="{action}"{block[head_end:]}'


def import_envelope(company_name: str, report: str, blocks: List[str]) -> str:
    messages = "\n".join(f'<TALLYMESSAGE xmlns:UDF="TallyUDF">{with_action(b)}</TALLYMESSAGE>' for b in blocks)
    return (f"<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC>"
            f"<REPORTNAME>{report}</REPORTNAME><STATICVARIABLES><SVCURRENTCOMPANY>{escape_xml(company_name)}"
            f"</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC><REQUESTDATA>{messages}</REQUESTDATA></IMPORTDATA>"
            f"</BODY></ENVELOPE>")


def import_counts(reply: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for key, value in _COUNT.findall(reply or ""):
        counts[key.lower()] = counts.get(key.lower(), 0) + int(value)
    return counts


def collection_request(tally_type: str, fetch: str, company_name: str) -> str:
    label = f"MyTallyBackup{tally_type}"
    return f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>{label}</ID></HEADER>
  <BODY><DESC>
    <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
    <TDL><TDLMESSAGE><COLLECTION NAME="{label}"><TYPE>{tally_type}</TYPE><FETCH>{fetch}</FETCH></COLLECTION></TDLMESSAGE></TDL>
  </DESC></BODY>
</ENVELOPE>"""


# ── Making a backup ──────────────────────────────────────────────────────────

def _export(tally, request: str, label: str) -> str:
    xml = tally._export(request, label, timeout=300)
    if xml is None:
        raise BackupError(f"Tally did not answer the export of {label.lower()}.")
    if "<LINEERROR>" in xml:
        error = re.search(r"<LINEERROR>(.*?)</LINEERROR>", xml, re.S)
        raise BackupError(f"Tally refused the export of {label.lower()}: {error.group(1).strip()[:200] if error else ''}")
    return xml


def _voucher_range(tally, company_name: str, date_from: str, date_to: str, expected: int,
                   methods: List[str]) -> Optional[Tuple[str, str, int]]:
    """The vouchers of one range, checked as the sync checks them: all dated inside it, none missing. Returns
    (export, the method that worked, vouchers) or None when no method gives the whole range."""
    recounted = False
    for method in methods:
        request = tally._voucher_request(company_name, "MyTallyBackupVouchers", VOUCHER_FETCH, date_from, date_to,
                                         filter_on_date=(method == "filter"))
        xml = _export(tally, request, f"Vouchers {date_from}-{date_to}")
        got = voucher_dates(xml)
        if any(not (date_from <= day <= date_to) for day in got):
            continue
        if len(got) < expected and not recounted:
            recounted = True   # a voucher may have been deleted or re-dated since they were listed
            fresh = tally.export_voucher_index(company_name)
            if fresh is None:
                raise BackupError("Tally did not list the vouchers.")
            expected = sum(1 for day in fresh if date_from <= day <= date_to)
        if len(got) >= expected:
            return xml, method, len(got)
    return None


def _export_vouchers(tally, company_name: str, zf: zipfile.ZipFile, range_method: Optional[str],
                     per_range: int) -> Tuple[List[str], int, Optional[str]]:
    """Write the company's vouchers into the ZIP. Returns (files, vouchers, the range method that worked)."""
    from agent import plan_voucher_ranges   # the sync's own planner (agent.py imports this module)
    dates = tally.export_voucher_index(company_name)
    if dates is None:
        raise BackupError("Tally did not list the vouchers.")
    methods = [range_method] + [m for m in VOUCHER_RANGE_METHODS if m != range_method] if range_method else list(VOUCHER_RANGE_METHODS)
    files: List[str] = []
    total = 0
    if len(dates) > per_range:
        for n, (date_from, date_to, expected) in enumerate(plan_voucher_ranges(dates, per_range), start=1):
            result = _voucher_range(tally, company_name, date_from, date_to, expected, methods)
            if result is None:
                files, total = [], 0
                break   # this Tally does not honour date ranges: export them in one go below
            xml, method, got = result
            methods = [method] + [m for m in methods if m != method]
            name = f"vouchers_{n:04d}.xml"
            zf.writestr(name, xml)
            files.append(name)
            total += got
        else:
            return files, total, methods[0]
    # Few vouchers, or a Tally that does not honour date ranges: all of them in one export. Its own file name,
    # so ranges written before a Tally stopped honouring them are not mistaken for it (only the manifest counts).
    xml = _export(tally, tally._voucher_request(company_name, "MyTallyBackupVouchers", VOUCHER_FETCH), "Vouchers")
    got = len(voucher_dates(xml))
    if got < len(dates):
        fresh = tally.export_voucher_index(company_name)
        if fresh is None or got < len(fresh):
            raise BackupError(f"Tally exported {got} of the company's {len(fresh) if fresh else len(dates)} vouchers.")
    zf.writestr("vouchers_all.xml", xml)
    return ["vouchers_all.xml"], got, range_method


def make_backup(tally, company: Dict[str, str], kind: str, key: str, folder: str,
                range_method: Optional[str] = None, per_range: int = VOUCHERS_PER_RANGE) -> Dict[str, Any]:
    """Export the company from Tally into folder/<key>.zip. Returns the entry kept about it locally. Raises
    BackupError when the backup would not be whole; nothing is left behind then."""
    name = company["name"]
    os.makedirs(folder, exist_ok=True)
    final = os.path.join(folder, f"{key}.zip")
    partial = final + ".tmp"
    taken_at = now_ist()
    records: Dict[str, int] = {}
    files: Dict[str, List[str]] = {}
    try:
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_key, tally_type, tag, fetch, label in ENTITIES:
                xml = _export(tally, collection_request(tally_type, fetch, name), label)
                zf.writestr(f"{file_key}.xml", xml)
                files[file_key], records[file_key] = [f"{file_key}.xml"], len(object_blocks(xml, tag))
            if not records.get("groups"):
                # Every Tally company has its built-in groups: none means the export was not of this company
                raise BackupError(f"Tally exported no groups for '{name}'. Is the company open in Tally?")
            files["vouchers"], records["vouchers"], range_method = _export_vouchers(tally, name, zf, range_method, per_range)
            zf.writestr("manifest.json", json.dumps({
                "format_version": FORMAT_VERSION, "backup_key": key, "kind": kind, "taken_at": taken_at.isoformat(),
                "company": {"guid": company.get("guid", ""), "name": name, "fingerprint": company.get("fingerprint", ""),
                            "books_from": company.get("starting_from", "")},
                "files": files, "records": records,
            }, indent=2))
        digest = hashlib.sha256()
        with open(partial, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(block)
        size = os.path.getsize(partial)
        os.replace(partial, final)
    except BaseException:
        try:
            os.remove(partial)
        except OSError:
            pass
        raise
    return {"key": key, "kind": kind, "taken_at": taken_at.isoformat(), "size": size, "sha256": digest.hexdigest(),
            "records": records, "company_name": name, "fingerprint": company.get("fingerprint", ""),
            "uploaded": False, "range_method": range_method}


# ── Copies on this PC ────────────────────────────────────────────────────────

def folder_problem(path: str) -> Optional[str]:
    """Why backups cannot be kept in this folder, or None when they can. It is made if it does not exist."""
    if not path or not os.path.isabs(path):
        return "Choose a full folder path."
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return None
    except OSError as e:
        return f"Backups cannot be written to {path} ({e.strerror or e})."


def move_backups(old_root: str, new_root: str) -> Tuple[int, List[str]]:
    """Move each company's backups from old_root into new_root, so the keep rule still looks after them.
    A company that already has a folder in new_root is left where it is. Returns (moved, problems)."""
    moved, problems = 0, []
    if not old_root or not os.path.isdir(old_root) or os.path.abspath(old_root) == os.path.abspath(new_root):
        return moved, problems
    for name in os.listdir(old_root):
        source = os.path.join(old_root, name)
        if not os.path.isfile(os.path.join(source, "index.json")):
            continue
        target = os.path.join(new_root, name)
        if os.path.exists(target):
            problems.append(f"{source} was left where it is: {target} already exists.")
            continue
        try:
            shutil.move(source, target)
            moved += 1
        except OSError as e:
            problems.append(f"{source} could not be moved ({e.strerror or e}).")
    return moved, problems


class LocalBackups:
    """This PC's copies: <root>/<company GUID>/<key>.zip, and index.json listing them."""

    def __init__(self, root: str):
        self.root = root

    def folder(self, guid: str) -> str:
        return os.path.join(self.root, re.sub(r"[^A-Za-z0-9_-]", "_", guid or "unlinked"))

    def path(self, guid: str, key: str) -> str:
        return os.path.join(self.folder(guid), f"{key}.zip")

    def entries(self, guid: str) -> List[Dict[str, Any]]:
        try:
            with open(os.path.join(self.folder(guid), "index.json"), "r", encoding="utf-8") as f:
                entries = json.load(f)
            return [e for e in entries if isinstance(e, dict) and e.get("key")]
        except (OSError, ValueError):
            return []

    def _save(self, guid: str, entries: List[Dict[str, Any]]) -> None:
        os.makedirs(self.folder(guid), exist_ok=True)
        target = os.path.join(self.folder(guid), "index.json")
        with open(target + ".tmp", "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        os.replace(target + ".tmp", target)

    def add(self, guid: str, entry: Dict[str, Any]) -> None:
        self._save(guid, [e for e in self.entries(guid) if e["key"] != entry["key"]] + [entry])

    def mark_uploaded(self, guid: str, key: str) -> None:
        entries = self.entries(guid)
        for e in entries:
            if e["key"] == key:
                e["uploaded"] = True
        self._save(guid, entries)

    def latest_taken_at(self, guid: str, kinds=("hourly", "manual")) -> Optional[datetime]:
        times = [datetime.fromisoformat(e["taken_at"]) for e in self.entries(guid) if e.get("kind") in kinds]
        return max(times) if times else None

    def pending_uploads(self, guid: str) -> List[Dict[str, Any]]:
        return [e for e in self.entries(guid) if not e.get("uploaded") and os.path.exists(self.path(guid, e["key"]))]

    def prune(self, guid: str, now: datetime) -> List[str]:
        """Delete the copies the keep rule no longer wants. Returns their keys."""
        entries = [e for e in self.entries(guid) if os.path.exists(self.path(guid, e["key"]))]
        keep = keys_to_keep(((e["key"], datetime.fromisoformat(e["taken_at"]), e.get("kind", "hourly")) for e in entries), now)
        removed = [e["key"] for e in entries if e["key"] not in keep]
        for key in removed:
            try:
                os.remove(self.path(guid, key))
            except OSError:
                pass
        self._save(guid, [e for e in entries if e["key"] in keep])
        return removed


# ── Uploading ────────────────────────────────────────────────────────────────

def upload(cloud, entry: Dict[str, Any], path: str, chunk_size: int = CHUNK_BYTES) -> Tuple[bool, str]:
    """Send a backup to the server, carrying on from what it already has. (stored, what happened)."""
    status, body = cloud.backup_announce(entry, chunk_size)
    if status != 200 or not isinstance(body, dict):
        return False, f"the server did not take it ({body})"
    if body.get("status") == "stored":
        return True, "already on the server"
    index, chunks, jumps = int(body.get("next_chunk", 0)), math.ceil(entry["size"] / chunk_size), 0
    with open(path, "rb") as f:
        while True:
            while index < chunks:
                f.seek(index * chunk_size)
                status, body, headers = cloud.backup_chunk(entry["key"], index, f.read(chunk_size))
                where = {k.lower(): v for k, v in (headers or {}).items()}.get("x-next-chunk")
                if status == 200 and isinstance(body, dict):
                    index = int(body.get("next_chunk", index + 1))
                elif status == 409 and where is not None and jumps < 5:
                    index, jumps = int(where), jumps + 1
                else:
                    return False, f"chunk {index + 1} of {chunks} was not taken ({body})"
            status, body, headers = cloud.backup_complete(entry["key"])
            if status == 200:
                return True, "stored on the server"
            where = {k.lower(): v for k, v in (headers or {}).items()}.get("x-next-chunk")
            if status in (409, 422) and where is not None and jumps < 5:
                index, jumps = int(where), jumps + 1   # the server wants part of it again
                continue
            return False, f"the server did not keep it ({body})"


# ── Restoring ────────────────────────────────────────────────────────────────

def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _backup_file(cloud, store: LocalBackups, guid: str, job: Dict[str, Any]) -> str:
    """The backup's ZIP on this PC, checked against the checksum the server holds."""
    local = store.path(guid, job["backup_key"])
    if os.path.exists(local) and _sha256_file(local) == job["sha256"]:
        return local
    fetched = local + ".download"
    ok, why = cloud.backup_download(job["backup_key"], fetched)
    if not ok:
        raise BackupError(f"The backup could not be downloaded: {why}.")
    if _sha256_file(fetched) != job["sha256"]:
        os.remove(fetched)
        raise BackupError("The downloaded backup does not match its checksum.")
    os.replace(fetched, local)
    return local


def write_backup_into_tally(tally, company_name: str, path: str) -> Tuple[bool, Dict[str, Dict[str, int]], Optional[str]]:
    """Send every object of the backup to Tally, masters first. Returns (no errors, per kind of record what
    happened, the first problems)."""
    summary: Dict[str, Dict[str, int]] = {}
    problems: List[str] = []
    with zipfile.ZipFile(path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        steps = [(key, tag, "All Masters") for key, _, tag, _, _ in ENTITIES] + [("vouchers", "VOUCHER", "Vouchers")]
        for key, tag, report in steps:
            blocks = [b for name in manifest["files"].get(key, []) for b in object_blocks(zf.read(name).decode("utf-8"), tag)]
            line = {"sent": len(blocks), "created": 0, "altered": 0, "errors": 0}
            for start in range(0, len(blocks), RESTORE_BATCH):
                answered, reply = tally.import_batch(import_envelope(company_name, report, blocks[start:start + RESTORE_BATCH]))
                if not answered:
                    summary[key] = line
                    return False, summary, f"Tally stopped answering while restoring {key}: {reply}"
                counts = import_counts(reply)
                line["created"] += counts.get("created", 0)
                line["altered"] += counts.get("altered", 0)
                errors = counts.get("errors", 0) + counts.get("exceptions", 0)
                line["errors"] += errors
                if errors and len(problems) < 5:
                    found = re.findall(r"<LINEERROR>(.*?)</LINEERROR>", reply, re.S)
                    problems.append(f"{key}: {found[0].strip()[:200] if found else f'{errors} error(s)'}")
            summary[key] = line
    failed = sum(line["errors"] for line in summary.values())
    return failed == 0, summary, ("; ".join(problems) if problems else None)


# ── The schedule ─────────────────────────────────────────────────────────────

class BackupScheduler:
    """Runs beside the sync: every CHECK_EVERY_SECONDS it looks, for each open linked company, for work asked
    for in the app, makes the hourly backup when it is due, uploads what has not reached the server, and
    deletes local copies the keep rule no longer wants. One thing at a time, each Tally request on its own, so
    the 5-second sync carries on between them."""

    def __init__(self, tally, store: Optional[LocalBackups], companies: Callable[[], List[Dict[str, str]]],
                 cloud_for: Callable[[Dict[str, str]], Any], interval_minutes: int = 60,
                 range_method: Callable[[], Optional[str]] = lambda: None,
                 on_restore: Callable[[bool], None] = lambda running: None):
        self.tally, self.store, self.companies, self.cloud_for = tally, store, companies, cloud_for
        self.interval = timedelta(minutes=max(5, interval_minutes))
        self.range_method, self.on_restore = range_method, on_restore
        # store is None until someone chooses where this PC keeps its backups; nothing is backed up till then
        self.status: Dict[str, Any] = {"running": False, "message": "", "last_backup_at": None, "last_error": "",
                                       "needs_folder": store is None}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._work = threading.Lock()            # held while a check runs: files are never moved under a backup
        self._pending_root: Optional[str] = None

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="backups", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick(now_ist())
            except Exception as e:   # never stops the sync, never stops trying
                logger.error(f"Backup check failed: {e}", exc_info=True)
            self._stop.wait(CHECK_EVERY_SECONDS)

    def set_store(self, store: Optional[LocalBackups]) -> None:
        self.store = store
        self.status["needs_folder"] = store is None

    def change_folder(self, new_root: str) -> str:
        """Keep backups in new_root from now on, moving the ones already made there. Done at once when nothing is
        being backed up, else as soon as the backup under way finishes. Returns what to tell the person."""
        if self._work.acquire(blocking=False):
            try:
                return self._apply_folder(new_root)
            finally:
                self._work.release()
        self._pending_root = new_root
        return f"Backups will be kept in {new_root}. The ones already made move there when the backup under way finishes."

    def _apply_folder(self, new_root: str) -> str:
        old_root = self.store.root if self.store else ""
        moved, problems = move_backups(old_root, new_root)
        self.set_store(LocalBackups(new_root))
        self._pending_root = None
        message = f"Backups are kept in {new_root}."
        if moved:
            message += f" The backups of {moved} compan{'y' if moved == 1 else 'ies'} were moved there."
        for problem in problems:
            logger.warning(f"🗂️ {problem}")
        if problems:
            message += f" {len(problems)} folder(s) could not be moved; see the log."
        return message

    def tick(self, now: datetime) -> None:
        with self._work:
            if self._pending_root:
                logger.info(f"🗂️ {self._apply_folder(self._pending_root)}")
            if self.store is None:
                return
            self._tick(now)

    def _tick(self, now: datetime) -> None:
        for company in self.companies():
            if company.get("state") != "open" or not company.get("guid"):
                continue
            cloud = self.cloud_for(company)
            ok, jobs = cloud.backup_jobs()
            if ok and isinstance(jobs, dict):
                for job in jobs.get("restores") or []:
                    self.restore(company, cloud, job)
                for job in jobs.get("backups") or []:
                    self.back_up(company, cloud, "manual", job["backup_key"])
            last = self.store.latest_taken_at(company["guid"])
            if last is None or now - last >= self.interval:
                self.back_up(company, cloud, "hourly")
            for entry in self.store.pending_uploads(company["guid"]):
                self._upload(company, cloud, entry)
            removed = self.store.prune(company["guid"], now)
            if removed:
                logger.info(f"🗂️ {len(removed)} older backup(s) of '{company['name']}' removed from this PC.")

    def back_up(self, company: Dict[str, str], cloud, kind: str, key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Make one backup, keep it here and upload it. Returns its entry, or None when it could not be made."""
        key = key or new_key(kind)
        self.status.update(running=True, message=f"Backing up '{company['name']}'…")
        logger.info(f"💾 Backing up '{company['name']}' ({kind})…")
        started = time.time()
        try:
            entry = make_backup(self.tally, company, kind, key, self.store.folder(company["guid"]), self.range_method())
        except Exception as e:   # a full disk as much as a Tally that would not export: never a partial backup
            why = str(e) if isinstance(e, BackupError) else f"The backup could not be written ({e})."
            self.status.update(running=False, message="", last_error=why)
            logger.error(f"❌ Backup of '{company['name']}' failed: {why}", exc_info=not isinstance(e, BackupError))
            if kind == "manual":
                cloud.backup_failed(key, why)
            return None
        finally:
            self.status["running"] = False
        self.store.add(company["guid"], entry)
        self.status.update(message="", last_backup_at=entry["taken_at"], last_error="")
        logger.info(f"✅ Backup of '{company['name']}' made in {time.time() - started:.0f}s: "
                    f"{entry['records'].get('ledgers', 0)} ledgers, {entry['records'].get('vouchers', 0)} vouchers, "
                    f"{entry['size'] / 1024 / 1024:.1f} MB.")
        self._upload(company, cloud, entry)
        return entry

    def _upload(self, company: Dict[str, str], cloud, entry: Dict[str, Any]) -> bool:
        stored, how = upload(cloud, entry, self.store.path(company["guid"], entry["key"]))
        if stored:
            self.store.mark_uploaded(company["guid"], entry["key"])
            logger.info(f"☁️ Backup {entry['key']} {how}.")
        else:
            logger.warning(f"⏳ Backup {entry['key']} is kept on this PC; upload will be tried again: {how}")
        return stored

    def restore(self, company: Dict[str, str], cloud, job: Dict[str, Any]) -> bool:
        """Carry out a restore asked for in the app. Nothing is written to Tally unless the open company is the
        same copy of the books and a backup of it as it is now has been stored on the server."""
        restore_id = job["restore_id"]
        name = company["name"]
        fingerprint, wanted = (company.get("fingerprint") or "").strip(), (job.get("fingerprint") or "").strip()
        if fingerprint and wanted and fingerprint != wanted:
            return self._refuse(cloud, restore_id, f"The '{name}' open in Tally is a different copy of the books than "
                                                   "the one backed up, so nothing was restored.")
        logger.info(f"♻️ Restore of '{name}' asked for: backing up the company as it is first.")
        self.on_restore(True)
        try:
            pre = self.back_up(company, cloud, "pre_restore")
            if pre is None or not self.store_has_uploaded(company["guid"], pre["key"]):
                return self._refuse(cloud, restore_id, "The backup of the company as it is now could not be stored on the "
                                                       "server, so nothing was restored.")
            status, body = cloud.restore_start(restore_id, pre["key"])
            if status != 200:
                logger.error(f"⛔ Restore not started: {body}")
                return False
            try:
                path = _backup_file(cloud, self.store, company["guid"], job)
                ok, summary, error = write_backup_into_tally(self.tally, name, path)
            except (BackupError, zipfile.BadZipFile, KeyError, ValueError) as e:
                ok, summary, error = False, {}, str(e)
            cloud.restore_finish(restore_id, ok, summary, error)
            if ok:
                logger.info(f"✅ Restore of '{name}' finished.")
            else:
                logger.error(f"❌ Restore of '{name}' finished with problems: {error}")
            return ok
        finally:
            self.on_restore(False)

    def _refuse(self, cloud, restore_id: int, why: str) -> bool:
        """Turn down a restore before anything is written, and tell the app why, so it is not tried again."""
        logger.error(f"⛔ Restore not done: {why}")
        cloud.restore_finish(restore_id, False, {}, why)
        return False

    def store_has_uploaded(self, guid: str, key: str) -> bool:
        return any(e["key"] == key and e.get("uploaded") for e in self.store.entries(guid))
