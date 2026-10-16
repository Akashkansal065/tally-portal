"""Write a bank reconciliation date back to Tally, safely (WS-14).

The safe shape: read the voucher's *current* full XML from Tally by master id, check its AlterID is the one
MyTally last saw, change only BANKERSDATE / BANKMANUALSTATUS inside the one matching BANKALLOCATIONS.LIST, and send
that voucher back as an Alter addressed by TAGNAME="MASTERID" with the voucher's date. Repeat-safe: a voucher that
already holds the values is not sent again. Anything unexpected stops and reports; nothing is guessed.
"""
import re
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape, unescape

DONE, ALREADY, STALE, FAILED = "done", "already", "stale", "failed"

_OPEN = re.compile(r"<VOUCHER\b([^>]*)>")
_ALLOC = re.compile(r"<BANKALLOCATIONS\.LIST>(.*?)</BANKALLOCATIONS\.LIST>", re.S)


def _tag(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", text, re.S)
    return unescape(m.group(1)).strip() if m else ""


def _amount(text: str) -> Optional[float]:
    try:
        return abs(float(text.replace(",", "").split()[0]))
    except (ValueError, IndexError):
        return None


def voucher_alter_id(block: str) -> str:
    return _tag(_OPEN.sub("", block, count=1), "ALTERID")


def _set_tag(alloc_inner: str, tag: str, value: str) -> str:
    pattern = re.compile(rf"<{tag}\b[^>]*>.*?</{tag}>|<{tag}\s*/>", re.S)
    new = f"<{tag}>{escape(value)}</{tag}>"
    if pattern.search(alloc_inner):
        return pattern.sub(new, alloc_inner, count=1)
    return alloc_inner + new


def apply_bank_dates(block: str, instrument_number: str, amount: str, bankers_date: str,
                     manual_status: str) -> Tuple[Optional[str], str, str]:
    """Return (new voucher block or None, outcome, message). bankers_date is YYYYMMDD or "" to clear it. Only
    the one BANKALLOCATIONS.LIST that matches instrument number (when given) and amount is touched."""
    wanted_amount = _amount(amount or "")
    matches: List[re.Match] = []
    for m in _ALLOC.finditer(block):
        inner = m.group(1)
        if instrument_number and _tag(inner, "INSTRUMENTNUMBER") != instrument_number:
            continue
        if wanted_amount is not None and _amount(_tag(inner, "AMOUNT")) != wanted_amount:
            continue
        matches.append(m)
    if len(matches) != 1:
        return None, FAILED, (f"Expected exactly one bank allocation matching instrument '{instrument_number}' and amount "
                              f"{amount}; Tally's voucher has {len(matches)}.")
    m = matches[0]
    inner = m.group(1)
    if _tag(inner, "BANKERSDATE") == bankers_date and _tag(inner, "BANKMANUALSTATUS") == manual_status:
        return None, ALREADY, "Tally already holds these values."
    changed = inner
    if bankers_date or _tag(inner, "BANKERSDATE"):
        changed = _set_tag(changed, "BANKERSDATE", bankers_date)
    if manual_status or _tag(inner, "BANKMANUALSTATUS"):
        changed = _set_tag(changed, "BANKMANUALSTATUS", manual_status)
    new_block = block[:m.start(1)] + changed + block[m.end(1):]
    return new_block, DONE, "Changed BANKERSDATE/BANKMANUALSTATUS only."


def alter_envelope(company_name: str, block: str, master_id: int, voucher_date: str) -> str:
    """The voucher as an Alter addressed by master id and date; everything else in it as Tally exported it."""
    head = _OPEN.search(block)
    if head is None:
        raise ValueError("not a voucher")
    vch_type = re.search(r'VCHTYPE="([^"]*)"', head.group(1))
    attrs = f'DATE="{voucher_date}" TAGNAME="MASTERID" TAGVALUE="{int(master_id)}"'
    if vch_type:
        attrs += f' VCHTYPE="{vch_type.group(1)}"'
    attrs += ' ACTION="Alter"'
    body = block[:head.start()] + f"<VOUCHER {attrs}>" + block[head.end():]
    return (f"<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE>"
            f"<ID>Vouchers</ID></HEADER><BODY><DESC><STATICVARIABLES><SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>"
            f"<SVCURRENTCOMPANY>{escape(company_name)}</SVCURRENTCOMPANY></STATICVARIABLES></DESC><DATA>"
            f'<TALLYMESSAGE xmlns:UDF="TallyUDF">{body}</TALLYMESSAGE></DATA></BODY></ENVELOPE>')


def parse_marker(xml: str) -> Optional[Dict[str, str]]:
    """The directive the server queues (see backend/app/services/reconcile_writeback.py)."""
    if "<MYTALLYRECONCILE" not in xml:
        return None
    alloc = re.search(r"<ALLOCATION>(.*?)</ALLOCATION>", xml, re.S)
    inner = alloc.group(1) if alloc else ""
    out = {"master_id": _tag(xml, "MASTERID"), "date": _tag(xml, "DATE"), "alter_id": _tag(xml, "ALTERID"),
           "instrument_number": _tag(inner, "INSTRUMENTNUMBER"), "amount": _tag(inner, "AMOUNT"),
           "bankers_date": _tag(inner, "BANKERSDATE"), "manual_status": _tag(inner, "BANKMANUALSTATUS")}
    return out if out["master_id"].isdigit() and re.fullmatch(r"\d{8}", out["date"]) else None
