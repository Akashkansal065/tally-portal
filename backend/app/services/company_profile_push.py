"""Company profile edits made in the app, sent to Tally, and checked against what Tally holds afterwards.

Tally stays the source of the profile: every sync reads it back (tally_xml_importer). So an edit is queued as the
values that changed, not as "send the company row": the row may already hold Tally's older values again by the
time the push runs. Only filled-in values are sent, so a push can never blank something in Tally.

The company's name and its books/financial-year dates are not sent: Tally finds the company by its name, and the
dates decide which vouchers it shows.

Tally answering a company alteration with "ignored" looks like success to the sync agent, so the answer is not
trusted. The next import compares what was sent with what Tally now holds and marks the queue row FAILED when
they differ.
"""
import re
from typing import Dict, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.logging_config import get_logger
from app.models.portal_core import SyncQueue
from app.services.tally_xml import x

logger = get_logger(__name__)

ADDRESS_FIELDS = ("address_line1", "address_line2")
PUSHED_FIELDS = ADDRESS_FIELDS + ("state", "country", "pincode", "telephone", "mobile", "email", "website", "gstin", "pan")

_TAGS = {
    "state": "STATENAME",
    "country": "COUNTRYNAME",
    "pincode": "PINCODE",
    "telephone": "PHONENUMBER",
    "email": "EMAIL",
    "website": "WEBSITE",
    "pan": "INCOMETAXNUMBER",
    "gstin": "GSTREGISTRATIONNUMBER",
}


def profile_values(company) -> Dict[str, str]:
    return {field: (getattr(company, field) or "").strip() for field in PUSHED_FIELDS}


def fields_to_push(before: Dict[str, str], after: Dict[str, str]) -> Dict[str, str]:
    """The filled-in values that differ from before the edit."""
    changed = {field: value for field, value in after.items() if value and value != before.get(field, "")}
    if any(field in changed for field in ADDRESS_FIELDS):
        # Tally replaces the whole address, so both lines go together
        changed.update({field: after[field] for field in ADDRESS_FIELDS if after.get(field)})
    return changed


def build_company_alter_envelope(tally_name: str, fields: Dict[str, str]) -> str:
    """The alteration of the company Tally knows as tally_name, or "" when there is nothing to send."""
    fields = fields or {}
    parts = [f"<{tag}>{x(fields[field])}</{tag}>" for field, tag in _TAGS.items() if fields.get(field)]
    if fields.get("mobile"):
        parts.append(f"<MOBILENUMBERS.LIST><MOBILENUMBERS>{x(fields['mobile'])}</MOBILENUMBERS></MOBILENUMBERS.LIST>")
    address = [fields[field] for field in ADDRESS_FIELDS if fields.get(field)]
    if address:
        parts.append('<ADDRESS.LIST TYPE="String">' + "".join(f"<ADDRESS>{x(line)}</ADDRESS>" for line in address) + "</ADDRESS.LIST>")
    if not parts or not (tally_name or "").strip():
        return ""
    body = "\n".join(parts)
    return f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{x(tally_name)}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<COMPANY NAME="{x(tally_name)}" ACTION="Alter">
{body}
</COMPANY>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""


def _plain(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _not_taken(sent: Dict[str, str], from_tally: Dict[str, str], skip: set) -> List[str]:
    missing = [field for field in sent if field not in ADDRESS_FIELDS and field not in skip
               and _plain(sent[field]) != _plain(from_tally.get(field))]
    sent_address = "".join(sent.get(field) or "" for field in ADDRESS_FIELDS)
    if sent_address and "address" not in skip and _plain(sent_address) != _plain(from_tally.get("address")):
        missing.append("address")
    return missing


async def check_company_pushes(db: AsyncSession, company_id: int, from_tally: Dict[str, str]) -> None:
    """Compare the profile edits sent to Tally with what this import read back from it.

    from_tally: the profile as Tally holds it now, keyed like PUSHED_FIELDS with the address joined under
    "address". An export taken just before the push can still be on its way in, so a difference only counts the
    second time it is seen."""
    rows = (await db.execute(select(SyncQueue).where(
        SyncQueue.company_id == company_id, SyncQueue.record_type == "Company", SyncQueue.record_id == company_id,
        SyncQueue.is_processed == True, SyncQueue.status.in_(("SUCCESS", "PENDING")),  # noqa: E712
    ).order_by(SyncQueue.sync_id.desc()).limit(10))).scalars().all()
    newer = set()   # a field edited again later is judged by the later push only
    for item in rows:
        snapshot = dict(item.snapshot_data or {})
        sent = snapshot.get("fields") or {}
        if not sent or "verified" in snapshot:
            continue
        missing = _not_taken(sent, from_tally, newer)
        newer.update(field for field in sent if field not in ADDRESS_FIELDS)
        if any(field in sent for field in ADDRESS_FIELDS):
            newer.add("address")
        if not missing:
            snapshot["verified"] = True
            logger.info(f"🏢 Tally took the company profile edit #{item.sync_id} of company #{company_id}.")
        elif snapshot.get("unconfirmed"):
            snapshot["verified"] = False
            item.status = "FAILED"
            item.error_message = ("Tally did not take: " + ", ".join(missing) + ". Change it in TallyPrime.")[:500]
            logger.warning(f"🏢 Company profile edit #{item.sync_id} of company #{company_id}: {item.error_message}")
        else:
            snapshot["unconfirmed"] = True
        item.snapshot_data = snapshot
