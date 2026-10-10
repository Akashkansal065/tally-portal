"""
Payroll masters and Tally: attendance/production types, pay heads, employee groups and employees.

In Tally an attendance type is its own master, a pay head is a ledger with a pay type, and an employee
group or employee is a cost centre marked for payroll (an employee's salary details hang off it).

Sending follows the rule the vouchers use: the change is sent before it is committed, a change Tally
refuses is not kept, and a change made while Tally cannot be reached is kept and queued. Every send first
asks Tally what it holds (by Tally's own GUID once the app knows it, by name before that), so sending the
same change twice never makes a second record and a rename made on either side is followed.
"""
import asyncio
import logging
import re
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.tally_target import current_tally_url
from app.models.portal_core import Company, SyncQueue
from app.services.tally_xml import x

logger = logging.getLogger(__name__)

# record type in the sync queue -> (Tally collection type, XML tag)
KINDS = {
    "AttendanceType": ("AttendanceType", "ATTENDANCETYPE"),
    "PayHead": ("Ledger", "LEDGER"),
    "Employee": ("CostCentre", "COSTCENTRE"),
}
PRIMARY = "&#4; Primary"


def _post(url: str, xml: str, timeout: int = 10) -> str:
    from app.routers import sync
    return sync._post_to_tally_sync(url, xml, timeout)


def _tdl_text(value: str) -> str:
    return (value or "").replace('"', "")


async def tally_lookup(tally_url: str, company: str, tdl_type: str, guid: Optional[str] = None, name: Optional[str] = None) -> Optional[dict]:
    """What Tally holds for a master: {"name", "guid", "master_id"}, or None when it has none. Raises when Tally cannot be reached."""
    formula = f'$GUID = "{_tdl_text(guid)}"' if guid else f'$Name = "{_tdl_text(name)}"'
    xml = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MyTallyMasterLookup</ID></HEADER>
  <BODY><DESC>
    <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVCURRENTCOMPANY>{x(company)}</SVCURRENTCOMPANY></STATICVARIABLES>
    <TDL><TDLMESSAGE>
      <SYSTEM TYPE="Formulae" NAME="MyTallyMasterLookupFilter">{x(formula)}</SYSTEM>
      <COLLECTION NAME="MyTallyMasterLookup" ISMODIFY="No"><TYPE>{tdl_type}</TYPE><FETCH>NAME,GUID,MASTERID</FETCH><FILTERS>MyTallyMasterLookupFilter</FILTERS></COLLECTION>
    </TDLMESSAGE></TDL>
  </DESC></BODY>
</ENVELOPE>"""
    resp = await asyncio.to_thread(_post, tally_url, xml, 10)
    if not resp or not resp.strip():
        raise ConnectionError("No reply from Tally")
    resp = re.sub(r"<CMPINFO>.*?</CMPINFO>", "", resp, flags=re.S)
    tag = tdl_type.upper()
    found = re.search(rf'<{tag} NAME="([^"]*)"(.*?)</{tag}>', resp, re.S)
    if not found:
        return None
    import html
    got_guid = re.search(r"<GUID[^>]*>\s*([^<\s]+)\s*</GUID>", found.group(2))
    master_id = re.search(r"<MASTERID[^>]*>\s*(\d+)\s*</MASTERID>", found.group(2))
    return {"name": html.unescape(found.group(1)), "guid": got_guid.group(1) if got_guid else None,
            "master_id": int(master_id.group(1)) if master_id else None}


def _envelope(company: str, object_xml: str) -> str:
    return f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC><STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{x(company)}</SVCURRENTCOMPANY></STATICVARIABLES></DESC>
    <DATA><TALLYMESSAGE xmlns:UDF="TallyUDF">
      {object_xml}
    </TALLYMESSAGE></DATA>
  </BODY>
</ENVELOPE>"""


def object_xml(tag: str, tally_name: str, action: str, name: str = "", body: str = "") -> str:
    if action == "Delete":
        return f'<{tag} NAME="{x(tally_name)}" ACTION="Delete"><NAME>{x(tally_name)}</NAME></{tag}>'
    return (f'<{tag} NAME="{x(tally_name)}" ACTION="{action}"><NAME>{x(name)}</NAME>'
            f'<LANGUAGENAME.LIST><NAME.LIST TYPE="String"><NAME>{x(name)}</NAME></NAME.LIST></LANGUAGENAME.LIST>{body}</{tag}>')


