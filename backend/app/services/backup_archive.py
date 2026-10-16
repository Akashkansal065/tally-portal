"""Reading a backup ZIP as the sync agent writes it (desktop-sync-agent/backups.py): a manifest.json and one XML
file per kind of master plus the vouchers, and checking that what is inside is what the manifest says."""
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FORMAT_VERSION = 1

# (file key, tag of one object): the order a restore writes them (a ledger needs its group and currency first)
ENTITY_ORDER: List[Tuple[str, str]] = [
    ("groups", "GROUP"), ("currencies", "CURRENCY"), ("ledgers", "LEDGER"), ("cost_categories", "COSTCATEGORY"),
    ("cost_centres", "COSTCENTRE"), ("units", "UNIT"), ("attendance_types", "ATTENDANCETYPE"),
    ("stock_groups", "STOCKGROUP"), ("stock_categories", "STOCKCATEGORY"), ("godowns", "GODOWN"),
    ("stock_items", "STOCKITEM"), ("voucher_types", "VOUCHERTYPE"), ("vouchers", "VOUCHER"),
]


class ArchiveError(Exception):
    """The archive is not a whole backup. The message is shown to people."""


def _without_cmpinfo(xml: str) -> str:
    start = xml.find("<CMPINFO>")
    if start < 0:
        return xml
    end = xml.find("</CMPINFO>", start)
    return xml[:start] + (xml[end + len("</CMPINFO>"):] if end >= 0 else "")


def object_blocks(xml: str, tag: str) -> List[str]:
    """Every object of this tag in an export, as Tally wrote it (nested objects of the same tag kept inside)."""
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
        if xml[head_end - 1] == "/":
            pos = head_end + 1
            continue
        depth, scan = 1, head_end + 1
        while depth:
            inner = opener.search(xml, scan)
            close = xml.find(closer, scan)
            if close < 0:
                return blocks
            if inner is not None and inner.start() < close:
                depth, scan = depth + 1, inner.end()
            else:
                depth, scan = depth - 1, close + len(closer)
        blocks.append(xml[found.start():scan])
        pos = scan


def read_manifest(zf: zipfile.ZipFile) -> Dict[str, Any]:
    try:
        manifest = json.loads(zf.read("manifest.json"))
    except KeyError:
        raise ArchiveError("The backup has no manifest.")
    except ValueError:
        raise ArchiveError("The backup's manifest is not readable.")
    if not isinstance(manifest, dict) or manifest.get("format_version") != FORMAT_VERSION:
        raise ArchiveError("The backup is of a format this server does not know.")
    if not isinstance(manifest.get("files"), dict) or not isinstance(manifest.get("records"), dict):
        raise ArchiveError("The backup's manifest is incomplete.")
    return manifest


def entity_blocks(zf: zipfile.ZipFile, manifest: Dict[str, Any], key: str, tag: str) -> List[str]:
    blocks: List[str] = []
    for name in manifest["files"].get(key, []):
        if name not in zf.namelist() or name.startswith("/") or ".." in name:
            raise ArchiveError(f"The backup is missing '{name}' that its manifest lists.")
        blocks += object_blocks(zf.read(name).decode("utf-8", "replace"), tag)
    return blocks


def validate_archive(path: Path) -> Dict[str, Any]:
    """Whole-archive check used by the restore drill: the ZIP's own CRCs, the manifest, every listed file, and
    that each kind holds as many objects as the manifest says. Returns the manifest. Raises ArchiveError."""
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            if bad:
                raise ArchiveError(f"'{bad}' in the backup is damaged.")
            manifest = read_manifest(zf)
            wrong: List[str] = []
            for key, tag in ENTITY_ORDER:
                expected = int(manifest["records"].get(key, 0) or 0)
                got = len(entity_blocks(zf, manifest, key, tag))
                if got != expected:
                    wrong.append(f"{key}: manifest says {expected}, archive holds {got}")
            if wrong:
                raise ArchiveError("The backup does not match its manifest (" + "; ".join(wrong[:4]) + ").")
            return manifest
    except zipfile.BadZipFile:
        raise ArchiveError("The backup file is not a ZIP archive.")