def attendance_type_body(row) -> str:
    kind = row.type_of_attendance or "Attendance / Leave with Pay"
    if kind == "Production":
        return f"<PARENT>{PRIMARY}</PARENT><ATTENDANCEPRODUCTIONTYPE>Production</ATTENDANCEPRODUCTIONTYPE><BASEUNITS>{x(row.unit_name or '')}</BASEUNITS>"
    return f"<PARENT>{PRIMARY}</PARENT><ATTENDANCEPRODUCTIONTYPE>{x(kind)}</ATTENDANCEPRODUCTIONTYPE><ATTENDANCEPERIOD>{x(row.period or 'Days')}</ATTENDANCEPERIOD>"


def pay_head_body(row, group_name: str) -> str:
    return (f"<PARENT>{x(group_name)}</PARENT><PAYTYPE>{x(row.pay_head_type)}</PAYTYPE><PAYSLIPNAME>{x(row.payslip_name or row.name)}</PAYSLIPNAME>"
            f"<CALCULATIONTYPE>{x(row.calculation_type or '')}</CALCULATIONTYPE><FORPAYROLL>Yes</FORPAYROLL>")


def employee_body(row, category_name: str, parent_name: Optional[str]) -> str:
    body = f"<PARENT>{x(parent_name) if parent_name else PRIMARY}</PARENT><CATEGORY>{x(category_name)}</CATEGORY><FORPAYROLL>Yes</FORPAYROLL>"
    if row.is_employee_group:
        return body + "<ISEMPLOYEEGROUP>Yes</ISEMPLOYEEGROUP>"
    body += "<ISEMPLOYEEGROUP>No</ISEMPLOYEEGROUP>"
    if row.date_of_join:
        body += f"<DATEOFJOIN>{row.date_of_join.strftime('%Y%m%d')}</DATEOFJOIN>"
    body += f"<DESIGNATION>{x(row.designation or '')}</DESIGNATION><GENDER>{x(row.gender or '')}</GENDER>"
    body += f'<MAILINGNAME.LIST TYPE="String"><MAILINGNAME>{x(row.employee_number or "")}</MAILINGNAME></MAILINGNAME.LIST>'
    periods = {}
    for rate in row.salary_rates:
        periods.setdefault(rate.effective_from, []).append(rate)
    for start in sorted(periods):
        lines = "".join(f"<EMPLOYEERATE.LIST><NAME>{x(r.pay_head_name)}</NAME>" + (f"<EMPTIMERATE>{r.rate}</EMPTIMERATE>" if r.rate is not None else "") + "</EMPLOYEERATE.LIST>"
                        for r in periods[start])
        body += f"<EMPLOYEEPERIOD.LIST><PERIODFROM>{start.strftime('%Y%m%d')}</PERIODFROM>{lines}</EMPLOYEEPERIOD.LIST>"
    return body


async def send_master(db: AsyncSession, company_id: int, record_type: str, record_id: int, action: str, name: str, body: str,
                      tally_guid: Optional[str] = None, tally_name: Optional[str] = None, sync_id: Optional[int] = None) -> dict:
    """
    Sends one payroll master to Tally and reports what happened, without committing:
    {"status", "message", "guid", "master_id"} where status is SUCCESS, ALREADY_ABSENT, NOT_CONFIGURED,
    REJECTED (Tally answered and refused) or NO_RESPONSE (Tally could not be reached).
    tally_name: the name Tally may still know the record by, used when the app has no GUID for it.
    """
    from app.routers.sync import check_tally_success, parse_tally_response_metrics
    result = {"status": "NOT_CONFIGURED", "message": "TALLY_URL is not configured", "guid": tally_guid, "master_id": None}
    tally_url = current_tally_url()
    if not tally_url:
        return result
    tdl_type, tag = KINDS[record_type]
    company = (await db.execute(select(Company.name).where(Company.company_id == company_id))).scalars().first() or ""
    started = time.time()
    payload = resp = ""
    result.update(payload="", response="", duration_ms=0)
    try:
        held = await tally_lookup(tally_url, company, tdl_type, guid=tally_guid) if tally_guid else None
        if held is None:
            held = await tally_lookup(tally_url, company, tdl_type, name=tally_name or name)
        if action == "Delete":
            if held is None:
                return {**result, "status": "ALREADY_ABSENT", "message": None}
            payload = _envelope(company, object_xml(tag, held["name"], "Delete"))
        else:
            payload = _envelope(company, object_xml(tag, held["name"] if held else name, "Alter" if held else "Create", name, body))
        resp = await asyncio.to_thread(_post, tally_url, payload, 10)
    except Exception as e:
        logger.warning(f"Tally could not be reached for {record_type} #{record_id} ({action}): {e}")
        return {**result, "status": "NO_RESPONSE", "message": f"Tally could not be reached: {e}"}

    # The exchange is written to the traffic log by the caller, once it has committed or rolled back
    result.update(payload=payload, response=resp, duration_ms=int((time.time() - started) * 1000))
    if not resp or not resp.strip():
        return {**result, "status": "NO_RESPONSE", "message": "No reply from Tally"}
    if not check_tally_success(resp):
        reason = parse_tally_response_metrics(resp)["error_summary"] or "Tally did not accept the change"
        logger.warning(f"Tally refused {record_type} #{record_id} ({action}): {reason}")
        return {**result, "status": "REJECTED", "message": reason}
    if action == "Delete":
        return {**result, "status": "SUCCESS", "message": None}
    try:
        now = await tally_lookup(tally_url, company, tdl_type, name=name)
    except Exception:
        now = None
    return {**result, "status": "SUCCESS", "message": None, "guid": (now or {}).get("guid") or tally_guid, "master_id": (now or {}).get("master_id")}


async def record_master_push(db: AsyncSession, company_id: int, record_type: str, record_id: int, name: str, action: str, result: dict,
                             sync_id: Optional[int] = None) -> None:
    """Writes one exchange with Tally to the traffic log. Commits, so it is called after the change itself is settled."""
    if not result.get("payload"):
        return
    from app.routers.sync import record_sync_traffic_log
    await record_sync_traffic_log(db=db, company_id=company_id, sync_id=sync_id, entity_type=record_type, entity_id=record_id, entity_name=name,
                                  action=action, outbound_format="XML", outbound_payload=result["payload"], inbound_response=result.get("response") or "",
                                  duration_ms=result.get("duration_ms") or 0, tally_url=current_tally_url())


async def queue_for_later(db: AsyncSession, company_id: int, record_type: str, record_id: int, action: str, tally_guid: Optional[str], tally_name: str) -> None:
    """Keeps a change made while Tally was away. One waiting row per record: a later change replaces an earlier one."""
    waiting = (await db.execute(select(SyncQueue).where(
        SyncQueue.company_id == company_id, SyncQueue.record_type == record_type, SyncQueue.record_id == record_id,
        SyncQueue.is_processed == False))).scalars().all()  # noqa: E712
    carried = {"tally_guid": tally_guid, "tally_name": tally_name}
    for row in waiting:
        # The name and GUID Tally knows the record by come from the oldest waiting row
        carried = {**carried, **{k: v for k, v in (row.snapshot_data or {}).items() if v}}
        await db.delete(row)
    if action == "Delete" and any(r.action == "Create" for r in waiting) and not carried.get("tally_guid"):
        return  # made and removed while Tally was away: nothing to tell it
    made_offline = action != "Delete" and any(r.action == "Create" for r in waiting)
    db.add(SyncQueue(company_id=company_id, record_type=record_type, record_id=record_id,
                     action="Create" if made_offline else action, snapshot_data=carried))


# ---------------------------------------------------------------------------------------------------
# The app's rows behind each kind of master
# ---------------------------------------------------------------------------------------------------

SIMPLE_CALCULATIONS = ("As User Defined Value", "Flat Rate")


async def load_row(db: AsyncSession, record_type: str, record_id: int):
    from sqlalchemy.orm import selectinload
    from app.models.tally_core import MstAttendanceType, MstCostCentre, MstPayHead
    if record_type == "AttendanceType":
        stmt = select(MstAttendanceType).where(MstAttendanceType.attendance_type_id == record_id)
    elif record_type == "PayHead":
        stmt = select(MstPayHead).where(MstPayHead.pay_head_id == record_id)
    else:
        stmt = select(MstCostCentre).options(selectinload(MstCostCentre.salary_rates)).where(MstCostCentre.cost_centre_id == record_id)
    return (await db.execute(stmt.execution_options(populate_existing=True))).scalars().first()


async def build_body(db: AsyncSession, record_type: str, row) -> str:
    from app.models.tally_core import MstCostCategory, MstCostCentre, MstGroup
    if record_type == "AttendanceType":
        return attendance_type_body(row)
    if record_type == "PayHead":
        group = (await db.execute(select(MstGroup.name).where(MstGroup.group_id == row.under_group_id))).scalars().first()
        body = pay_head_body(row, group or "Indirect Expenses")
        if row.calculation_type not in SIMPLE_CALCULATIONS:
            # Calculated pay heads carry formulas and slabs the app does not hold, and a pay head whose
            # calculation has not been read from Tally yet is unknown: either way Tally keeps what it has
            body = re.sub(r"<CALCULATIONTYPE>.*?</CALCULATIONTYPE>", "", body)
        elif row.calculation_type == "Flat Rate":
            body += "<CALCULATIONPERIOD>Months</CALCULATIONPERIOD>"
        return body
    category = (await db.execute(select(MstCostCategory.name).where(MstCostCategory.category_id == row.category_id))).scalars().first()
    parent = (await db.execute(select(MstCostCentre.name).where(MstCostCentre.cost_centre_id == row.parent_id))).scalars().first() if row.parent_id else None
    return employee_body(row, category or "Primary Cost Category", parent)


async def tally_identity(db: AsyncSession, record_type: str, row) -> Optional[str]:
    """The GUID Tally gave the record; a pay head carries it on its ledger."""
    if record_type != "PayHead":
        return row.tally_guid
    from app.models.tally_core import MstLedger
    return (await db.execute(select(MstLedger.tally_guid).where(MstLedger.ledger_id == row.ledger_id))).scalars().first() if row.ledger_id else None


async def store_identity(db: AsyncSession, record_type: str, row, result: dict) -> None:
    if not result.get("guid"):
        return
    if record_type == "PayHead":
        from app.models.tally_core import MstLedger
        ledger = (await db.execute(select(MstLedger).where(MstLedger.ledger_id == row.ledger_id))).scalars().first() if row.ledger_id else None
        if ledger:
            ledger.tally_guid, ledger.tally_master_id = result["guid"], result.get("master_id")
    else:
        row.tally_guid, row.tally_master_id = result["guid"], result.get("master_id")


async def replay_queued(db: AsyncSession, item: SyncQueue) -> None:
    """Sends a change that was made while Tally was away, and settles its queue row."""
    from sqlalchemy.sql import func
    carried = item.snapshot_data or {}
    row = await load_row(db, item.record_type, item.record_id) if item.action != "Delete" else None
    if item.action != "Delete" and row is None:
        item.is_processed, item.status, item.error_message = True, "SUCCESS", "The record no longer exists in the app"
        await db.commit()
        return
    name = row.name if row is not None else (carried.get("tally_name") or "")
    body = await build_body(db, item.record_type, row) if row is not None else ""
    guid = carried.get("tally_guid") or (await tally_identity(db, item.record_type, row) if row is not None else None)
    result = await send_master(db, item.company_id, item.record_type, item.record_id, item.action, name, body, guid, carried.get("tally_name"), item.sync_id)
    item.attempts, item.last_attempt_at = (item.attempts or 0) + 1, func.now()
    item.last_payload, item.last_response = result.get("payload") or item.last_payload, result.get("response") or item.last_response
    if result["status"] in ("SUCCESS", "ALREADY_ABSENT"):
        if row is not None:
            await store_identity(db, item.record_type, row, result)
        item.is_processed, item.status, item.error_message = True, "SUCCESS", None
    elif result["status"] == "REJECTED":
        item.status, item.error_message = "FAILED", (result["message"] or "")[:500]
    await db.commit()
    await record_master_push(db, item.company_id, item.record_type, item.record_id, name, item.action, result, item.sync_id)
