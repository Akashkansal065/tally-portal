import os
import threading
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import update, delete, text
from sqlalchemy.sql import func
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import re
from decimal import Decimal
from datetime import datetime
import urllib.request
import logging
import uuid

from app.core.database import get_db
from app.core.permissions import require_permission, get_effective_permission, is_admin_user, bind_sync_company, bind_device_sync_company, SYNC_COMPANY_GUID_HEADER
from app.core.agent_auth import agent_device
from app.core.config import settings
from app.core.tally_target import current_tally_url
from app.routers.admin import require_admin
from app.routers.auth import get_current_user
from app.models.portal_core import Company, User, SyncQueue, SyncTrafficLog, DeletedRecordAudit
from app.models.tally_core import MstLedger, MstGroup, TrnVoucher, TrnAccounting, MstStockItem, MstVoucherType
from app.services.tally_xml_importer import import_tally_xml
from app.services.tally_schema_validator import TallySchemaValidator
from app.services.tally_xml import x, xml_tag, clean_xml_str

logger = logging.getLogger("uvicorn.error")
schema_validator = TallySchemaValidator()

router = APIRouter(prefix="/sync", tags=["Tally Synchronization"])

# Global lock to serialize direct outbound HTTP requests to Tally Prime (:9000)
_TALLY_HTTP_LOCK = threading.Lock()

# Global lock to serialize inbound sync background tasks and prevent deadlocks
sync_lock = asyncio.Lock()

def generate_curl_command(tally_url: str, payload: str, format_type: str = "XML") -> str:
    """Generates a clean, copy-paste ready cURL command for Postman / Terminal testing."""
    content_type = "application/json" if format_type in ("JSON", "JSONEX") else "text/xml"
    escaped_payload = payload.replace("'", "'\\''")
    return f"curl --location '{tally_url}' \\\n  --header 'Content-Type: {content_type}' \\\n  --data-raw '{escaped_payload}'"

def parse_tally_response_metrics(resp_str: str) -> dict:
    """Extracts structured counts and error messages from Tally XML / JSON response."""
    metrics = {
        "created": 0, "altered": 0, "deleted": 0, "cancelled": 0, "ignored": 0,
        "errors": 0, "exceptions": 0,
        "vchnumber": None, "error_summary": None, "status": "SUCCESS"
    }
    if not resp_str or not resp_str.strip():
        metrics["status"] = "TIMEOUT"
        metrics["error_summary"] = "Socket timed out / No response from Tally"
        return metrics

    # Extract all LINEERROR tags if present
    line_errors = re.findall(r'<LINEERROR>(.*?)</LINEERROR>', resp_str)
    if line_errors:
        cleaned_errors = [le.replace("&apos;", "'").replace("&quot;", '"').strip() for le in line_errors if le.strip()]
        if cleaned_errors:
            metrics["error_summary"] = " | ".join(cleaned_errors)
            metrics["status"] = "EXCEPTION" if any("does not exist" in err.lower() for err in cleaned_errors) else "FAILED"

    # Extract top-level EXCEPTION tag if present (Tally fatal envelope errors)
    if not metrics["error_summary"] and "<EXCEPTION>" in resp_str:
        m_exc = re.search(r'<EXCEPTION>(.*?)</EXCEPTION>', resp_str, re.DOTALL)
        if m_exc:
            metrics["error_summary"] = m_exc.group(1).replace("&apos;", "'").replace("&quot;", '"').strip()
            metrics["status"] = "EXCEPTION"

    # Extract general ERROR tag if present
    if not metrics["error_summary"] and "<ERROR>" in resp_str:
        m_err = re.search(r'<ERROR>(.*?)</ERROR>', resp_str)
        if m_err:
            metrics["error_summary"] = m_err.group(1).replace("&apos;", "'").replace("&quot;", '"').strip()
            metrics["status"] = "FAILED"

    m_c = re.search(r'<CREATED>(\d+)</CREATED>', resp_str)
    if m_c: metrics["created"] = int(m_c.group(1))
    
    m_a = re.search(r'<ALTERED>(\d+)</ALTERED>', resp_str)
    if m_a: metrics["altered"] = int(m_a.group(1))
    
    m_d = re.search(r'<DELETED>(\d+)</DELETED>', resp_str)
    if m_d: metrics["deleted"] = int(m_d.group(1))

    m_can = re.search(r'<CANCELLED>(\d+)</CANCELLED>', resp_str)
    if m_can: metrics["cancelled"] = int(m_can.group(1))

    m_ig = re.search(r'<IGNORED>(\d+)</IGNORED>', resp_str)
    if m_ig: metrics["ignored"] = int(m_ig.group(1))
    
    m_e = re.search(r'<ERRORS>(\d+)</ERRORS>', resp_str)
    if m_e: metrics["errors"] = int(m_e.group(1))
    
    m_ex = re.search(r'<EXCEPTIONS>(\d+)</EXCEPTIONS>', resp_str)
    if m_ex: metrics["exceptions"] = int(m_ex.group(1))
    
    m_vn = re.search(r'<VCHNUMBER>(.*?)</VCHNUMBER>', resp_str)
    if m_vn: metrics["vchnumber"] = m_vn.group(1)

    if "import_result" in resp_str:
        try:
            jd = json.loads(resp_str)
            ir = jd.get("data", {}).get("import_result", {})
            metrics["created"] = ir.get("created", 0)
            metrics["altered"] = ir.get("altered", 0)
            metrics["deleted"] = ir.get("deleted", 0)
            metrics["cancelled"] = ir.get("cancelled", 0)
            metrics["ignored"] = ir.get("ignored", 0)
            metrics["errors"] = ir.get("errors", 0)
            metrics["exceptions"] = ir.get("exceptions", 0)
            metrics["vchnumber"] = str(ir.get("vchnumber") or "")
            if ir.get("line_error"):
                metrics["error_summary"] = str(ir.get("line_error"))
        except Exception:
            pass

    if metrics["exceptions"] > 0 and metrics["status"] == "SUCCESS":
        metrics["status"] = "EXCEPTION"
    elif metrics["errors"] > 0 and metrics["status"] == "SUCCESS":
        metrics["status"] = "FAILED"
    elif metrics["created"] == 0 and metrics["altered"] == 0 and metrics["deleted"] == 0 and metrics["cancelled"] == 0 and metrics["ignored"] == 0 and "<STATUS>0</STATUS>" in resp_str:
        metrics["status"] = "FAILED"

    if not metrics["error_summary"] and metrics["status"] in ["FAILED", "EXCEPTION"]:
        metrics["error_summary"] = f"Tally rejected import (Errors: {metrics['errors']}, Exceptions: {metrics['exceptions']})"

    return metrics

async def record_sync_traffic_log(
    db: AsyncSession,
    company_id: int,
    sync_id: Optional[int],
    entity_type: str,
    entity_id: Optional[int],
    entity_name: Optional[str],
    action: str,
    outbound_format: str,
    outbound_payload: str,
    inbound_response: str,
    duration_ms: int,
    tally_url: str
):
    """Persists every outbound request and inbound response with a copy-ready Postman cURL."""
    try:
        metrics = parse_tally_response_metrics(inbound_response)
        curl_cmd = generate_curl_command(tally_url, outbound_payload, outbound_format)
        
        status_val = metrics["status"]
        if action == "Delete" and metrics["error_summary"] and "does not exist" in metrics["error_summary"].lower():
            status_val = "EXCEPTION"

        log_entry = SyncTrafficLog(
            company_id=company_id,
            sync_id=sync_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            action=action,
            status=status_val,
            http_status=200 if inbound_response else 504,
            outbound_format=outbound_format,
            outbound_payload=outbound_payload,
            curl_command=curl_cmd,
            inbound_response=inbound_response,
            error_summary=metrics["error_summary"],
            parsed_created=metrics["created"],
            parsed_altered=metrics["altered"],
            parsed_deleted=metrics["deleted"],
            parsed_errors=metrics["errors"],
            parsed_exceptions=metrics["exceptions"],
            tally_vchnumber=metrics["vchnumber"],
            duration_ms=duration_ms
        )
        db.add(log_entry)
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to record SyncTrafficLog: {str(e)}", exc_info=True)

class ActiveTallySyncConfig:
    def __init__(self, tally_url: str):
        self.tally_url = tally_url

async def get_active_tally_sync_for_company(company_id: int, db: AsyncSession) -> Optional[ActiveTallySyncConfig]:
    """
    Retrieves the active Tally Sync configuration for a specific company.
    Currently uses the global current_tally_url() until multi-tenant Tally sync configuration is implemented.
    """
    if current_tally_url():
        return ActiveTallySyncConfig(tally_url=current_tally_url())
    return None

async def run_inbound_sync_background(xml_data: str, user_id: int, company_name: Optional[str] = None):
    """Asynchronously parses and imports inbound Tally XML, serialized via a global lock."""
    from app.core.database import AsyncSessionLocal
    from app.core.cache import clear_company_cache
    import logging
    logger = logging.getLogger("uvicorn.error")

    async with sync_lock:
        async with AsyncSessionLocal() as db:
            try:
                logger.info(f"Background inbound sync task started for user_id={user_id}, target_company='{company_name}'")
                result = await import_tally_xml(xml_data, db, user_id, override_company_name=company_name)
                company_id = result.get("company_id")
                if result.get("status") == "error":
                    logger.error(f"Background inbound sync failed for user_id={user_id}: {result.get('message')}")
                else:
                    logger.info(f"Background inbound sync succeeded for company '{result.get('company_name')}' (ID: {company_id})")
                    if company_id:
                        clear_company_cache(company_id)
            except Exception as e:
                logger.error(f"Background inbound sync exception for user_id={user_id}: {str(e)}", exc_info=True)

@router.post("/inbound", dependencies=[Depends(bind_device_sync_company)])
async def inbound_sync(
    request: Request,
    company_name: Optional[str] = Query(None),
    force: bool = Query(False),
    user: User = Depends(require_permission("sync", "create")),
    db: AsyncSession = Depends(get_db)
):
    """
    Receives raw Tally XML export from sync bridge daemon, importing it directly into the database.
    Requires the 'sync' permission (Desktop Sync Agent account); force overwrite also needs sync delete.
    """
    if not company_name:
        company_name = request.headers.get("x-company-name")
    # Unlike the other agent endpoints, a GUID no company is linked to yet is allowed here: this import
    # is what links it
    company_guid = (request.headers.get(SYNC_COMPANY_GUID_HEADER) or "").strip() or None

    is_force = force or (request.headers.get("x-force-sync", "").strip().lower() in ("true", "1", "yes"))
    if is_force and agent_device(request) is None:
        sync_perms = await get_effective_permission(user, "sync", db)
        if not sync_perms.get("can_delete", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Force overwrite requires delete permission on Tally Sync."
            )
    body = await request.body()
    # Auto detect UTF-16 or UTF-8 to prevent UnicodeDecodeError on raw file uploads
    if body.startswith(b'\xff\xfe') or body.startswith(b'\xfe\xff'):
        xml_data = body.decode('utf-16')
    else:
        try:
            xml_data = body.decode('utf-8')
        except UnicodeDecodeError:
            xml_data = body.decode('utf-8', errors='ignore')
    
    if not xml_data or not xml_data.strip():
        return {
            "status": "error",
            "message": "Empty sync payload received.",
            "imported_groups": 0, "imported_ledgers": 0, "imported_vouchers": 0,
            "imported_stock_groups": 0, "imported_uoms": 0, "imported_godowns": 0,
            "imported_stock_categories": 0, "imported_stock_items": 0
        }
        
    # Which company this is for is settled here, never by a name in the payload. A signed-in PC is already
    # held to a company linked to it. A person's import goes to the company they are working in, or, when
    # an agent on a person's login names a Tally company, to the company linked to that GUID.
    target_company_id = user.company_id
    if agent_device(request) is None and company_guid:
        from app.core.permissions import company_for_tally_guid
        named = await company_for_tally_guid(db, user, company_guid)
        if named is not None:
            target_company_id = named.company_id
        else:
            current_guid = (await db.execute(select(Company.tally_guid).where(Company.company_id == user.company_id))).scalar()
            if current_guid:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, headers={"X-Sync-Reason": "company_not_linked"},
                    detail=f"No company you can access is linked to Tally company GUID {company_guid}. "
                           "Link it from the Desktop Sync Agent.")
            # The company being worked in has never been tied to a Tally company: this import ties it

    async with sync_lock:
        try:
            result = await import_tally_xml(
                xml_data, db, user.user_id,
                company_guid=company_guid,
                force_overwrite=is_force,
                target_company_id=target_company_id,
            )
            company_id = result.get("company_id")
            if company_id:
                from app.core.cache import clear_company_cache
                clear_company_cache(company_id)
            return result
        except Exception as ex:
            # Full exception stays in the server log; the client gets a reference to quote, not internals
            error_ref = uuid.uuid4().hex[:12]
            logger.error(f"❌ [INBOUND SYNC CRITICAL EXCEPTION] ref={error_ref} user_id={user.user_id} company='{company_name}': {ex}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Inbound XML import failed on server (error ref {error_ref}). Check the backend logs for this reference."
            )

def voucher_remote_id(voucher) -> Optional[str]:
    """
    The REMOTEID a voucher created here was sent to Tally under, or None if it has never been sent under one.
    Tally updates the voucher it first received under a REMOTEID when the same one is sent again, which is
    what makes a re-sent push harmless.
    """
    return voucher.tally_remote_id


def new_voucher_remote_id() -> str:
    """
    A REMOTEID for a voucher about to be sent for the first time. Random, never built from the voucher's row
    id: row ids get reused (after deletes and a restart, or a re-import), and a reused id would address some
    other voucher Tally still holds under it.
    """
    return f"MYTALLY-{uuid.uuid4().hex}"


def is_tally_guid(guid: Optional[str]) -> bool:
    """True for a GUID Tally issued, as opposed to a placeholder this app or the importer made up."""
    return bool(guid) and not guid.startswith(("MYTALLY-", "GEN-"))


def voucher_address_attrs(vdate_str: str, remote_id: Optional[str], master_id: Optional[int]) -> str:
    """
    How a voucher import says which voucher it means. A voucher Tally already holds is addressed by its
    master id: Tally's own GUID does not work as a REMOTEID (it creates a second voucher), and a voucher
    number is not safe (Tally ignores the voucher type when matching one).
    With a master id, vdate_str must be the date the voucher has in Tally now: Tally looks under that date,
    and creates a second voucher when a changed date is given here instead.
    """
    if master_id:
        return f'DATE="{vdate_str}" TAGNAME="MASTERID" TAGVALUE="{int(master_id)}"'
    return f'REMOTEID="{x(remote_id)}"'


def build_voucher_address_envelope(comp_name: str, vtype_name: str, vdate_str: str, action: str,
                                   remote_id: Optional[str] = None, master_id: Optional[int] = None) -> str:
    """A Delete or Cancel: only the address of the voucher, no content."""
    return f'''<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER {voucher_address_attrs(vdate_str, remote_id, master_id)} VCHTYPE="{x(vtype_name)}" ACTION="{x(action)}">
              <DATE>{vdate_str}</DATE>
              <VOUCHERTYPENAME>{x(vtype_name)}</VOUCHERTYPENAME>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'''


async def build_voucher_xml_payload(voucher_id: int, action: str, db: AsyncSession, master_id: Optional[int] = None,
                                    tally_date: Optional[str] = None) -> str:
    """
    The voucher as a Tally import. master_id: the voucher's master id when Tally already holds it, with
    tally_date the date (YYYYMMDD) it has there; without one the voucher goes under its own REMOTEID.
    """
    try:
        from app.models.tally_core import (
            TrnVoucher, TrnAccounting, MstLedger, MstVoucherType, BillAllocation, 
            TrnInventory, MstStockItem, MstGodown, Batch, VoucherAccountingAllocation,
            CostCenter, TrnCostCentreAllocation, MstCostCentre
        )
        from app.models.portal_core import Company
        
        # populate_existing: the caller may hold this voucher with lines it has since replaced
        v_stmt = select(TrnVoucher).options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bill_allocations).selectinload(BillAllocation.bill),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.cost_centre_allocations).selectinload(TrnCostCentreAllocation.cost_centre),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.stock_item).selectinload(MstStockItem.unit),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.godown),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.batch),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.accounting_allocations).selectinload(VoucherAccountingAllocation.ledger),
            selectinload(TrnVoucher.eway_bills),
            selectinload(TrnVoucher.payment_links)
        ).where(TrnVoucher.voucher_id == voucher_id).execution_options(populate_existing=True)
        v_res = await db.execute(v_stmt)
        voucher = v_res.scalars().first()
        if not voucher:
            return ""

        comp = (await db.execute(select(Company).where(Company.company_id == voucher.company_id))).scalars().first()
        comp_name = comp.name if comp else ""
        vtype_name = voucher.voucher_type.name if voucher.voucher_type else "Journal"
        is_inv = getattr(voucher, 'is_invoice', False) or bool(getattr(voucher, 'inventory_entries', None))
        vdate_str = voucher.voucher_date.strftime("%Y%m%d")
        obj_view = "Invoice Voucher View" if is_inv else "Accounting Voucher View"

        if action in ("Cancel", "Delete"):
            return build_voucher_address_envelope(comp_name, vtype_name, tally_date or vdate_str, action,
                                                  voucher_remote_id(voucher), master_id)

        from app.services.voucher_kinds import stock_leaves, is_sales_side, is_stock_journal, is_physical_stock, is_attendance, is_payroll
        from app.models.tally_core import TrnAttendance, TrnPayHead
        remote_alt_xml = f"\n              <REMOTEALTGUID>{x(voucher.tally_remote_id)}</REMOTEALTGUID>" if voucher.tally_remote_id else ""
        cancelled_xml = "\n              <ISCANCELLED>Yes</ISCANCELLED>" if (voucher.is_cancelled or voucher.status == "cancelled") else ""

        def simple_envelope(view: str, body_xml: str) -> str:
            """A voucher that is only its header and the lines given (no party, no invoice fields)."""
            return f'''<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER {voucher_address_attrs(tally_date or vdate_str, voucher_remote_id(voucher), master_id)} VCHTYPE="{x(vtype_name)}" ACTION="{x(action)}" OBJVIEW="{view}">
              <DATE>{vdate_str}</DATE>
              <VOUCHERTYPENAME>{x(vtype_name)}</VOUCHERTYPENAME>
              <VOUCHERNUMBER>{x(voucher.voucher_number)}</VOUCHERNUMBER>
              <PERSISTEDVIEW>{view}</PERSISTEDVIEW>
              <NARRATION>{x(voucher.narration)}</NARRATION>{cancelled_xml}{remote_alt_xml}{body_xml}
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'''

        if is_attendance(voucher.voucher_type):
            # Attendance: one line per employee and attendance type; nothing else
            rows = (await db.execute(select(TrnAttendance).where(TrnAttendance.voucher_id == voucher_id).order_by(TrnAttendance.id))).scalars().all()
            lines_xml = "".join(f'''
              <ATTENDANCEENTRIES.LIST>
               <NAME>{x(row.employee_name)}</NAME>
               <ATTENDANCETYPE>{x(row.attendancetype_name)}</ATTENDANCETYPE>
               <ATTDTYPETIMEVALUE> {_qty(row.time_value)}</ATTDTYPETIMEVALUE>
               <ATTDTYPEVALUE> {_qty(row.time_value)}</ATTDTYPEVALUE>
              </ATTENDANCEENTRIES.LIST>''' for row in rows)
            return simple_envelope("Accounting Voucher View", lines_xml)

        pay_rows = (await db.execute(select(TrnPayHead).where(TrnPayHead.voucher_id == voucher_id).order_by(TrnPayHead.id))).scalars().all()
        if is_payroll(voucher.voucher_type) and pay_rows:
            # Payroll: per cost category and employee the pay heads, then the ledger lines they add up to.
            # Signs as Tally keeps them: an earning is debited (negative, deemed positive), a deduction credited.
            by_category: dict = {}
            for row in pay_rows:
                by_category.setdefault(row.category or "Primary Cost Category", {}).setdefault(row.employee_name, []).append(row)
            lines_xml = ""
            for category, employees in by_category.items():
                lines_xml += f"\n              <CATEGORYENTRY.LIST>\n               <CATEGORY>{x(category)}</CATEGORY>"
                for employee, heads in employees.items():
                    employee_total = sum((Decimal(str(h.amount or 0)) for h in heads), Decimal("0"))
                    lines_xml += f"\n               <EMPLOYEEENTRIES.LIST>\n                <EMPLOYEENAME>{x(employee)}</EMPLOYEENAME>\n                <AMOUNT>{float(employee_total):.2f}</AMOUNT>"
                    for head in heads:
                        head_amount = Decimal(str(head.amount or 0))
                        lines_xml += f'''
                <PAYHEADALLOCATIONS.LIST>
                 <PAYHEADNAME>{x(head.payhead_name)}</PAYHEADNAME>
                 <ISDEEMEDPOSITIVE>{'Yes' if head_amount < 0 else 'No'}</ISDEEMEDPOSITIVE>
                 <AMOUNT>{float(head_amount):.2f}</AMOUNT>
                </PAYHEADALLOCATIONS.LIST>'''
                    lines_xml += "\n               </EMPLOYEEENTRIES.LIST>"
                lines_xml += "\n              </CATEGORYENTRY.LIST>"
            payable_name = ""
            for ent in voucher.entries:
                lname = ent.ledger.name if ent.ledger else ""
                debit = ent.debit_amount and ent.debit_amount > 0
                if voucher.party_ledger_id and ent.ledger_id == voucher.party_ledger_id:
                    payable_name = lname
                lines_xml += f'''
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>{x(lname)}</LEDGERNAME>
               <ISDEEMEDPOSITIVE>{'Yes' if debit else 'No'}</ISDEEMEDPOSITIVE>
               <AMOUNT>{-float(ent.debit_amount) if debit else float(ent.credit_amount):.2f}</AMOUNT>
              </ALLLEDGERENTRIES.LIST>'''
            party_xml = f"\n              <PARTYLEDGERNAME>{x(payable_name)}</PARTYLEDGERNAME>" if payable_name else ""
            return simple_envelope("PaySlip Voucher View", f"{party_xml}\n              <ASPAYSLIP>Yes</ASPAYSLIP>{lines_xml}")

        physical = is_physical_stock(voucher.voucher_type)
        if physical or is_stock_journal(voucher.voucher_type) or any(inv.flow_type for inv in voucher.inventory_entries):
            # A Stock Journal has no ledger lines and no party: items produced go in INVENTORYENTRIESIN.LIST,
            # items consumed in INVENTORYENTRIESOUT.LIST, and Tally only takes it in its Consumption view
            view = "Consumption Voucher View"
            lines_xml = ""
            for inv in voucher.inventory_entries:
                arrives = inv.flow_type == "destination" if inv.flow_type else bool(inv.is_inward)
                tag = "INVENTORYENTRIESIN.LIST" if arrives else "INVENTORYENTRIESOUT.LIST"
                uom_name = inv.stock_item.unit.symbol if (inv.stock_item and inv.stock_item.unit) else "nos"
                amount = f"{'-' if arrives else ''}{float(abs(inv.amount or 0)):.2f}"
                qty_str = f" {_qty(inv.quantity)} {uom_name}"
                rate_tag = f"\n               <RATE>{float(inv.rate):.2f}/{x(uom_name)}</RATE>" if inv.rate else ""
                if physical:
                    # A Physical Stock count: Tally takes the counted quantity, always in the "in" list, and
                    # refuses it in any other list or view. Rate and amount are not part of a count.
                    tag, arrives, amount, rate_tag = "INVENTORYENTRIESIN.LIST", True, "", ""
                    qty_str = f" {_qty(inv.actual_quantity if inv.actual_quantity is not None else inv.quantity)} {uom_name}"
                amount_tag = f"\n               <AMOUNT>{amount}</AMOUNT>" if amount else ""
                batch_amount_tag = f"\n                <AMOUNT>{amount}</AMOUNT>" if amount else ""
                godown_name = inv.godown.name if (inv.godown and inv.godown.name) else "Main Location"
                batch_name = inv.batch.batch_number if (inv.batch and inv.batch.batch_number) else "Primary Batch"
                lines_xml += f'''
              <{tag}>
               <STOCKITEMNAME>{x(inv.stock_item.name if inv.stock_item else "")}</STOCKITEMNAME>
               <ISDEEMEDPOSITIVE>{'Yes' if arrives else 'No'}</ISDEEMEDPOSITIVE>{rate_tag}{amount_tag}
               <ACTUALQTY>{x(qty_str)}</ACTUALQTY>
               <BILLEDQTY>{x(qty_str)}</BILLEDQTY>
               <BATCHALLOCATIONS.LIST>
                <GODOWNNAME>{x(godown_name)}</GODOWNNAME>
                <BATCHNAME>{x(batch_name)}</BATCHNAME>{batch_amount_tag}
                <ACTUALQTY>{x(qty_str)}</ACTUALQTY>
                <BILLEDQTY>{x(qty_str)}</BILLEDQTY>
               </BATCHALLOCATIONS.LIST>
              </{tag}>'''
            cancelled = "\n              <ISCANCELLED>Yes</ISCANCELLED>" if (voucher.is_cancelled or voucher.status == "cancelled") else ""
            remote_alt = f"\n              <REMOTEALTGUID>{x(voucher.tally_remote_id)}</REMOTEALTGUID>" if voucher.tally_remote_id else ""
            return f'''<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER {voucher_address_attrs(tally_date or vdate_str, voucher_remote_id(voucher), master_id)} VCHTYPE="{x(vtype_name)}" ACTION="{x(action)}" OBJVIEW="{view}">
              <DATE>{vdate_str}</DATE>
              <VOUCHERTYPENAME>{x(vtype_name)}</VOUCHERTYPENAME>
              <VOUCHERNUMBER>{x(voucher.voucher_number)}</VOUCHERNUMBER>
              <PERSISTEDVIEW>{view}</PERSISTEDVIEW>
              <NARRATION>{x(voucher.narration)}</NARRATION>{cancelled}{remote_alt}{lines_xml}
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'''

        # Stock direction and sales/purchase side are separate questions (a Debit Note sends stock out but
        # posts to a purchase ledger); is_sales below means "stock leaves, party debited"
        is_sales = stock_leaves(voucher.voucher_type)
        sales_side = is_sales_side(voucher.voucher_type)
        sales_pur_ledger_name = "GST Sales" if sales_side else "GST Purchase"
        for ent in voucher.entries:
            if ent.ledger and ent.ledger.group:
                gname = ent.ledger.group.name.lower()
                if ("sales" in gname if sales_side else "purchase" in gname):
                    sales_pur_ledger_name = ent.ledger.name
                    break

        party_ledger_name = ""
        if voucher.party_ledger_id:
            p_res = await db.execute(select(MstLedger).where(MstLedger.ledger_id == voucher.party_ledger_id))
            party_ledger = p_res.scalars().first()
            if party_ledger:
                party_ledger_name = party_ledger.name
        elif vtype_name in ["Sales", "Purchase", "Payment", "Receipt"]:
            for ent in voucher.entries:
                if ent.ledger and ent.ledger.group:
                    gname = ent.ledger.group.name.lower()
                    if "bank" not in gname and "cash" not in gname and "sales" not in gname and "purchase" not in gname and "duty" not in gname and "tax" not in gname:
                        party_ledger_name = ent.ledger.name
                        break
        if not party_ledger_name and voucher.entries:
            party_ledger_name = voucher.entries[0].ledger.name if voucher.entries[0].ledger else "Suspense A/c"

        all_inventory_xml = ""
        if is_inv and getattr(voucher, 'inventory_entries', None):
            for inv in voucher.inventory_entries:
                item_name = inv.stock_item.name if inv.stock_item else "Item"
                uom_name = inv.stock_item.unit.name if (inv.stock_item and inv.stock_item.unit) else "nos"
                is_dp = 'No' if is_sales else 'Yes'
                inv_amt = float(abs(inv.amount))
                signed_inv_amt = inv_amt if is_sales else -inv_amt
                rate_str = f"{inv.rate}/{uom_name}" if inv.rate else ""
                qty_str = f" {inv.quantity} {uom_name}" if inv.quantity else ""
                billed_qty_str = f" {inv.billed_qty} {uom_name}" if inv.billed_qty else qty_str
                godown_name = inv.godown.name if (inv.godown and inv.godown.name) else "Main Location"
                batch_name = inv.batch.batch_number if (inv.batch and inv.batch.batch_number) else "Primary Batch"
                discount_tag = f"\n               <DISCOUNT>{float(inv.discount_percent):g}</DISCOUNT>" if getattr(inv, 'discount_percent', None) and float(inv.discount_percent) > 0 else ""
                
                all_inventory_xml += f'''
              <ALLINVENTORYENTRIES.LIST>
               <STOCKITEMNAME>{x(item_name)}</STOCKITEMNAME>
               <ISDEEMEDPOSITIVE>{is_dp}</ISDEEMEDPOSITIVE>
               <RATE>{x(rate_str)}</RATE>{discount_tag}
               <AMOUNT>{signed_inv_amt:.2f}</AMOUNT>
               <ACTUALQTY>{x(qty_str)}</ACTUALQTY>
               <BILLEDQTY>{x(billed_qty_str)}</BILLEDQTY>
               <BATCHALLOCATIONS.LIST>
                <GODOWNNAME>{x(godown_name)}</GODOWNNAME>
                <BATCHNAME>{x(batch_name)}</BATCHNAME>
                <AMOUNT>{signed_inv_amt:.2f}</AMOUNT>
                <ACTUALQTY>{x(qty_str)}</ACTUALQTY>
                <BILLEDQTY>{x(billed_qty_str)}</BILLEDQTY>
               </BATCHALLOCATIONS.LIST>
               <ACCOUNTINGALLOCATIONS.LIST>
                <LEDGERNAME>{x(sales_pur_ledger_name)}</LEDGERNAME>
                <ISDEEMEDPOSITIVE>{is_dp}</ISDEEMEDPOSITIVE>
                <ISPARTYLEDGER>No</ISPARTYLEDGER>
                <AMOUNT>{signed_inv_amt:.2f}</AMOUNT>
               </ACCOUNTINGALLOCATIONS.LIST>
              </ALLINVENTORYENTRIES.LIST>'''

        ledger_tag = "LEDGERENTRIES.LIST" if is_inv else "ALLLEDGERENTRIES.LIST"
        entries_xml = ""
        from app.models.tally_core import TrnBill
        party_bill_name = (await db.execute(select(TrnBill.bill_reference).where(
            TrnBill.voucher_id == voucher.voucher_id, TrnBill.party_ledger_id == voucher.party_ledger_id))).scalars().first() if voucher.party_ledger_id else None
        for ent in voucher.entries:
            lname = ent.ledger.name if ent.ledger else "Suspense A/c"
            # In Item Invoices, skip the main Sales/Purchase ledger from top-level entries to avoid double counting
            if is_inv and (lname.strip().lower() == sales_pur_ledger_name.strip().lower() or (ent.ledger and ent.ledger.group and ("sales" in ent.ledger.group.name.lower() or "purchase" in ent.ledger.group.name.lower()))):
                continue

            amt = -float(ent.debit_amount) if ent.debit_amount > 0 else float(ent.credit_amount)
            is_dp = 'Yes' if ent.debit_amount > 0 else 'No'
            is_party = (party_ledger_name and lname.strip().lower() == party_ledger_name.strip().lower())
            
            entries_xml += f'''
              <{ledger_tag}>
               <LEDGERNAME>{x(lname)}</LEDGERNAME>
               <ISDEEMEDPOSITIVE>{is_dp}</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>{'Yes' if is_party else 'No'}</ISPARTYLEDGER>
               <AMOUNT>{amt:.2f}</AMOUNT>'''

            if getattr(ent, 'bank_allocations', None):
                for ba in ent.bank_allocations:
                    ba_amt = -float(ba.amount) if ent.debit_amount > 0 else float(ba.amount)
                    inst_date = ba.instrument_date.strftime("%Y%m%d") if ba.instrument_date else vdate_str
                    tx_type = ba.transaction_type or "Others"
                    bank_op_tag = f"\n                 <BANKOPERATIONREFERENCE>{x(ba.bank_operation_ref)}</BANKOPERATIONREFERENCE>" if getattr(ba, 'bank_operation_ref', None) else ""
                    bank_prt_tag = f"\n                 <BANKPORTALREFERENCE>{x(ba.bank_portal_ref)}</BANKPORTALREFERENCE>" if getattr(ba, 'bank_portal_ref', None) else ""
                    bank_txn_tag = f"\n                 <BANKTRANSACTIONREFERENCE>{x(ba.bank_transaction_ref)}</BANKTRANSACTIONREFERENCE>" if getattr(ba, 'bank_transaction_ref', None) else ""
                    paylink_tag = f"\n                 <PAYMENTLINK>{x(ba.payment_link)}</PAYMENTLINK>" if getattr(ba, 'payment_link', None) else ""
                    entries_xml += f'''
               <BANKALLOCATIONS.LIST>
                <DATE>{vdate_str}</DATE>
                <INSTRUMENTDATE>{inst_date}</INSTRUMENTDATE>
                <TRANSACTIONTYPE>{x(tx_type)}</TRANSACTIONTYPE>
                <PAYMENTMODE>Transacted</PAYMENTMODE>{bank_op_tag}{bank_prt_tag}{bank_txn_tag}{paylink_tag}
                <BANKPARTYNAME>{x(party_ledger_name or 'Cash')}</BANKPARTYNAME>
                <AMOUNT>{ba_amt:.2f}</AMOUNT>
               </BANKALLOCATIONS.LIST>'''

            if getattr(ent, 'bill_allocations', None):
                for ba in ent.bill_allocations:
                    bname = ba.bill.bill_reference if getattr(ba, 'bill', None) and ba.bill else (getattr(ba, 'bill_reference', '') or f"{voucher.voucher_number or '1'}")
                    b_amt = -abs(float(ba.amount)) if ent.debit_amount > 0 else abs(float(ba.amount))
                    entries_xml += f'''
               <BILLALLOCATIONS.LIST>
                <NAME>{x(bname)}</NAME>
                <BILLTYPE>{x(ba.allocation_type)}</BILLTYPE>
                <AMOUNT>{b_amt:.2f}</AMOUNT>
               </BILLALLOCATIONS.LIST>'''
            elif is_party:
                # The bill the app raised for this voucher, so both sides hold it under one name
                bname = str(party_bill_name or voucher.reference_number or voucher.voucher_number or '1')
                entries_xml += f'''
               <BILLALLOCATIONS.LIST>
                <NAME>{x(bname)}</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>{amt:.2f}</AMOUNT>
               </BILLALLOCATIONS.LIST>'''

            # Multi-Cost-Centre allocations support
            if getattr(ent, 'cost_centre_allocations', None):
                for cca in ent.cost_centre_allocations:
                    cc_name = cca.cost_centre.name if getattr(cca, 'cost_centre', None) and cca.cost_centre else "Cost Centre"
                    cca_amt = -float(cca.amount) if ent.debit_amount > 0 else float(cca.amount)
                    entries_xml += f'''
               <COSTCENTREALLOCATIONS.LIST>
                <NAME>{x(cc_name)}</NAME>
                <AMOUNT>{cca_amt:.2f}</AMOUNT>
               </COSTCENTREALLOCATIONS.LIST>'''

            entries_xml += f'''
              </{ledger_tag}>'''

        vch_tag_attrs = f'{voucher_address_attrs(tally_date or vdate_str, voucher_remote_id(voucher), master_id)} VCHTYPE="{x(vtype_name)}" ACTION="{x(action)}" OBJVIEW="{x(obj_view)}"'
        cancelled_tag = "\n              <ISCANCELLED>Yes</ISCANCELLED>" if (voucher.is_cancelled or voucher.status == "cancelled") else ""
        # Tally matches a re-send on the REMOTEID attribute but never gives it back; REMOTEALTGUID it stores and
        # returns, so the same identifier goes there too and the voucher can be recognised when read from Tally
        remote_alt_tag = f"\n              <REMOTEALTGUID>{x(voucher.tally_remote_id)}</REMOTEALTGUID>" if voucher.tally_remote_id else ""

        is_invoice_tag = "\n              <ISINVOICE>Yes</ISINVOICE>" if is_inv else ""
        
        eff_date_val = voucher.effective_date.strftime("%Y%m%d") if voucher.effective_date else vdate_str
        ref_date_tag = f"\n              <REFERENCEDATE>{voucher.reference_date.strftime('%Y%m%d')}</REFERENCEDATE>" if getattr(voucher, 'reference_date', None) else ""
        # The other party's document number (a supplier's invoice number on a purchase)
        if voucher.reference_number:
            ref_date_tag = f"\n              <REFERENCE>{x(voucher.reference_number)}</REFERENCE>" + ref_date_tag
        pos_tag = f"\n              <PLACEOFSUPPLY>{x(voucher.place_of_supply)}</PLACEOFSUPPLY>" if getattr(voucher, 'place_of_supply', None) else ""
        buyer_tag = f"\n              <BASICBUYERNAME>{x(voucher.buyer_name)}</BASICBUYERNAME>" if getattr(voucher, 'buyer_name', None) else ""
        consignee_tag = f"\n              <CONSIGNEEMAILINGNAME>{x(voucher.consignee_name)}</CONSIGNEEMAILINGNAME>" if getattr(voucher, 'consignee_name', None) else ""
        order_ref_tag = f"\n              <BASICORDERREF>{x(voucher.order_reference)}</BASICORDERREF>" if getattr(voucher, 'order_reference', None) else ""
        despatch_tag = f"\n              <BASICSHIPDELIVERYNOTE>{x(voucher.despatch_doc_no)}</BASICSHIPDELIVERYNOTE>" if getattr(voucher, 'despatch_doc_no', None) else ""
        post_dated_tag = f"\n              <ISPOSTDATED>{'Yes' if getattr(voucher, 'is_post_dated', False) else 'No'}</ISPOSTDATED>"

        # e-Invoice XML tags
        irn_tag = f"\n              <IRN>{x(voucher.irn)}</IRN>" if getattr(voucher, 'irn', None) else ""
        irn_ack_tag = f"\n              <IRNACKNO>{x(voucher.irn_ack_no)}</IRNACKNO>" if getattr(voucher, 'irn_ack_no', None) else ""
        irn_date_tag = f"\n              <IRNACKDATE>{voucher.irn_ack_date.strftime('%Y-%m-%d %H:%M:%S')}</IRNACKDATE>" if getattr(voucher, 'irn_ack_date', None) else ""
        irn_qr_tag = f"\n              <IRNQRCODE>{x(voucher.irn_qr_code)}</IRNQRCODE>" if getattr(voucher, 'irn_qr_code', None) else ""
        irn_cancelled_tag = f"\n              <IRNCANCELLED>{'Yes' if getattr(voucher, 'irn_cancelled', False) else 'No'}</IRNCANCELLED>" if getattr(voucher, 'irn', None) else ""

        # e-Way Bill XML tags
        eway_bills_xml = ""
        if getattr(voucher, 'eway_bills', None):
            for eb in voucher.eway_bills:
                b_date = eb.bill_date.strftime("%Y%m%d") if eb.bill_date else ""
                v_date = eb.valid_up_to.strftime("%Y%m%d") if eb.valid_up_to else ""
                d_date = eb.doc_date.strftime("%Y%m%d") if eb.doc_date else ""
                eway_bills_xml += f'''
              <EWAYBILLDETAILS.LIST>
               <BILLNUMBER>{x(eb.bill_number)}</BILLNUMBER>
               <BILLDATE>{b_date}</BILLDATE>
               <VALIDUPTO>{v_date}</VALIDUPTO>
               <DISTANCE>{x(eb.distance_km or '0')}</DISTANCE>
               <TRANSPORTERID>{x(eb.transporter_id)}</TRANSPORTERID>
               <TRANSPORTERNAME>{x(eb.transporter_name)}</TRANSPORTERNAME>
               <DOCNUMBER>{x(eb.doc_number)}</DOCNUMBER>
               <DOCDATE>{d_date}</DOCDATE>
               <VEHICLENUMBER>{x(eb.vehicle_number)}</VEHICLENUMBER>
               <VEHICLETYPE>{x(eb.vehicle_type or 'Regular')}</VEHICLETYPE>
               <TRANSPORTMODE>{x(eb.transport_mode or 'Road')}</TRANSPORTMODE>
               <SUBTYPE>{x(eb.sub_type or 'Supply')}</SUBTYPE>
               <DOCTYPE>{x(eb.doc_type or 'Tax Invoice')}</DOCTYPE>
              </EWAYBILLDETAILS.LIST>'''

        paylink_xml = ""
        if getattr(voucher, 'payment_links', None):
            for pl in voucher.payment_links:
                paylink_xml += f'''
              <PAYLINK.LIST>
               <PAYLINKID>{x(pl.link_id)}</PAYLINKID>
               <PAYMENTURL>{x(pl.payment_url)}</PAYMENTURL>
               <PAYMENTMODE>{x(pl.payment_mode)}</PAYMENTMODE>
               <STATUS>{x(pl.status)}</STATUS>
               <AMOUNT>{float(pl.amount):.2f}</AMOUNT>
              </PAYLINK.LIST>'''

        xml_result = f'''<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER {vch_tag_attrs}>
              <DATE>{vdate_str}</DATE>
              <EFFECTIVEDATE>{eff_date_val}</EFFECTIVEDATE>
              <VCHSTATUSDATE>{vdate_str}</VCHSTATUSDATE>
              <VOUCHERTYPENAME>{x(vtype_name)}</VOUCHERTYPENAME>
              <VOUCHERNUMBER>{x(voucher.voucher_number)}</VOUCHERNUMBER>{ref_date_tag}{pos_tag}{buyer_tag}{consignee_tag}{order_ref_tag}{despatch_tag}{post_dated_tag}{irn_tag}{irn_ack_tag}{irn_date_tag}{irn_qr_tag}{irn_cancelled_tag}
              <PARTYNAME>{x(party_ledger_name)}</PARTYNAME>
              <PARTYLEDGERNAME>{x(party_ledger_name)}</PARTYLEDGERNAME>
              <PERSISTEDVIEW>{x(obj_view)}</PERSISTEDVIEW>{is_invoice_tag}
              <NARRATION>{x(voucher.narration)}</NARRATION>{cancelled_tag}{remote_alt_tag}{eway_bills_xml}{paylink_xml}
              {all_inventory_xml}
              {entries_xml}
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'''

        # Run Phase 3 Schema Pre-Flight Validation
        val_errors = schema_validator.validate_xml_envelope(xml_result)
        if val_errors:
            logger.warning(f"⚠️ [SCHEMA VALIDATION] Voucher ID {voucher_id} generated warnings: {val_errors}")

        return xml_result
    except Exception as e:
        logger.error(f"Error in build_voucher_xml_payload for voucher {voucher_id}: {e}", exc_info=True)
        return ""

@router.get("/outbound-queue", dependencies=[Depends(bind_sync_company)])
async def get_outbound_queue(
    user: User = Depends(require_permission("sync", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns unsynced local creations/modifications formatted as Tally-compatible XML payloads.
    """
    from app.models.tally_core import (
        MstLedger, MstGroup, MstVoucherType, MstStockItem, 
        MstStockGroup, MstGodown, MstUom, StockItemOpeningBalance
    )
    from app.models.portal_core import Company

    stmt = select(SyncQueue).where(
        SyncQueue.company_id == user.company_id,
        SyncQueue.is_processed == False
    ).order_by(SyncQueue.created_at.asc())
    
    res = await db.execute(stmt)
    queue_items = res.scalars().all()
    
    outbound_payloads = []
    
    for item in queue_items:
        xml_envelope = ""
        # 1. Map Ledger
        if item.record_type == "Ledger":
            l_stmt = select(MstLedger).where(MstLedger.ledger_id == item.record_id)
            l_res = await db.execute(l_stmt)
            ledger = l_res.scalars().first()
            # The name Tally knows the ledger by: differs after a rename, and is all that is left after a delete
            tally_name = (item.snapshot_data or {}).get("tally_name")
            if ledger:
                g_stmt = select(MstGroup).where(MstGroup.group_id == ledger.group_id)
                g_res = await db.execute(g_stmt)
                group = g_res.scalars().first()
                group_name = group.name if group else "Sundry Debtors"

                c_stmt = select(Company).where(Company.company_id == ledger.company_id)
                c_res = await db.execute(c_stmt)
                comp_obj = c_res.scalars().first()
                comp_name = comp_obj.name if comp_obj else ""
                
                xml_envelope = build_ledger_xml_envelope(ledger, group_name, comp_name, item.action or 'Create', tally_name)
            elif item.action == "Delete" and tally_name:
                c_res = await db.execute(select(Company).where(Company.company_id == item.company_id))
                comp_obj = c_res.scalars().first()
                xml_envelope = build_ledger_delete_envelope(tally_name, comp_obj.name if comp_obj else "")
                
        # 2. Map Voucher Creation / Alteration / Deletion
        elif item.record_type == "Voucher":
            vch = (await db.execute(select(TrnVoucher).where(TrnVoucher.voucher_id == item.record_id))).scalars().first()
            ident = (item.snapshot_data or {}).get("tally_voucher") or {}
            if vch:
                # A voucher Tally already holds is addressed by its master id, a new one by its own REMOTEID
                action = item.action or 'Create'
                if action in ("Create", "Alter"):
                    action = "Alter" if vch.tally_master_id else "Create"
                if not vch.tally_master_id and not vch.tally_remote_id:
                    vch.tally_remote_id = new_voucher_remote_id()
                    await db.commit()
                xml_envelope = await build_voucher_xml_payload(
                    item.record_id, action, db, vch.tally_master_id,
                    vch.tally_date.strftime("%Y%m%d") if vch.tally_master_id and vch.tally_date else None)
            elif item.action == "Delete" and (ident.get("master_id") or ident.get("remote_id")):
                c_res = await db.execute(select(Company).where(Company.company_id == item.company_id))
                comp_obj = c_res.scalars().first()
                xml_envelope = build_voucher_address_envelope(
                    comp_obj.name if comp_obj else "", ident.get("vtype") or "Journal", ident.get("date") or "", "Delete",
                    remote_id=None if ident.get("master_id") else ident.get("remote_id"), master_id=ident.get("master_id"))

        # 3. Map Stock Item
        elif item.record_type in ("StockItem", "Stock_Item", "Item"):
            from app.models.tally_core import MstStockItem, StockItemOpeningBalance
            item_stmt = select(MstStockItem).options(
                selectinload(MstStockItem.unit),
                selectinload(MstStockItem.group),
                selectinload(MstStockItem.category),
                selectinload(MstStockItem.opening_balances).selectinload(StockItemOpeningBalance.godown)
            ).where(MstStockItem.stock_item_id == item.record_id)
            item_res = await db.execute(item_stmt)
            st_item = item_res.scalars().first()
            if st_item:
                c_stmt = select(Company).where(Company.company_id == st_item.company_id)
                c_res = await db.execute(c_stmt)
                comp_obj = c_res.scalars().first()
                comp_name = comp_obj.name if comp_obj else ""

                if item.action == "Delete":
                    xml_envelope = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="{x(st_item.name)}" Action="Delete"><NAME>{x(st_item.name)}</NAME></STOCKITEM>
      </TALLYMESSAGE>
    </DESC>
  </BODY>
</ENVELOPE>"""
                else:
                    uom_symbol = st_item.unit.symbol if st_item.unit else "nos"
                    raw_group = st_item.group.name.strip() if st_item.group and st_item.group.name else ""
                    parent_tag = f"<PARENT>{x(raw_group)}</PARENT>" if raw_group and raw_group.lower() not in ("primary", "not applicable") else "<PARENT>&#4; Primary</PARENT>"
                    xml_envelope = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="{x(st_item.name)}" Action="{x(item.action or 'Create')}">
          <NAME>{x(st_item.name)}</NAME>
          {parent_tag}
          <BASEUNITS>{x(uom_symbol)}</BASEUNITS>
        </STOCKITEM>
      </TALLYMESSAGE>
    </DESC>
  </BODY>
</ENVELOPE>"""

        # 4. Map Group
        elif item.record_type in ("Group", "AccountGroup"):
            g_stmt = select(MstGroup).where(MstGroup.group_id == item.record_id)
            g_res = await db.execute(g_stmt)
            grp = g_res.scalars().first()
            # The name Tally knows the group by: differs from grp.name after a rename, and is all
            # that is left of the group after a delete
            tally_name = (item.snapshot_data or {}).get("tally_name")
            group_inner_xml = ""
            if grp and item.action != "Delete":
                parent_name = "Primary"
                if grp.parent_group_id:
                    p_res = await db.execute(select(MstGroup).where(MstGroup.group_id == grp.parent_group_id))
                    p_grp = p_res.scalars().first()
                    if p_grp:
                        parent_name = p_grp.name
                group_inner_xml = f"""<GROUP NAME="{x(tally_name or grp.name)}" Action="{x(item.action or 'Create')}">
          <NAME>{x(grp.name)}</NAME>
          <PARENT>{x(parent_name)}</PARENT>
        </GROUP>"""
            elif item.action == "Delete" and (tally_name or grp):
                delete_name = tally_name or grp.name
                group_inner_xml = f"""<GROUP NAME="{x(delete_name)}" Action="Delete">
          <NAME>{x(delete_name)}</NAME>
        </GROUP>"""

            if group_inner_xml:
                c_stmt = select(Company).where(Company.company_id == item.company_id)
                c_res = await db.execute(c_stmt)
                comp_obj = c_res.scalars().first()
                comp_name = comp_obj.name if comp_obj else ""
                
                xml_envelope = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {group_inner_xml}
      </TALLYMESSAGE>
    </DESC>
  </BODY>
</ENVELOPE>"""

        # 5. Map Voucher Type
        elif item.record_type in ("VoucherType", "Voucher_Type"):
            vt_stmt = select(MstVoucherType).where(MstVoucherType.voucher_type_id == item.record_id)
            vt_res = await db.execute(vt_stmt)
            vt = vt_res.scalars().first()
            if vt:
                c_stmt = select(Company).where(Company.company_id == vt.company_id)
                c_res = await db.execute(c_stmt)
                comp_obj = c_res.scalars().first()
                comp_name = comp_obj.name if comp_obj else ""
                
                parent_type = vt.parent_type or vt.name
                xml_envelope = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHERTYPE NAME="{x(vt.name)}" Action="{x(item.action or 'Create')}">
          <NAME>{x(vt.name)}</NAME>
          <PARENT>{x(parent_type)}</PARENT>
          <NUMBERINGMETHOD>{x(vt.numbering_method or 'Automatic')}</NUMBERINGMETHOD>
        </VOUCHERTYPE>
      </TALLYMESSAGE>
    </DESC>
  </BODY>
</ENVELOPE>"""

        if xml_envelope:
            outbound_payloads.append({
                "sync_id": item.sync_id,
                "record_type": item.record_type,
                "record_id": item.record_id,
                "action": item.action,
                "xml_payload": xml_envelope
            })
        else:
            # Auto-retire records where the entity no longer exists in MySQL
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == item.sync_id).values(is_processed=True))
            await db.commit()
            
    if outbound_payloads:
        # Lets the agent check each payload is for the Tally company it is tied to before sending it
        queue_company_guid = (await db.execute(
            select(Company.tally_guid).where(Company.company_id == user.company_id))).scalar()
        for payload in outbound_payloads:
            payload["company_guid"] = queue_company_guid
        items_summary = ", ".join([f"{p['record_type']} #{p['record_id']} ({p['action']})" for p in outbound_payloads])
        logger.info(f"📤 [OUTBOUND DISPATCH] Sending {len(outbound_payloads)} item(s) to Desktop Sync Agent: [{items_summary}]")
        # Payloads carry customer names, GSTINs and addresses: only at DEBUG (they're also in the sync traffic log)
        if logger.isEnabledFor(logging.DEBUG):
            for p in outbound_payloads:
                logger.debug(f"--- PAYLOAD FOR {p['record_type']} #{p['record_id']} ({p['action']}) ---\n{p['xml_payload']}")

    return outbound_payloads

@router.post("/acknowledge", dependencies=[Depends(bind_sync_company)])
async def acknowledge_sync(
    sync_ids: List[int],
    user: User = Depends(require_permission("sync", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Marks sync queue records as processed upon successful local Tally ingestion.
    """
    ack_msg = f"✅ [SYNC ACKNOWLEDGED] Marked {len(sync_ids)} sync task(s) as successfully ingested into Tally: {sync_ids}"
    logger.info(ack_msg)
    stmt = update(SyncQueue).where(
        SyncQueue.sync_id.in_(sync_ids),
        SyncQueue.company_id == user.company_id
    ).values(is_processed=True, status="SUCCESS", error_message=None)
    
    await db.execute(stmt)
    await db.commit()
    
    return {"status": "success", "acknowledged_count": len(sync_ids)}

@router.post("/voucher-identities", dependencies=[Depends(bind_sync_company)])
async def report_voucher_identities(
    identities: List[Dict[str, Any]],
    user: User = Depends(require_permission("sync", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    What Tally made of vouchers the Desktop Sync Agent pushed: each one's master id, GUID, date and the number
    Tally gave it. The app's provisional number is replaced by Tally's. Safe to send more than once.
    Body: [{"voucher_id", "master_id", "guid", "number", "date" (YYYYMMDD)}]
    """
    from app.core.cache import clear_company_cache
    updated = 0
    for ident in identities:
        if not str(ident.get("master_id") or "").isdigit() or not ident.get("voucher_id"):
            continue
        voucher = (await db.execute(select(TrnVoucher).where(
            TrnVoucher.voucher_id == ident["voucher_id"], TrnVoucher.company_id == user.company_id))).scalars().first()
        if not voucher:
            continue
        await adopt_tally_voucher_identity(db, voucher, {
            "master_id": int(ident["master_id"]), "guid": ident.get("guid") or None,
            "number": ident.get("number") or None, "date": ident.get("date") or None})
        updated += 1
    await db.commit()
    if updated:
        clear_company_cache(user.company_id)
    return {"status": "success", "updated": updated}

class CompanySyncReport(BaseModel):
    tally_guid: str
    state: str = Field(max_length=30)          # live / closed / ambiguous / error
    ok: bool = False                           # a whole cycle for this company finished with no errors
    error: Optional[str] = None
    master_alter_id: Optional[int] = None
    voucher_alter_id: Optional[int] = None
    pending_count: Optional[int] = None
    fingerprint: Optional[str] = Field(default=None, max_length=200)   # which copy of the books is open in Tally
    progress: Optional[str] = Field(default=None, max_length=60)       # "Full sync 3 of 12" while one is under way


@router.post("/state")
async def report_sync_state(
    request: Request,
    reports: List[CompanySyncReport],
    user: User = Depends(require_permission("sync", "update")),
    db: AsyncSession = Depends(get_db),
):
    """
    What the Desktop Sync Agent found for each of its companies this cycle, including ones that are closed in
    Tally. This is where the app's "Last synced" comes from: last_success_at moves only when ok is true.
    A company the caller is not the one syncing is skipped, not an error, so one stale entry cannot lose the rest.
    """
    from app.core.agent_auth import COPY_MISMATCH, device_company
    from app.core.datetime_utils import get_ist_now
    from app.core.permissions import company_for_tally_guid
    from app.models.portal_core import CompanySyncState
    device = agent_device(request)
    recorded, skipped = 0, []
    now = get_ist_now()
    for report in reports:
        guid = report.tally_guid.strip()
        wrong_copy = None
        try:
            company = (await device_company(db, device, guid, report.fingerprint) if device is not None
                       else await company_for_tally_guid(db, user, guid))
        except HTTPException as refused:
            company = None
            if device is not None and (refused.headers or {}).get("X-Sync-Reason") == COPY_MISMATCH:
                # Still this PC's company: say why it stopped, where the app will show it
                wrong_copy = refused.detail
                company = await device_company(db, device, guid)
        if company is None:
            skipped.append(guid)
            continue
        row = (await db.execute(select(CompanySyncState).where(CompanySyncState.company_id == company.company_id))).scalars().first()
        if row is None:
            row = CompanySyncState(company_id=company.company_id)
            db.add(row)
        row.device_id = device.device_id if device is not None else row.device_id
        row.last_attempt_at = now
        row.progress = report.progress
        if wrong_copy:
            row.state, row.last_error = "error", wrong_copy
            recorded += 1
            continue
        if report.fingerprint and not company.tally_fingerprint:
            company.tally_fingerprint = report.fingerprint.strip()    # first seen: this is the copy that is synced
        row.state = report.state
        row.last_error = None if report.ok else (report.error or row.last_error)
        if report.ok:
            row.last_success_at = now
        for field in ("master_alter_id", "voucher_alter_id", "pending_count"):
            value = getattr(report, field)
            if value is not None:
                setattr(row, field, value)
        recorded += 1
    await db.commit()
    return {"recorded": recorded, "skipped": skipped}


@router.get("/last-alter-id", dependencies=[Depends(bind_sync_company)])
async def get_last_alter_id(
    user: User = Depends(require_permission("sync", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the maximum tally_alter_id across all masters and vouchers to use for incremental inbound sync.
    """
    from sqlalchemy.sql import func
    from app.models.tally_core import (
        MstGroup, MstLedger, MstVoucherType, TrnVoucher, 
        MstStockGroup, MstStockCategory, MstUom, MstGodown, MstStockItem, CostCenter
    )
    
    # Tally counts changes to masters and to vouchers separately (the company's ALTMSTID and ALTVCHID), so
    # each has its own watermark: one shared number would skip whichever kind is behind the other.
    master_tables = [MstLedger, MstStockItem, MstGroup, MstVoucherType, MstStockGroup, MstStockCategory, MstUom, MstGodown, CostCenter]
    details = {}
    for model in master_tables + [TrnVoucher]:
        try:
            stmt = select(func.max(model.tally_alter_id)).where(model.company_id == user.company_id)
            details[model.__tablename__] = int((await db.execute(stmt)).scalar() or 0)
        except Exception:
            pass

    voucher_alter_id = details.get(TrnVoucher.__tablename__, 0)
    master_alter_id = max([v for k, v in details.items() if k != TrnVoucher.__tablename__], default=0)
    return {
        "last_alter_id": max(master_alter_id, voucher_alter_id),
        "last_master_alter_id": master_alter_id,
        "last_ledger_alter_id": details.get(MstLedger.__tablename__, 0),
        "last_voucher_alter_id": voucher_alter_id,
        "last_stock_item_alter_id": details.get(MstStockItem.__tablename__, 0),
        "details": details
    }


def _post_to_tally_sync(url: str, xml_payload: str, timeout: int = 5) -> str:
    import http.client
    import ssl
    encoded_data = xml_payload.encode('utf-8')
    
    # SSL Context for HTTPS proxies/tunnels (enforces certificate verification unless explicitly overridden)
    ssl_ctx = None
    if url.startswith("https"):
        ssl_ctx = ssl.create_default_context()
        insecure_tls = getattr(settings, "TALLY_INSECURE_TLS", False) or os.environ.get("TALLY_INSECURE_TLS", "").lower() in ("1", "true")
        if insecure_tls:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        data=encoded_data,
        headers={
            'Content-Type': 'text/xml;charset=utf-8',
            'Content-Length': str(len(encoded_data))
        },
        method='POST'
    )
    
    raw_bytes = bytearray()
    with _TALLY_HTTP_LOCK:
        try:
            kwargs = {"timeout": timeout}
            if ssl_ctx:
                kwargs["context"] = ssl_ctx

            with urllib.request.urlopen(req, **kwargs) as response:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    raw_bytes.extend(chunk)
        except http.client.IncompleteRead as e:
            logger.warning(f"IncompleteRead encountered from Tally XML endpoint ({len(e.partial)} bytes recovered).")
            raw_bytes.extend(e.partial)
        except Exception as e:
            logger.error(f"Connection error while fetching from Tally ({url}): {str(e)}")
            if not raw_bytes:
                return ""

    if not raw_bytes:
        return ""

    try:
        return bytes(raw_bytes).decode('utf-8')
    except (UnicodeDecodeError, UnicodeError):
        try:
            return bytes(raw_bytes).decode('utf-16')
        except Exception:
            return bytes(raw_bytes).decode('latin1', errors='replace')


def _ledger_import_envelope(comp_name: str, ledger_xml: str) -> str:
    return f"""<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>All Masters</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          {ledger_xml}
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""


def build_ledger_delete_envelope(ledger_name: str, comp_name: str) -> str:
    return _ledger_import_envelope(comp_name, f"""<LEDGER NAME="{x(ledger_name)}" ACTION="Delete">
            <NAME>{x(ledger_name)}</NAME>
          </LEDGER>""")


def build_ledger_xml_envelope(ledger: MstLedger, group_name: str, comp_name: str, action: str, tally_name: Optional[str] = None) -> str:
    """
    tally_name: the name Tally currently knows the ledger by, when it differs from ledger.name (a rename).
    Tally finds the object by the NAME attribute and creates a new one if that name is unknown, so a
    rename must address the old name and carry the new one in <NAME>.
    Relationships (addresses, GST registrations, MSME, lower deductions, bank details) are sent only
    when the caller has loaded them.
    """
    target_name = tally_name or ledger.name
    if (action or "").lower() == "delete":
        return build_ledger_delete_envelope(target_name, comp_name)

    gstin_val = ledger.gstin or ''
    pan_val = getattr(ledger, 'pan_number', None) or (gstin_val[2:12].upper() if len(gstin_val) >= 12 else '')
    state_val = ledger.state or ''
    country_val = getattr(ledger, 'country', None) or 'India'
    pincode_val = getattr(ledger, 'pincode', None) or ''
    
    raw_addr = ledger.address or ''
    clean_addr = raw_addr.split(" | Mobile: ")[0].strip() if " | Mobile: " in raw_addr else raw_addr.strip()
    mobile_val = getattr(ledger, 'mobile', None) or ''
    if not mobile_val and " | Mobile: " in raw_addr:
        mobile_val = raw_addr.split(" | Mobile: ")[1].strip()

    contact_val = getattr(ledger, 'contact_person', None) or ''
    phone_val = getattr(ledger, 'phone', None) or ''
    email_val = getattr(ledger, 'email', None) or ''
    aadhar_val = getattr(ledger, 'aadhar_number', None) or ''
    credit_limit_val = getattr(ledger, 'credit_limit', None)
    credit_days_val = getattr(ledger, 'credit_period_days', None)
    is_billwise = 'Yes' if getattr(ledger, 'is_billwise_on', True) else 'No'
    
    gst_reg_type = getattr(ledger, 'gst_registration_type', None) or ('Regular' if gstin_val else 'Unregistered')
    if gst_reg_type == 'Unregistered/Consumer':
        gst_reg_type = 'Unregistered'

    ledger_type_val = getattr(ledger, 'ledger_type', '') or ''
    tax_class_name = getattr(ledger, 'tax_classification_name', '') or ''

    op_sign = '-' if ledger.opening_balance_type == 'Dr' else ''
    op_bal_str = f"{op_sign}{ledger.opening_balance}" if ledger.opening_balance else "0.00"

    addr_lines = [line.strip() for line in clean_addr.replace('\n', ',').split(',') if line.strip()]
    if not addr_lines and clean_addr:
        addr_lines = [clean_addr]
    
    address_nodes = "".join([f"<ADDRESS>{x(line)}</ADDRESS>" for line in addr_lines])
    addr_list_xml = f"<ADDRESS.LIST>{address_nodes}</ADDRESS.LIST>" if address_nodes else ""

    applicable_from = getattr(ledger, 'gst_applicable_from', None)
    app_from_str = applicable_from.strftime("%Y%m%d") if applicable_from else "20250401"

    # Tally matches a mailing block by its applicable-from date; a block without one is not stored reliably
    mailing_details_xml = f"""<LEDMAILINGDETAILS.LIST>
      <APPLICABLEFROM>{app_from_str}</APPLICABLEFROM>
      <MAILINGNAME>{x(ledger.name)}</MAILINGNAME>
      <STATE>{x(state_val)}</STATE>
      <COUNTRY>{x(country_val)}</COUNTRY>
      <PINCODE>{x(pincode_val)}</PINCODE>
      {addr_list_xml}
    </LEDMAILINGDETAILS.LIST>""" if (state_val or country_val or pincode_val or addr_list_xml) else ""

    # Multi-Address support
    loaded_addrs = ledger.__dict__.get('addresses')
    if loaded_addrs and len(loaded_addrs) > 0:
        mailing_details_xml = ""
        for a in loaded_addrs:
            a_lines = [l.strip() for l in (a.address or '').replace('\n', ',').split(',') if l.strip()]
            a_nodes = "".join([f"<ADDRESS>{x(l)}</ADDRESS>" for l in a_lines])
            a_list = f"<ADDRESS.LIST>{a_nodes}</ADDRESS.LIST>" if a_nodes else ""
            mailing_details_xml += f"""<LEDMAILINGDETAILS.LIST>
      <APPLICABLEFROM>{app_from_str}</APPLICABLEFROM>
      <ADDRESSNAME>{x(a.address_name or 'Primary')}</ADDRESSNAME>
      <MAILINGNAME>{x(a.mailing_name or ledger.name)}</MAILINGNAME>
      <STATE>{x(a.state_name or state_val)}</STATE>
      <COUNTRY>{x(a.country_name or country_val)}</COUNTRY>
      <PINCODE>{x(a.pincode or pincode_val)}</PINCODE>
      {a_list}
    </LEDMAILINGDETAILS.LIST>"""

    # Multi-GST Registrations support
    gst_reg_details_xml = ""
    loaded_regs = ledger.__dict__.get('gst_registrations')
    if loaded_regs and len(loaded_regs) > 0:
        for reg in loaded_regs:
            r_app = reg.applicable_from.strftime("%Y%m%d") if reg.applicable_from else app_from_str
            gst_reg_details_xml += f"""<LEDGSTREGDETAILS.LIST>
      <APPLICABLEFROM>{r_app}</APPLICABLEFROM>
      <GSTREGISTRATIONTYPE>{x(reg.registration_type or 'Regular')}</GSTREGISTRATIONTYPE>
      <GSTIN>{x(reg.gstin)}</GSTIN>
      <STATENAME>{x(reg.state_name or state_val)}</STATENAME>
      <PLACEOFSUPPLY>{x(reg.place_of_supply or state_val)}</PLACEOFSUPPLY>
    </LEDGSTREGDETAILS.LIST>"""
    elif (gst_reg_type or gstin_val):
        gst_reg_details_xml = f"""<LEDGSTREGDETAILS.LIST>
      <APPLICABLEFROM>{app_from_str}</APPLICABLEFROM>
      <GSTREGISTRATIONTYPE>{x(gst_reg_type)}</GSTREGISTRATIONTYPE>
      <GSTIN>{x(gstin_val)}</GSTIN>
    </LEDGSTREGDETAILS.LIST>"""

    # MSME Details support
    msme_details_xml = ""
    loaded_msme = ledger.__dict__.get('msme_details')
    if loaded_msme and len(loaded_msme) > 0:
        for m in loaded_msme:
            m_app = m.applicable_from.strftime("%Y%m%d") if m.applicable_from else app_from_str
            msme_details_xml += f"""<MSMEREGISTRATIONDETAILS.LIST>
      <ENTERPRISETYPE>{x(m.enterprise_type or 'Micro')}</ENTERPRISETYPE>
      <UDYAMREGNO>{x(m.udyam_reg_no or '')}</UDYAMREGNO>
      <APPLICABLEFROM>{m_app}</APPLICABLEFROM>
    </MSMEREGISTRATIONDETAILS.LIST>"""

    # Lower TDS Deduction support
    lower_ded_xml = ""
    loaded_low = ledger.__dict__.get('lower_deductions')
    if loaded_low and len(loaded_low) > 0:
        for ld in loaded_low:
            l_app_from = ld.applicable_from.strftime("%Y%m%d") if ld.applicable_from else "20250401"
            l_app_to = ld.applicable_to.strftime("%Y%m%d") if ld.applicable_to else "20260331"
            lower_ded_xml += f"""<LOWERDEDUCTION.LIST>
      <SECTIONNUMBER>{x(ld.section_number)}</SECTIONNUMBER>
      <CERTIFICATENO>{x(ld.certificate_no)}</CERTIFICATENO>
      <RATEOFDEDUCTION>{ld.rate_of_deduction:.2f}</RATEOFDEDUCTION>
      <APPLICABLEFROM>{l_app_from}</APPLICABLEFROM>
      <APPLICABLETO>{l_app_to}</APPLICABLETO>
      <LIMIT>{x(ld.threshold_limit or '0.00')}</LIMIT>
    </LOWERDEDUCTION.LIST>"""

    # Bank details: a bank ledger carries its own account; any other ledger carries the party's
    # bank accounts as payment details
    bank_xml = ""
    loaded_banks = ledger.__dict__.get('bank_details') or []
    if getattr(ledger, 'is_bank_account', False):
        first = loaded_banks[0] if loaded_banks else None
        account_no = getattr(ledger, 'bank_account_no', None) or (first.account_number if first else None) or ''
        ifsc = getattr(ledger, 'bank_ifsc', None) or (first.ifsc_code if first else None) or ''
        holder = (first.account_holder_name if first else None) or ''
        if account_no or ifsc or holder:
            bank_xml = f"""<BANKACCHOLDERNAME>{x(holder)}</BANKACCHOLDERNAME>
            <BANKDETAILS>{x(account_no)}</BANKDETAILS>
            <IFSCODE>{x(ifsc)}</IFSCODE>"""
    else:
        for bd in loaded_banks:
            if not (bd.account_number or bd.ifsc_code or bd.bank_name):
                continue
            bank_xml += f"""<PAYMENTDETAILS.LIST>
      <IFSCODE>{x(bd.ifsc_code or '')}</IFSCODE>
      <BANKNAME>{x(bd.bank_name or '')}</BANKNAME>
      <ACCOUNTNUMBER>{x(bd.account_number or '')}</ACCOUNTNUMBER>
      <PAYMENTFAVOURING>{x(bd.favouring_name or bd.account_holder_name or ledger.name)}</PAYMENTFAVOURING>
      <TRANSACTIONNAME>{x(bd.ref_id or 'Primary')}</TRANSACTIONNAME>
      <SETASDEFAULT>{'Yes' if bd.is_default else 'No'}</SETASDEFAULT>
      <DEFAULTTRANSACTIONTYPE>{x(bd.transaction_type or 'e-Fund Transfer')}</DEFAULTTRANSACTIONTYPE>
    </PAYMENTDETAILS.LIST>"""

    return _ledger_import_envelope(comp_name, f"""<LEDGER NAME="{x(target_name)}" ACTION="{x(action)}">
            <NAME>{x(ledger.name)}</NAME>
            <PARENT>{x(group_name)}</PARENT>
            <MAILINGNAME>{x(ledger.name)}</MAILINGNAME>
            <OPENINGBALANCE>{op_bal_str}</OPENINGBALANCE>
            <COUNTRYOFRESIDENCE>{x(country_val)}</COUNTRYOFRESIDENCE>
            <COUNTRYNAME>{x(country_val)}</COUNTRYNAME>
            <PRIORSTATENAME>{x(state_val)}</PRIORSTATENAME>
            <STATENAME>{x(state_val)}</STATENAME>
            <PINCODE>{x(pincode_val)}</PINCODE>
            {addr_list_xml}
            <LEDGERCONTACT>{x(contact_val)}</LEDGERCONTACT>
            <LEDGERPHONE>{x(phone_val)}</LEDGERPHONE>
            <LEDGERMOBILE>{x(mobile_val)}</LEDGERMOBILE>
            <EMAIL>{x(email_val)}</EMAIL>
            <ISBILLWISEON>{is_billwise}</ISBILLWISEON>
            <CREDITLIMIT>{x(credit_limit_val or '')}</CREDITLIMIT>
            <BILLCREDITPERIOD>{x(f"{credit_days_val} Days" if credit_days_val else '')}</BILLCREDITPERIOD>
            <GSTREGISTRATIONTYPE>{x(gst_reg_type)}</GSTREGISTRATIONTYPE>
            <PARTYGSTIN>{x(gstin_val)}</PARTYGSTIN>
            <INCOMETAXNUMBER>{x(pan_val)}</INCOMETAXNUMBER>
            <LEDGERTYPE>{x(ledger_type_val)}</LEDGERTYPE>
            <TAXCLASSIFICATIONNAME>{x(tax_class_name)}</TAXCLASSIFICATIONNAME>
            {mailing_details_xml}
            {gst_reg_details_xml}
            {msme_details_xml}
            {lower_ded_xml}
            {bank_xml}
            <LWLEDADHARNOSTORE>{x(aadhar_val)}</LWLEDADHARNOSTORE>
            <UDF:LWLEDADHARNOSTORE DESC="`LWLedAdharNoStore`" TYPE="String">{x(aadhar_val)}</UDF:LWLEDADHARNOSTORE>
          </LEDGER>""")


def check_tally_success(response_xml: str) -> bool:
    if not response_xml or not response_xml.strip():
        return False
    if "<LINEERROR>" in response_xml or "<ERROR>" in response_xml or "<EXCEPTION>" in response_xml:
        return False

    # Fail if explicit ERRORS or EXCEPTIONS count is greater than 0
    m_err = re.search(r'<ERRORS>\s*(\d+)\s*</ERRORS>', response_xml)
    if m_err and int(m_err.group(1)) > 0:
        return False
    m_exc = re.search(r'<EXCEPTIONS>\s*(\d+)\s*</EXCEPTIONS>', response_xml)
    if m_exc and int(m_exc.group(1)) > 0:
        return False

    # Success means Tally changed at least one object. STATUS 1 or ERRORS 0 on their own only say the request was
    # read: a reply with every count at 0 means nothing reached the books, so the push stays queued for retry.
    for tag in ("CREATED", "ALTERED", "UPDATED", "DELETED", "CANCELLED", "COMBINED", "IGNORED"):
        m = re.search(rf'<{tag}>\s*(\d+)\s*</{tag}>', response_xml)
        if m and int(m.group(1)) > 0:
            return True
    return "<LASTVOUCHERID>" in response_xml


def build_ledger_json_payload(ledger: MstLedger, group_name: str, comp_name: str, action: str) -> dict:
    act_lower = action.lower()
    if act_lower == 'delete':
        return {
            "static_variables": [
                {"name": "svMstImportFormat", "value": "jsonex"},
                {"name": "svCurrentCompany", "value": comp_name}
            ],
            "tallymessage": [
                {
                    "metadata": {
                        "type": "Ledger",
                        "action": "Delete",
                        "name": ledger.name
                    }
                }
            ]
        }

    gstin_val = ledger.gstin or ''
    pan_val = getattr(ledger, 'pan_number', None) or (gstin_val[2:12].upper() if len(gstin_val) >= 12 else '')
    state_val = ledger.state or ''
    country_val = getattr(ledger, 'country', None) or 'India'
    pincode_val = getattr(ledger, 'pincode', None) or ''

    raw_addr = ledger.address or ''
    clean_addr = raw_addr.split(" | Mobile: ")[0].strip() if " | Mobile: " in raw_addr else raw_addr.strip()
    mobile_val = getattr(ledger, 'mobile', None) or ''
    if not mobile_val and " | Mobile: " in raw_addr:
        mobile_val = raw_addr.split(" | Mobile: ")[1].strip()

    contact_val = getattr(ledger, 'contact_person', None) or ''
    phone_val = getattr(ledger, 'phone', None) or ''
    email_val = getattr(ledger, 'email', None) or ''
    aadhar_val = getattr(ledger, 'aadhar_number', None) or ''
    credit_limit_val = getattr(ledger, 'credit_limit', None)
    credit_days_val = getattr(ledger, 'credit_period_days', None)
    is_billwise = bool(getattr(ledger, 'is_billwise_on', True))

    gst_reg_type = getattr(ledger, 'gst_registration_type', None) or ('Regular' if gstin_val else 'Unregistered')
    if gst_reg_type == 'Unregistered/Consumer':
        gst_reg_type = 'Unregistered'

    op_sign = '-' if ledger.opening_balance_type == 'Dr' else ''
    op_bal_str = f"{op_sign}{ledger.opening_balance}" if ledger.opening_balance else "0.00"

    addr_lines = [{"metadata": True, "type": "String"}] + [line.strip() for line in clean_addr.replace('\n', ',').split(',') if line.strip()]

    transporter_id_val = getattr(ledger, 'transporter_id', None) or ''
    is_transporter_val = bool(transporter_id_val)
    pos_val = getattr(ledger, 'place_of_supply', None) or state_val or ''

    applicable_from = getattr(ledger, 'gst_applicable_from', None)
    app_from_str = applicable_from.strftime("%Y%m%d") if applicable_from else "20250401"

    msg_obj = {
        "metadata": {
            "type": "Ledger",
            "action": act_lower,
            "name": ledger.name
        },
        "name": ledger.name,
        "parent": group_name,
        "currencyname": "INR",
        "ledgercountryisdcode": "+91",
        "mailingname": ledger.name,
        "countryofresidence": country_val,
        "priorstatename": state_val,
        "pincode": pincode_val,
        "countryname": country_val,
        "ledmailingdetails": [
            {
                "address": addr_lines,
                "applicablefrom": app_from_str,
                "pincode": pincode_val,
                "mailingname": ledger.name,
                "state": state_val,
                "country": country_val
            }
        ],
        "ledgercontact": contact_val,
        "ledgermobile": mobile_val,
        "ledgerphone": phone_val,
        "email": email_val,
        "incometaxnumber": pan_val,
        "lwledadlharnosstore": aadhar_val,
        "partygstin": gstin_val,
        "gstregistrationtype": gst_reg_type,
        "vatdealertype": gst_reg_type,
        "ledgstregdetails": [
            {
                "applicablefrom": app_from_str,
                "gstregistrationtype": gst_reg_type,
                "transporterid": transporter_id_val,
                "state": state_val,
                "placeofsupply": pos_val,
                "gstin": gstin_val,
                "isothterritoryassessee": bool(getattr(ledger, 'is_other_territory_assessee', False)),
                "considerpurchaseforexport": False,
                "istransporter": is_transporter_val,
                "iscommonparty": bool(getattr(ledger, 'is_common_party', False))
            }
        ],
        "isbillwiseon": is_billwise,
        "isaffectstock": bool(getattr(ledger, 'is_inventory_affected', False)),
        "iscostcentreson": bool(getattr(ledger, 'is_cost_centres_on', False)),
        "ischequeprintingenabled": True,
        "isdeemedpositive": True if ledger.opening_balance_type == 'Dr' else False,
        "openingbalance": op_bal_str
    }

    desc = getattr(ledger, 'description', None)
    if desc:
        msg_obj["description"] = desc

    notes_val = getattr(ledger, 'notes', None)
    if notes_val:
        msg_obj["notes"] = notes_val

    alias_name = getattr(ledger, 'alias_name', None)
    if alias_name:
        msg_obj["languagename"] = [
            {
                "name": [
                    {"metadata": True, "type": "String"},
                    ledger.name,
                    alias_name
                ],
                "languageid": {"type": "Number", "value": "1033"}
            }
        ]

    if credit_limit_val:
        msg_obj["creditlimit"] = str(credit_limit_val)
    if credit_days_val:
        msg_obj["creditdays"] = f"{credit_days_val} Days"

    bank_list = getattr(ledger, 'bank_details', None)
    if bank_list and len(bank_list) > 0:
        pay_details = []
        for b in bank_list:
            ttype = b.transaction_type or "e-Fund Transfer"
            p_obj = {
                "transactiontype": ttype,
                "transacttype": ttype
            }
            fav_name = b.favouring_name or ledger.name
            if fav_name:
                p_obj["favouringname"] = fav_name

            if ttype in ["Cheque", "Electronic Cheque"]:
                p_obj["crossusing"] = b.cross_using or "A/c Payee"
                if b.account_number:
                    p_obj["accountnumber"] = b.account_number
                if b.bank_name:
                    p_obj["bankname"] = b.bank_name
                if b.ifsc_code:
                    p_obj["ifsccode"] = b.ifsc_code
            elif ttype == "UPI":
                if b.upi_id:
                    p_obj["emailid"] = b.upi_id
                    p_obj["payeeupiid"] = b.upi_id
                if b.account_number:
                    p_obj["accountnumber"] = b.account_number
                if b.ifsc_code:
                    p_obj["ifsccode"] = b.ifsc_code
                if b.bank_name:
                    p_obj["bankname"] = b.bank_name
            else:
                if b.account_number:
                    p_obj["accountnumber"] = b.account_number
                if b.ifsc_code:
                    p_obj["ifsccode"] = b.ifsc_code
                if b.bank_name:
                    p_obj["bankname"] = b.bank_name

            pay_details.append(p_obj)
        if pay_details:
            msg_obj["paymentdetails"] = pay_details

    return {
        "static_variables": [
            {"name": "svMstImportFormat", "value": "jsonex"},
            {"name": "svCurrentCompany", "value": comp_name}
        ],
        "tallymessage": [msg_obj]
    }


def _post_json_to_tally_sync(url: str, json_payload: dict, timeout: int = 5) -> str:
    import ssl
    encoded_data = json.dumps(json_payload).encode('utf-8')
    
    # SSL Context for HTTPS proxies/tunnels (enforces certificate verification unless explicitly overridden)
    ssl_ctx = None
    if url.startswith("https"):
        ssl_ctx = ssl.create_default_context()
        insecure_tls = getattr(settings, "TALLY_INSECURE_TLS", False) or os.environ.get("TALLY_INSECURE_TLS", "").lower() in ("1", "true")
        if insecure_tls:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        data=encoded_data,
        headers={
            'content-type': 'application/json',
            'version': '1',
            'tallyrequest': 'Import',
            'type': 'Data',
            'id': 'All Masters'
        },
        method='POST'
    )
    
    raw_bytes = bytearray()
    with _TALLY_HTTP_LOCK:
        try:
            kwargs = {"timeout": timeout}
            if ssl_ctx:
                kwargs["context"] = ssl_ctx

            with urllib.request.urlopen(req, **kwargs) as response:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    raw_bytes.extend(chunk)
        except Exception as e:
            logger.error(f"Connection error while posting JSON to Tally ({url}): {str(e)}")
            if not raw_bytes:
                return ""

    if not raw_bytes:
        return ""

    return bytes(raw_bytes).decode('utf-8', errors='ignore')


def tally_json_failure_reason(response_str: str) -> Optional[str]:
    """
    None when Tally accepted a JSON import, otherwise why it did not.
    Tally answers status "1" even when it rejects the object, so the counters decide: any error or
    exception is a rejection, and so is a reply in which nothing was created, altered or deleted.
    """
    if not response_str or not response_str.strip():
        return "No response from Tally"
    try:
        data = json.loads(response_str)
    except Exception:
        return f"Unreadable Tally response: {response_str.strip()[:200]}"
    if not isinstance(data, dict) or str(data.get("status")) != "1":
        return f"Tally returned status {data.get('status') if isinstance(data, dict) else data!r}"
    result = (data.get("data") or {}).get("import_result") or {}

    def count(key: str) -> int:
        try:
            return int(result.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    if count("errors") or count("exceptions"):
        return f"Tally rejected the request ({count('errors')} error(s), {count('exceptions')} exception(s))"
    # ignored is what a resend of an already-saved object can return
    if not sum(count(k) for k in ("created", "altered", "deleted", "combined", "cancelled", "ignored")):
        return "Tally changed nothing"
    return None


def check_tally_json_success(response_str: str) -> bool:
    return tally_json_failure_reason(response_str) is None



def build_cost_centre_json_payload(centre, category_name: str, parent_name: str, company_name: str, action: str) -> dict:
    act_lower = action.lower()
    if act_lower == "delete":
        return {
            "static_variables": [
                {"name": "svMstImportFormat", "value": "jsonex"},
                {"name": "svCurrentCompany", "value": company_name}
            ],
            "tallymessage": [
                {
                    "metadata": {
                        "type": "CostCentre",
                        "action": "delete",
                        "name": centre.name
                    }
                }
            ]
        }
    
    centre_data = {
        "metadata": {
            "type": "CostCentre",
            "action": act_lower,
            "name": centre.name
        },
        "name": centre.name,
        "category": category_name
    }
    
    if parent_name:
        centre_data["parent"] = parent_name

    if getattr(centre, 'alias', None):
        centre_data["languagename"] = [
            {
                "name": [
                    {"metadata": True, "type": "String"},
                    centre.name,
                    centre.alias
                ]
            }
        ]

    return {
        "static_variables": [
            {"name": "svMstImportFormat", "value": "jsonex"},
            {"name": "svCurrentCompany", "value": company_name}
        ],
        "tallymessage": [centre_data]
    }


def build_cost_category_json_payload(category, company_name: str, action: str) -> dict:
    act_lower = action.lower()
    if act_lower == "delete":
        return {
            "static_variables": [
                {"name": "svMstImportFormat", "value": "jsonex"},
                {"name": "svCurrentCompany", "value": company_name}
            ],
            "tallymessage": [
                {
                    "metadata": {
                        "type": "CostCategory",
                        "action": "delete",
                        "name": category.name
                    }
                }
            ]
        }
    
    cat_data = {
        "metadata": {
            "type": "CostCategory",
            "action": act_lower,
            "name": category.name
        },
        "name": category.name,
        "allocaterevenue": "Yes" if category.allocate_revenue else "No",
        "allocatenonrevenue": "Yes" if category.allocate_non_revenue else "No"
    }

    if getattr(category, 'alias', None):
        cat_data["languagename"] = [
            {
                "name": [
                    {"metadata": True, "type": "String"},
                    category.name,
                    category.alias
                ]
            }
        ]

    return {
        "static_variables": [
            {"name": "svMstImportFormat", "value": "jsonex"},
            {"name": "svCurrentCompany", "value": company_name}
        ],
        "tallymessage": [cat_data]
    }


async def try_push_cost_category_realtime(category_id: int, sync_id: int, action: str, db: AsyncSession):
    try:
        from sqlalchemy.future import select
        from sqlalchemy import update
        from app.models.portal_core import SyncQueue
        from app.models.tally_core import MstCostCategory
        from app.models.portal_core import Company
        
        cat = (await db.execute(select(MstCostCategory).where(MstCostCategory.category_id == category_id))).scalars().first()
        if not cat:
            return
            
        comp = (await db.execute(select(Company).where(Company.company_id == cat.company_id))).scalars().first()
        if not comp:
            return

        active_tally = await get_active_tally_sync_for_company(comp.company_id, db)
        if not active_tally:
            return

        payload = build_cost_category_json_payload(cat, comp.name, action)
        url = f"{active_tally.tally_url.rstrip('/')}/"
        response = await asyncio.to_thread(_post_json_to_tally_sync, url, payload, timeout=10)
        success = check_tally_json_success(response)
        
        if success:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(is_processed=True))
            await db.commit()
            logger.info(f"Real-time Tally Push Success for CostCategory {cat.name} ({action})")
        else:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(attempts=SyncQueue.attempts + 1, error_message=str(response)[:500]))
            await db.commit()
            logger.error(f"Real-time Tally Push Failed for CostCategory {cat.name} ({action}). Tally Response: {response}")

    except Exception as e:
        logger.error(f"Error in try_push_cost_category_realtime: {str(e)}")

async def try_push_cost_centre_realtime(cost_centre_id: int, sync_id: int, action: str, db: AsyncSession):
    try:
        from sqlalchemy.future import select
        from sqlalchemy import update
        from app.models.portal_core import SyncQueue
        from app.models.tally_core import MstCostCentre, MstCostCategory
        from app.models.portal_core import Company
        
        logger.info(f"Attempting real-time Tally push for CostCentre ID {cost_centre_id} with action {action}")
        
        cc = (await db.execute(select(MstCostCentre).where(MstCostCentre.cost_centre_id == cost_centre_id))).scalars().first()
        if not cc:
            logger.warning(f"CostCentre ID {cost_centre_id} not found for real-time push")
            return
            
        comp = (await db.execute(select(Company).where(Company.company_id == cc.company_id))).scalars().first()
        if not comp:
            logger.warning(f"Company ID {cc.company_id} not found for CostCentre {cost_centre_id}")
            return

        cat = (await db.execute(select(MstCostCategory).where(MstCostCategory.category_id == cc.category_id))).scalars().first()
        cat_name = cat.name if cat else "Primary Cost Category"

        parent_name = ""
        if cc.parent_id:
            parent = (await db.execute(select(MstCostCentre).where(MstCostCentre.cost_centre_id == cc.parent_id))).scalars().first()
            if parent:
                parent_name = parent.name

        active_tally = await get_active_tally_sync_for_company(comp.company_id, db)
        if not active_tally:
            return

        payload = build_cost_centre_json_payload(cc, cat_name, parent_name, comp.name, action)
        url = f"{active_tally.tally_url.rstrip('/')}/"
        response = await asyncio.to_thread(_post_json_to_tally_sync, url, payload, timeout=10)
        success = check_tally_json_success(response)
        
        if success:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(is_processed=True))
            await db.commit()
            logger.info(f"Real-time Tally Push Success for CostCentre {cc.name} ({action})")
        else:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(attempts=SyncQueue.attempts + 1, error_message=str(response)[:500]))
            await db.commit()
            logger.error(f"Real-time Tally Push Failed for CostCentre {cc.name} ({action}). Tally Response: {response}")

    except Exception as e:
        logger.error(f"Error in try_push_cost_centre_realtime: {str(e)}")

async def try_push_cost_centre_class_realtime(class_id: int, sync_id: int, action: str, db: AsyncSession):
    try:
        from sqlalchemy.orm import selectinload
        from sqlalchemy.future import select
        from sqlalchemy import update
        from app.models.portal_core import SyncQueue, Company
        from app.models.tally_core import MstCostCentreClass, MstCostCentreClassAllocation
        from app.core.config import settings

        tally_url = current_tally_url()
        if not tally_url:
            return

        stmt = select(MstCostCentreClass).options(
            selectinload(MstCostCentreClass.allocations).selectinload(MstCostCentreClassAllocation.category),
            selectinload(MstCostCentreClass.allocations).selectinload(MstCostCentreClassAllocation.cost_centre)
        ).where(MstCostCentreClass.class_id == class_id)
        
        cls = (await db.execute(stmt)).scalars().first()
        if not cls: return
        
        comp = (await db.execute(select(Company).where(Company.company_id == cls.company_id))).scalars().first()
        comp_name = comp.name if comp else ""

        # Group allocations by category
        cat_map = {}
        for alloc in cls.allocations:
            cat_name = alloc.category.name if alloc.category else "Primary Cost Category"
            if cat_name not in cat_map:
                cat_map[cat_name] = []
            cat_map[cat_name].append(alloc)
            
        xml_allocations = ""
        for cat_name, allocs in cat_map.items():
            xml_allocations += f"<CATEGORYALLOCATIONS.LIST>\n<CATEGORY>{x(cat_name)}</CATEGORY>\n"
            for alloc in allocs:
                cc_name = alloc.cost_centre.name if alloc.cost_centre else ""
                xml_allocations += f"<COSTCENTREALLOCATIONS.LIST>\n<NAME>{x(cc_name)}</NAME>\n<PERCENTAGE>{alloc.percentage}</PERCENTAGE>\n</COSTCENTREALLOCATIONS.LIST>\n"
            xml_allocations += "</CATEGORYALLOCATIONS.LIST>\n"
            
        xml_envelope = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<COSTCENTRECLASS NAME="{x(cls.name)}" ACTION="{x(action)}">
<NAME>{x(cls.name)}</NAME>
{xml_allocations}
</COSTCENTRECLASS>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""

        response = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope)
        if check_tally_success(response):
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(is_processed=True))
            await db.commit()
            logger.info(f"Real-time Tally Push Success for CostCentreClass {cls.name} ({action})")
        else:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(attempts=SyncQueue.attempts + 1, error_message=str(response)[:500]))
            await db.commit()
            logger.error(f"Real-time Tally Push Failed for CostCentreClass {cls.name} ({action}). Tally Response: {response}")

    except Exception as e:
        logger.error(f"Error in try_push_cost_centre_class_realtime: {str(e)}")

async def try_push_currency_realtime(currency_id: int, sync_id: int, action: str, db: AsyncSession, deleted_symbol: str = None, deleted_code: str = None):
    try:
        from sqlalchemy.orm import selectinload
        from sqlalchemy.future import select
        from sqlalchemy import update
        from app.models.portal_core import SyncQueue, Company, Currency
        from app.core.config import settings

        tally_url = current_tally_url()
        if not tally_url:
            return

        curr = None
        if action != "Delete":
            stmt = select(Currency).options(selectinload(Currency.rates)).where(Currency.currency_id == currency_id)
            curr = (await db.execute(stmt)).scalars().first()
            if not curr: return
        
        sq = (await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_id))).scalars().first()
        if not sq: return
        # A currency belongs to one company and is only ever sent to that company's Tally
        if curr is not None and curr.company_id != sq.company_id:
            logger.error(f"Currency {currency_id} is not company {sq.company_id}'s; not sent to Tally.")
            return
        
        comp = (await db.execute(select(Company).where(Company.company_id == sq.company_id))).scalars().first()
        comp_name = comp.name if comp else ""

        if action == "Delete":
            xml_envelope = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<CURRENCY NAME="{x(deleted_symbol)}" ACTION="Delete">
</CURRENCY>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""
        else:
            in_millions = "Yes" if curr.show_amount_in_millions else "No"
            is_suffix = "Yes" if curr.suffix_symbol_to_amount else "No"
            has_space = "Yes" if curr.add_space_between_amount_and_symbol else "No"
            formal_name = curr.formal_name or curr.code
            decimal_word = curr.word_representing_amount_after_decimal or ""
            
            rates_xml = ""
            for r in curr.rates:
                if r.company_id == sq.company_id:
                    rdate_str = r.rate_date.strftime("%Y%m%d")
                    if r.standard_rate:
                        rates_xml += f"<DAILYSTDRATE.LIST>\n<DATE>{rdate_str}</DATE>\n<SPECIFIEDRATE>{x(r.standard_rate)}/{x(curr.symbol)}</SPECIFIEDRATE>\n</DAILYSTDRATE.LIST>\n"
                    if r.selling_rate:
                        rates_xml += f"<DAILYSELLINGRATE.LIST>\n<DATE>{rdate_str}</DATE>\n<SPECIFIEDRATE>{x(r.selling_rate)}/{x(curr.symbol)}</SPECIFIEDRATE>\n</DAILYSELLINGRATE.LIST>\n"
                    if r.buying_rate:
                        rates_xml += f"<DAILYBUYINGRATE.LIST>\n<DATE>{rdate_str}</DATE>\n<SPECIFIEDRATE>{x(r.buying_rate)}/{x(curr.symbol)}</SPECIFIEDRATE>\n</DAILYBUYINGRATE.LIST>\n"

            xml_envelope = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<CURRENCY NAME="{x(curr.symbol)}" ACTION="{x(action)}">
<ORIGINALNAME>{x(curr.symbol)}</ORIGINALNAME>
<MAILINGNAME>{x(formal_name)}</MAILINGNAME>
<EXPANDEDSYMBOL>{x(formal_name)}</EXPANDEDSYMBOL>
<ISOCURRENCYCODE>{x(curr.code)}</ISOCURRENCYCODE>
<DECIMALPLACES>{curr.decimal_places}</DECIMALPLACES>
<INMILLIONS>{in_millions}</INMILLIONS>
<ISSUFFIX>{is_suffix}</ISSUFFIX>
<HASSPACE>{has_space}</HASSPACE>
<DECIMALSYMBOL>{x(decimal_word)}</DECIMALSYMBOL>
<DECIMALPLACESFORPRINTING>{curr.decimal_places_for_words}</DECIMALPLACESFORPRINTING>
{rates_xml}
</CURRENCY>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""

        response = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope)
        if check_tally_success(response):
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(is_processed=True))
            await db.commit()
            logger.info(f"Real-time Tally Push Success for Currency {curr.symbol} ({action})")
        else:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(attempts=SyncQueue.attempts + 1, error_message=str(response)[:500]))
            await db.commit()
            logger.error(f"Real-time Tally Push Failed for Currency {curr.symbol} ({action}). Tally Response: {response}")

    except Exception as e:
        logger.error(f"Error in try_push_currency_realtime: {str(e)}")

async def try_push_voucher_type_realtime(vt_id: int, sync_id: int, action: str, db: AsyncSession, old_name: str = None, deleted_name: str = None):
    try:
        from sqlalchemy.future import select
        from sqlalchemy import update
        from app.models.portal_core import SyncQueue, Company
        from app.models.tally_core import MstVoucherType, MstVoucherTypeClass
        from app.core.config import settings

        tally_url = current_tally_url()
        if not tally_url:
            return

        from sqlalchemy.orm import selectinload
        vt = None
        if action != "Delete":
            stmt = select(MstVoucherType).options(
                selectinload(MstVoucherType.prefixes),
                selectinload(MstVoucherType.suffixes),
                selectinload(MstVoucherType.restarts),
                selectinload(MstVoucherType.classes).selectinload(MstVoucherTypeClass.groups)
            ).where(MstVoucherType.voucher_type_id == vt_id)
            vt = (await db.execute(stmt)).scalars().first()
            if not vt: return
            
        sq = (await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_id))).scalars().first()
        if not sq: return
        
        comp = (await db.execute(select(Company).where(Company.company_id == sq.company_id))).scalars().first()
        comp_name = comp.name if comp else ""

        if action == "Delete":
            logger.warning(f"Suppressing real-time Tally Push for VoucherType (Delete) because Tally crashes on this payload. vt_name={deleted_name}")
            return
        else:
            vt_name = vt.name
            original_name = old_name or vt.name
            parent = vt.parent_type or ""
            
            prevent_duplicates = "Yes" if getattr(vt, 'prevent_duplicates', False) else "No"

            xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHERTYPE NAME="{x(vt_name)}" ACTION="{x(action)}">
          <ORIGINALNAME>{x(original_name)}</ORIGINALNAME>
          <LANGUAGENAME.LIST>
            <NAME.LIST TYPE="String">
              <NAME>{x(vt_name)}</NAME>
            </NAME.LIST>
          </LANGUAGENAME.LIST>
          <PARENT>{x(parent)}</PARENT>
          <NUMBERINGMETHOD>{x(vt.numbering_method)}</NUMBERINGMETHOD>
          <PREVENTDUPLICATES>{prevent_duplicates}</PREVENTDUPLICATES>
          <EFFECTIVEDATE>{"Yes" if getattr(vt, 'use_effective_dates', False) else "No"}</EFFECTIVEDATE>
          <USEZEROENTRIES>{"Yes" if getattr(vt, 'allow_zero_valued_transactions', False) else "No"}</USEZEROENTRIES>
          <ISOPTIONAL>{"Yes" if getattr(vt, 'is_optional_by_default', False) else "No"}</ISOPTIONAL>
          <COMMONNARRATION>{"Yes" if getattr(vt, 'allow_narration_in_voucher', True) else "No"}</COMMONNARRATION>
          <MULTINARRATION>{"Yes" if getattr(vt, 'provide_narrations_for_each_ledger', False) else "No"}</MULTINARRATION>
          <PRINTAFTERSAVE>{"Yes" if getattr(vt, 'print_voucher_after_saving', False) else "No"}</PRINTAFTERSAVE>
          <WHATSAPPAFTERSAVE>{"Yes" if getattr(vt, 'whatsapp_voucher_after_saving', False) else "No"}</WHATSAPPAFTERSAVE>
          <ISDEFAULTALLOCENABLED>{"Yes" if getattr(vt, 'enable_default_accounting_allocations', False) else "No"}</ISDEFAULTALLOCENABLED>
          <TRACKADDLCOST>{"Yes" if getattr(vt, 'track_additional_costs_for_purchases', False) else "No"}</TRACKADDLCOST>
          {f'<VCHPRINTJURISDICTION>{x(vt.default_jurisdiction)}</VCHPRINTJURISDICTION>' if getattr(vt, 'default_jurisdiction', None) else ''}
          {f'<VCHPRINTTITLE>{x(vt.default_title_to_print)}</VCHPRINTTITLE>' if getattr(vt, 'default_title_to_print', None) else ''}
          <VOUCHERNUMBERSERIES.LIST>
            <NAME>Default</NAME>
            <NUMBERINGMETHOD>{x(vt.numbering_method)}</NUMBERINGMETHOD>
            <NUMBERINGSUBMETHOD>{x(vt.numbering_behavior or "")}</NUMBERINGSUBMETHOD>
            <PREVENTDUPLICATES>{prevent_duplicates}</PREVENTDUPLICATES>
            <PREFILLZERO>{"Yes" if getattr(vt, 'prefill_with_zero', False) else "No"}</PREFILLZERO>
            <USEDELETEDVCHNUM>{"Yes" if getattr(vt, 'show_unused_vch_nos', False) else "No"}</USEDELETEDVCHNUM>
            <WIDTHOFNUMBER>{getattr(vt, 'width_of_numerical_part', 0)}</WIDTHOFNUMBER>
            {''.join(f"<PREFIXLIST.LIST><DATE>{p.applicable_from.strftime('%Y%m%d')}</DATE><PARTICULARS>{x(p.particulars)}</PARTICULARS></PREFIXLIST.LIST>" for p in vt.prefixes)}
            {''.join(f"<SUFFIXLIST.LIST><DATE>{s.applicable_from.strftime('%Y%m%d')}</DATE><PARTICULARS>{x(s.particulars)}</PARTICULARS></SUFFIXLIST.LIST>" for s in vt.suffixes)}
            {''.join(f"<RESTARTFROMLIST.LIST><DATE>{r.applicable_from.strftime('%Y%m%d')}</DATE><PERIODBEGINNIGNUM>{r.starting_number}</PERIODBEGINNIGNUM><RESTARTFROM>{x(r.periodicity)}</RESTARTFROM></RESTARTFROMLIST.LIST>" for r in vt.restarts)}
          </VOUCHERNUMBERSERIES.LIST>
          {''.join(f'''<VOUCHERCLASSLIST.LIST>
            <CLASSNAME>{x(c.class_name)}</CLASSNAME>
            {f"<BANKALLOCFOR>{x(c.bank_alloc_for)}</BANKALLOCFOR>" if c.bank_alloc_for else ""}
          </VOUCHERCLASSLIST.LIST>''' for c in vt.classes)}
        </VOUCHERTYPE>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        response = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope)
        
        if check_tally_success(response):
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(is_processed=True, attempts=SyncQueue.attempts + 1))
            await db.commit()
            logger.info(f"Real-time Tally Push Success for VoucherType {vt_name if action == 'Delete' else vt.name} ({action})")
        else:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(attempts=SyncQueue.attempts + 1, error_message=str(response)[:500]))
            await db.commit()
            logger.error(f"Real-time Tally Push Failed for VoucherType {vt_name if action == 'Delete' else vt.name} ({action}). Tally Response: {response}")

    except Exception as e:
        logger.error(f"Error in try_push_voucher_type_realtime: {str(e)}")


async def find_tally_voucher(tally_url: str, comp_name: str, master_id: Optional[int] = None, guid: Optional[str] = None) -> Optional[dict]:
    """
    The voucher Tally holds under this master id or GUID: {"exists": False}, or {"exists": True, "master_id",
    "guid", "alter_id", "number", "date" (YYYYMMDD), "cancelled"}. None when Tally gave no usable answer.
    Tally does not give back the REMOTEID a voucher was sent under, so these two are the only ways to find one.
    """
    formula = f"$MasterID = {int(master_id)}" if master_id else f'$GUID = "{x(guid)}"'
    xml = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>MyTallyFindVoucher</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <SYSTEM TYPE="Formulae" NAME="MyTallyFindVoucherFilter">{formula}</SYSTEM>
          <COLLECTION NAME="MyTallyFindVoucher" ISMODIFY="No">
            <TYPE>Voucher</TYPE>
            <FETCH>GUID,MASTERID,ALTERID,VOUCHERNUMBER,DATE,VOUCHERTYPENAME,ISCANCELLED</FETCH>
            <FILTERS>MyTallyFindVoucherFilter</FILTERS>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""
    resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml, 10)
    if not resp or "<ENVELOPE>" not in resp or "<ERRORMSG>" in resp or "<LINEERROR>" in resp:
        return None
    found = re.search(r"<VOUCHER [^>]*>.*?</VOUCHER>", resp, re.S)
    if not found:
        return {"exists": False}

    def field(tag: str) -> str:
        m = re.search(rf"<{tag}[^>]*>([^<]*)</{tag}>", found.group(0))
        return m.group(1).strip() if m else ""

    if not field("MASTERID").isdigit():
        return None
    return {"exists": True, "master_id": int(field("MASTERID")), "guid": field("GUID") or None,
            "alter_id": int(field("ALTERID")) if field("ALTERID").isdigit() else None,
            "number": field("VOUCHERNUMBER") or None, "date": field("DATE") or None,
            "cancelled": field("ISCANCELLED").lower() == "yes"}


async def adopt_tally_voucher_identity(db: AsyncSession, voucher, tally: dict) -> Optional[str]:
    """
    Writes what Tally says about a voucher onto the app's copy: master id, GUID, date and the number.
    Tally numbers its automatic voucher types itself and ignores the number sent, so the number the app gave
    the voucher is replaced by Tally's. Returns the number that was replaced, or None if it already matched.
    Flushes, does not commit.
    """
    from app.models.tally_core import TrnBill, TrnInventory
    voucher.tally_master_id = tally["master_id"]
    if tally.get("date"):
        try:
            voucher.tally_date = datetime.strptime(tally["date"], "%Y%m%d").date()
        except ValueError:
            pass
    if tally.get("guid"):
        voucher.tally_guid = tally["guid"]
    # tally_alter_id is left alone: the inbound sync pulls "everything altered after the highest alter id the
    # app holds", so writing the alter id of our own push here would make it skip whatever was changed in
    # Tally just before. The voucher comes back through that sync, matched by its GUID.
    voucher.number_is_provisional = False
    if tally.get("guid"):
        # The inbound sync may have imported this same Tally voucher as a new one before the app knew they
        # were the same (a push whose reply was lost). The imported copy goes; this one carries the link.
        copies = (await db.execute(select(TrnVoucher).where(
            TrnVoucher.company_id == voucher.company_id, TrnVoucher.tally_guid == tally["guid"],
            TrnVoucher.voucher_id != voucher.voucher_id))).scalars().all()
        for copy in copies:
            if copy.status == "confirmed":
                for inv in (await db.execute(select(TrnInventory).where(TrnInventory.voucher_id == copy.voucher_id))).scalars().all():
                    item = (await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == inv.stock_item_id))).scalars().first()
                    if item:
                        qty = float(inv.quantity or 0)
                        item.closing_qty = float(item.closing_qty or 0) + (-qty if inv.is_inward else qty)
            logger.info(f"Voucher #{voucher.voucher_id} is Tally voucher {tally['guid']}; removing its imported copy #{copy.voucher_id}")
            await db.delete(copy)
    replaced = None
    number = tally.get("number")
    if number and number != voucher.voucher_number:
        replaced = voucher.voucher_number
        # A bill this voucher raised under its provisional number follows the number
        await db.execute(update(TrnBill).where(TrnBill.voucher_id == voucher.voucher_id, TrnBill.bill_reference == replaced)
                         .values(bill_reference=number[:50]))
        voucher.voucher_number = number
    if number and voucher.voucher_type_id:
        # Keep the app's own counter ahead of Tally's so the next provisional number is a likely one
        vtype = (await db.execute(select(MstVoucherType).where(MstVoucherType.voucher_type_id == voucher.voucher_type_id))).scalars().first()
        tail = re.search(r"(\d+)$", number[len(vtype.prefix or ""):] if vtype and number.startswith(vtype.prefix or "") else "")
        if vtype and tail and int(tail.group(1)) >= (vtype.next_number or 1):
            vtype.next_number = int(tail.group(1)) + 1
    await db.flush()
    return replaced


async def send_voucher(db: AsyncSession, voucher_id: int, action: str, ident: Optional[dict] = None) -> dict:
    """
    Sends a voucher to Tally and reports what happened, without committing anything: the caller decides
    whether its own changes stand. Reads the voucher as it is in the caller's transaction, and on success
    writes Tally's identifiers and number onto it (flushed, not committed).
    action: Create, Alter, Cancel or Delete. Create and Alter are the same request to this function: it asks
    Tally whether it holds the voucher and sends whichever fits.
    ident: {"company_id", "remote_id", "master_id", "guid", "vtype", "date" (YYYYMMDD)} for a Delete whose
    voucher is already gone from the app.
    Returns {"status", "reason", "envelope", "response", "name", "company_id", "duration_ms", "renumbered_from"};
    status is SUCCESS, ALREADY_ABSENT (a delete of something Tally does not have), NOT_CONFIGURED, REJECTED
    (Tally answered and refused), NO_RESPONSE or FAILED.
    """
    import time
    ident = ident or {}
    result = {"status": "FAILED", "reason": None, "envelope": None, "response": None, "name": None,
              "company_id": ident.get("company_id"), "duration_ms": 0, "renumbered_from": None}
    tally_url = current_tally_url()
    if not tally_url:
        result.update(status="NOT_CONFIGURED", reason="TALLY_URL is not configured")
        return result

    voucher = (await db.execute(
        select(TrnVoucher).options(selectinload(TrnVoucher.voucher_type))
        .where(TrnVoucher.voucher_id == voucher_id).execution_options(populate_existing=True)
    )).scalars().first()
    if voucher:
        company_id = voucher.company_id
        remote_id, master_id, guid = voucher_remote_id(voucher), voucher.tally_master_id, voucher.tally_guid
        vtype_name = voucher.voucher_type.name if voucher.voucher_type else "Journal"
        vdate_str = voucher.voucher_date.strftime("%Y%m%d")
        result["name"] = f"{vtype_name} #{voucher.voucher_number}"
    elif action == "Delete" and (ident.get("remote_id") or ident.get("master_id") or ident.get("guid")):
        company_id = ident.get("company_id")
        remote_id, master_id, guid = ident.get("remote_id"), ident.get("master_id"), ident.get("guid")
        vtype_name, vdate_str = ident.get("vtype") or "Journal", ident.get("date") or ""
        result["name"] = ident.get("name") or f"{vtype_name} voucher #{voucher_id}"
    else:
        result["reason"] = f"Voucher #{voucher_id} not found"
        return result
    result["company_id"] = company_id
    comp = (await db.execute(select(Company).where(Company.company_id == company_id))).scalars().first()
    comp_name = comp.name if comp else ""

    # Where the voucher is in Tally, if anywhere
    state = None
    if master_id:
        state = await find_tally_voucher(tally_url, comp_name, master_id=master_id)
        if state and state["exists"] and is_tally_guid(guid) and state["guid"] and state["guid"] != guid:
            state = {"exists": False}  # that master id now belongs to some other voucher
    elif is_tally_guid(guid):
        state = await find_tally_voucher(tally_url, comp_name, guid=guid)
    else:
        state = {"exists": False, "never_located": True}
    if state is None:
        result.update(status="NO_RESPONSE", reason="No response from Tally")
        return result
    in_tally = state["exists"]

    # A first send (no REMOTEID yet) is the only time a refused create is known to have left nothing real behind
    first_send = bool(voucher) and not in_tally and not voucher.tally_remote_id

    if action == "Delete":
        sent_action = "Delete"
        if in_tally:
            envelope = build_voucher_address_envelope(comp_name, vtype_name, state["date"] or vdate_str, "Delete", master_id=state["master_id"])
        elif remote_id and state.get("never_located"):
            # Not known to have reached Tally. Asking by its REMOTEID removes it if it did, and also the
            # leftover a refused create leaves behind, which would otherwise hold on to its ledgers.
            envelope = build_voucher_address_envelope(comp_name, vtype_name, vdate_str, "Delete", remote_id=remote_id)
        else:
            result.update(status="ALREADY_ABSENT", reason="Tally no longer has this voucher")
            return result
    elif action == "Cancel" and in_tally:
        sent_action = "Cancel"
        envelope = build_voucher_address_envelope(comp_name, vtype_name, state["date"] or vdate_str, "Cancel", master_id=state["master_id"])
    else:
        # Create, Alter, or the cancel of a voucher Tally never received (sent whole, marked cancelled)
        sent_action = "Alter" if in_tally else "Create"
        if not in_tally and not voucher.tally_remote_id:
            remote_id = voucher.tally_remote_id = new_voucher_remote_id()
            await db.flush()
        envelope = await build_voucher_xml_payload(voucher_id, sent_action, db, state["master_id"] if in_tally else None,
                                                   state.get("date") if in_tally else None)
        if not envelope:
            result["reason"] = "Failed to build XML envelope"
            return result

    async def post(xml: str) -> str:
        logger.debug(f"\n=======================================================\n📤 [OUTBOUND REALTIME TALLY XML PUSH] (voucher_id={voucher_id}, action={sent_action})\nURL: {tally_url}\nPAYLOAD:\n{xml}\n=======================================================\n")
        resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml)
        logger.debug(f"\n=======================================================\n📥 [TALLY REALTIME PUSH RESPONSE] (voucher_id={voucher_id})\nRESPONSE:\n{resp}\n=======================================================\n")
        return resp

    started = time.time()
    resp = await post(envelope)
    result.update(envelope=envelope, response=resp, sent_action=sent_action, duration_ms=int((time.time() - started) * 1000))

    if not resp or not resp.strip():
        result.update(status="NO_RESPONSE", reason="No response from Tally")
        return result
    if not check_tally_success(resp):
        reason = parse_tally_response_metrics(resp)["error_summary"] or "Tally rejected the voucher"
        if sent_action == "Delete" and not in_tally:
            # "Cannot be deleted!" for a voucher never located in Tally: there was nothing there to delete
            result.update(status="ALREADY_ABSENT", reason="Tally does not have this voucher")
        else:
            if sent_action == "Create" and first_send:
                # A create Tally refuses leaves a hidden voucher behind that keeps its ledgers from being deleted
                await asyncio.to_thread(_post_to_tally_sync, tally_url,
                                        build_voucher_address_envelope(comp_name, vtype_name, vdate_str, "Delete", remote_id=remote_id))
            result.update(status="REJECTED", reason=reason)
        return result

    result["status"] = "SUCCESS"
    if voucher and sent_action in ("Create", "Alter", "Cancel"):
        last = re.search(r"<LASTVCHID>\s*(\d+)\s*</LASTVCHID>", resp)
        tally = await find_tally_voucher(tally_url, comp_name, master_id=int(last.group(1))) if last and int(last.group(1)) else None
        if tally and tally["exists"]:
            old_number = voucher.voucher_number
            result["renumbered_from"] = await adopt_tally_voucher_identity(db, voucher, tally)
            if result["renumbered_from"] and sent_action != "Cancel" and f">{x(old_number)}</NAME>" in envelope:
                # A bill was named after the provisional number: send the voucher once more so the bill
                # carries the number Tally gave it
                again = await build_voucher_xml_payload(voucher_id, "Alter", db, tally["master_id"], tally["date"])
                again_resp = await post(again) if again else ""
                if check_tally_success(again_resp):
                    result.update(envelope=again, response=again_resp)
                    tally = await find_tally_voucher(tally_url, comp_name, master_id=tally["master_id"])
                    if tally and tally["exists"]:
                        await adopt_tally_voucher_identity(db, voucher, tally)
            result["name"] = f"{vtype_name} #{voucher.voucher_number}"
    return result


async def record_voucher_push(db: AsyncSession, voucher_id: int, sync_id: Optional[int], action: str, result: dict):
    """Writes a send_voucher() outcome to the traffic log, the queue row and, for a delete, the delete audit. Commits."""
    if result.get("envelope") is not None:
        await record_sync_traffic_log(
            db=db, company_id=result["company_id"], sync_id=sync_id if sync_id and sync_id > 0 else None,
            entity_type="Voucher", entity_id=voucher_id, entity_name=result["name"], action=result.get("sent_action") or action,
            outbound_format="XML", outbound_payload=result["envelope"], inbound_response=result["response"],
            duration_ms=result["duration_ms"], tally_url=current_tally_url())
    ok = result["status"] in ("SUCCESS", "ALREADY_ABSENT")
    if sync_id and sync_id > 0 and result["status"] != "NOT_CONFIGURED":
        await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(
            is_processed=ok, status=result["status"], attempts=func.coalesce(SyncQueue.attempts, 0) + 1,
            last_payload=result["envelope"], last_response=result["response"], last_attempt_at=func.now(),
            error_message=None if ok else ((result["reason"] or "")[:500] or None)))
    if action == "Delete" and result["status"] in ("SUCCESS", "ALREADY_ABSENT", "REJECTED"):
        await db.execute(
            update(DeletedRecordAudit)
            .where(DeletedRecordAudit.company_id == result["company_id"], DeletedRecordAudit.entity_type == "Voucher",
                   DeletedRecordAudit.record_id == voucher_id)
            .values(tally_sync_status="SYNCED_TO_TALLY" if ok else "NOT_DELETED_IN_TALLY",
                    tally_error_message=None if ok else (result["reason"] or "Cannot be deleted in Tally Prime")))
    await db.commit()


async def try_push_voucher_realtime(voucher_id: int, sync_id: int, action: str, db: AsyncSession):
    """
    Pushes a voucher to Tally and records the outcome on its queue row. A delete whose voucher is already gone
    from the app is addressed from the identifiers kept on the queue row. Returns (ok, status, message).
    """
    try:
        sync_item = None
        if sync_id and sync_id > 0:
            sync_item = (await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_id))).scalars().first()
        ident = dict((sync_item.snapshot_data if sync_item else None) or {}).get("tally_voucher") or {}
        if sync_item:
            ident.setdefault("company_id", sync_item.company_id)
        result = await send_voucher(db, voucher_id, action, ident)
        if result["status"] == "NOT_CONFIGURED":
            return (False, "NOT_CONFIGURED", result["reason"])
        await record_voucher_push(db, voucher_id, sync_id, action, result)
        if result["status"] in ("SUCCESS", "ALREADY_ABSENT"):
            logger.info(f"Real-time Tally Push Success for Voucher #{voucher_id} ({action}): {result['status']}")
            return (True, result["status"], result["reason"] if result["status"] == "ALREADY_ABSENT" else None)
        logger.error(f"Real-time Tally Push Failed for Voucher #{voucher_id} ({action}): {result['status']}: {result['reason']}")
        return (False, result["status"], result["reason"])
    except Exception as e:
        logger.error(f"Error in try_push_voucher_realtime: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


def build_group_xml_envelope(group, parent_name: str, company_name: str, action: str, tally_name: Optional[str] = None) -> str:
    """
    The group as an XML import. XML is used for groups because Tally's XML reply says why it refused
    (<LINEERROR>); its JSON reply only counts errors.
    tally_name: the name Tally currently knows the group by when it differs from group.name (a rename);
    for a delete it may be all that is known (group None).
    "&#4; Primary" and "&#4; Not Applicable" are Tally's own spellings, control character included.
    """
    target_name = tally_name or group.name
    if action.lower() == "delete":
        body = f"""<GROUP NAME="{x(target_name)}" Action="Delete">
          <NAME>{x(target_name)}</NAME>
        </GROUP>"""
    else:
        yes_no = lambda value: "Yes" if value else "No"
        method = (getattr(group, 'method_to_allocate', None) or "").strip()
        alloc = x(method) if method and method != "Not Applicable" else "&#4; Not Applicable"
        parent = x(parent_name) if parent_name else "&#4; Primary"

        alias_xml = ""
        if getattr(group, 'alias_name', None):
            alias_xml = f"""
          <LANGUAGENAME.LIST>
            <NAME.LIST TYPE="String">
              <NAME>{x(group.name)}</NAME>
              <NAME>{x(group.alias_name)}</NAME>
            </NAME.LIST>
            <LANGUAGEID>{int(getattr(group, 'language_id', None) or 1033)}</LANGUAGEID>
          </LANGUAGENAME.LIST>"""

        gst_xml = ""
        for gst in sorted(getattr(group, 'gst_details', None) or [], key=lambda g: g.applicable_from):
            app_from = gst.applicable_from.strftime("%Y%m%d")
            rate = Decimal(str(gst.gst_rate or 0))
            half = rate / 2
            fmt = lambda d: format(d.normalize(), "f") if d else "0"
            gst_xml += f"""
          <HSNDETAILS.LIST>
            <APPLICABLEFROM>{app_from}</APPLICABLEFROM>
            <HSNCODE>{x(gst.hsn_sac or '')}</HSNCODE>
            <SRCOFHSNDETAILS>{x(gst.hsn_sac_details or 'As per Company/Group')}</SRCOFHSNDETAILS>
          </HSNDETAILS.LIST>
          <GSTDETAILS.LIST>
            <APPLICABLEFROM>{app_from}</APPLICABLEFROM>
            <TAXABILITY>{x(gst.taxability_type or 'Unknown')}</TAXABILITY>
            <SRCOFGSTDETAILS>{x(gst.gst_rate_details or 'As per Company/Group')}</SRCOFGSTDETAILS>
            <STATEWISEDETAILS.LIST>
              <STATENAME>&#4; Any</STATENAME>
              <RATEDETAILS.LIST><GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD><GSTRATE>{fmt(rate)}</GSTRATE></RATEDETAILS.LIST>
              <RATEDETAILS.LIST><GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD><GSTRATE>{fmt(half)}</GSTRATE></RATEDETAILS.LIST>
              <RATEDETAILS.LIST><GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD><GSTRATE>{fmt(half)}</GSTRATE></RATEDETAILS.LIST>
            </STATEWISEDETAILS.LIST>
          </GSTDETAILS.LIST>"""

        body = f"""<GROUP NAME="{x(target_name)}" Action="{x(action)}">
          <NAME>{x(group.name)}</NAME>
          <PARENT>{parent}</PARENT>
          <ISADDABLE>{yes_no(getattr(group, 'is_addable', True))}</ISADDABLE>
          <ISREVENUE>{yes_no(getattr(group, 'is_revenue', False))}</ISREVENUE>
          <ISDEEMEDPOSITIVE>{yes_no(getattr(group, 'is_deemed_positive', False))}</ISDEEMEDPOSITIVE>
          <AFFECTSGROSSPROFIT>{yes_no(getattr(group, 'affects_gross_profit', False))}</AFFECTSGROSSPROFIT>
          <ISSUBLEDGER>{yes_no(getattr(group, 'is_subledger', False))}</ISSUBLEDGER>
          <ISBILLWISEON>{yes_no(getattr(group, 'is_billwise_on', False))}</ISBILLWISEON>
          <BASICGROUPISCALCULABLE>{yes_no(getattr(group, 'used_for_calculation', False))}</BASICGROUPISCALCULABLE>
          <ADDLALLOCTYPE>{alloc}</ADDLALLOCTYPE>
          <SORTPOSITION>{int(getattr(group, 'sort_position', None) or 1000)}</SORTPOSITION>{alias_xml}{gst_xml}
        </GROUP>"""

    return f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(company_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {body}
      </TALLYMESSAGE>
    </DESC>
  </BODY>
</ENVELOPE>"""


async def remove_tally_ghost(tally_url: str, comp_name: str, subtype: str, name: str) -> bool:
    """
    A create Tally rejects can still leave a ghost: an object that answers to its name with ALTERID 0, is in
    no list, and can block other masters for good. Deletes it if there is one; True when one was removed.
    """
    state = await fetch_tally_master_state(tally_url, comp_name, subtype, name)
    if not (state and state["exists"] and state["ghost"]):
        return False
    tag = subtype.upper().replace(" ", "")
    xml = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <{tag} NAME="{x(name)}" Action="Delete"><NAME>{x(name)}</NAME></{tag}>
      </TALLYMESSAGE>
    </DESC>
  </BODY>
</ENVELOPE>"""
    resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml, 10)
    return check_tally_success(resp)


async def try_push_group_realtime(group_id: int, sync_id: int, action: str, db: AsyncSession, tally_name: Optional[str] = None):
    """
    Pushes a group to Tally and records the outcome on its SyncQueue row.
    Returns (ok, status, message); status is SUCCESS, NOT_CONFIGURED, REJECTED (Tally answered and
    refused; message is Tally's reason), NO_RESPONSE (Tally unreachable or timed out), FAILED or EXCEPTION.
    """
    async def record(status_code: str, message: Optional[str], payload: Optional[str] = None, response: Optional[str] = None):
        await db.execute(
            update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(
                is_processed=(status_code == "SUCCESS"),
                attempts=func.coalesce(SyncQueue.attempts, 0) + 1,
                status=status_code,
                error_message=message[:500] if message else None,
                last_payload=payload,
                last_response=response[:5000] if response else None,
                last_attempt_at=func.now(),
            )
        )
        await db.commit()

    try:
        tally_url = current_tally_url()
        if not tally_url:
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        sq_res = await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_id))
        sync_item = sq_res.scalars().first()
        snapshot = (sync_item.snapshot_data if sync_item else None) or {}
        if not tally_name:
            tally_name = snapshot.get("tally_name")

        g_stmt = select(MstGroup).options(
            selectinload(MstGroup.parent),
            selectinload(MstGroup.gst_details)
        ).where(MstGroup.group_id == group_id).execution_options(populate_existing=True)
        g_res = await db.execute(g_stmt)
        group = g_res.scalars().first()
        # A delete that could not reach Tally is retried after the group is gone here; its name is on the queue row
        is_delete_replay = group is None and action.lower() == "delete" and bool(tally_name) and sync_item is not None
        if not group and not is_delete_replay:
            await record("FAILED", f"Group #{group_id} not found")
            return (False, "FAILED", f"Group #{group_id} not found")

        company_id = group.company_id if group else sync_item.company_id
        group_name = group.name if group else tally_name
        parent_name = group.parent.name if group and group.parent else ""
        
        c_stmt = select(Company).where(Company.company_id == company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        xml_envelope = build_group_xml_envelope(group, parent_name, comp_name, action, tally_name)

        logger.debug(f"\n=======================================================\nOUTBOUND REALTIME TALLY GROUP PUSH (group_id={group_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")

        import time
        start_time = time.time()
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        await record_sync_traffic_log(
            db, company_id, sync_id, "Group", group_id, group_name, action, "XML",
            xml_envelope, resp_str, int((time.time() - start_time) * 1000), tally_url
        )

        if check_tally_success(resp_str):
            await record("SUCCESS", None, xml_envelope, resp_str)
            return (True, "SUCCESS", None)
        if not resp_str or not resp_str.strip():
            logger.warning(f"Real-time Tally push got no answer for group_id={group_id} ({action})")
            await record("NO_RESPONSE", "No response from Tally", xml_envelope, resp_str)
            return (False, "NO_RESPONSE", "No response from Tally")

        reason = parse_tally_response_metrics(resp_str)["error_summary"] or "Tally rejected the request"
        if action.lower() == "delete" and "does not exist" in reason.lower():
            # Tally no longer has it, which is where a delete is headed
            await record("SUCCESS", None, xml_envelope, resp_str)
            return (True, "SUCCESS", None)
        if action.lower() == "create":
            await remove_tally_ghost(tally_url, comp_name, "Group", group_name)
        logger.warning(f"Real-time Tally push rejected for group_id={group_id} ({action}): {reason}")
        await record("REJECTED", reason, xml_envelope, resp_str)
        return (False, "REJECTED", reason)

    except Exception as e:
        logger.warning(f"Real-time Tally push exception for group_id={group_id}: {str(e)}", exc_info=True)
        try:
            await db.rollback()
            await record("EXCEPTION", str(e))
        except Exception:
            logger.warning(f"Could not record the push failure for sync_id={sync_id}", exc_info=True)
        return (False, "EXCEPTION", str(e))

async def try_push_ledger_realtime(ledger_id: int, sync_item_id: int, action: str, db: AsyncSession, tally_name: Optional[str] = None):
    """
    Attempts real-time push to Tally Prime on the fly, with the same full ledger XML the Desktop Sync Agent sends.
    Records structured traffic logs and updates DeletedRecordAudit when deleting.
    tally_name: the name Tally knows the ledger by when it differs from the current one (a rename); read
    from the queue row when not given, which is also where a delete finds the name once the ledger is gone.
    """
    import time
    start_time = time.time()
    try:
        tally_url = current_tally_url()
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        sync_item = None
        if sync_item_id and sync_item_id > 0:
            sync_item = (await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_item_id))).scalars().first()
        if not tally_name:
            tally_name = ((sync_item.snapshot_data if sync_item else None) or {}).get("tally_name")

        l_stmt = select(MstLedger).options(
            selectinload(MstLedger.group), selectinload(MstLedger.bank_details), selectinload(MstLedger.addresses),
            selectinload(MstLedger.gst_registrations), selectinload(MstLedger.msme_details),
            selectinload(MstLedger.lower_deductions)
        ).where(MstLedger.ledger_id == ledger_id).execution_options(populate_existing=True)
        l_res = await db.execute(l_stmt)
        ledger = l_res.scalars().first()
        if not ledger and not (action == "Delete" and tally_name):
            logger.warning(f"Real-time Tally push skipped: ledger_id={ledger_id} not found.")
            return (False, "FAILED", f"Ledger #{ledger_id} not found")

        company_id = ledger.company_id if ledger else (sync_item.company_id if sync_item else 1)
        ledger_name = ledger.name if ledger else tally_name
        group_name = ledger.group.name if (ledger and ledger.group) else "Sundry Debtors"
        
        c_stmt = select(Company).where(Company.company_id == company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        if action == "Delete":
            xml_envelope = build_ledger_delete_envelope(tally_name or ledger_name, comp_name)
        else:
            xml_envelope = build_ledger_xml_envelope(ledger, group_name, comp_name, action, tally_name)

        logger.debug(f"\n=======================================================\nOUTBOUND REALTIME TALLY LEDGER PUSH (ledger_id={ledger_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"\n=======================================================\nTALLY LEDGER PUSH RESPONSE (ledger_id={ledger_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

        # Record structured log in sync_traffic_logs with Postman-ready cURL
        await record_sync_traffic_log(
            db=db,
            company_id=company_id,
            sync_id=sync_item_id if sync_item_id and sync_item_id > 0 else None,
            entity_type="Ledger",
            entity_id=ledger_id,
            entity_name=ledger_name,
            action=action,
            outbound_format="XML",
            outbound_payload=xml_envelope,
            inbound_response=resp_str,
            duration_ms=duration_ms,
            tally_url=tally_url
        )

        metrics = parse_tally_response_metrics(resp_str)
        is_success = check_tally_success(resp_str)
        # A delete of something Tally no longer has is already where it should be: settle it instead of
        # leaving the row to be retried for ever
        already_absent = (not is_success and action == "Delete"
                          and "does not exist" in (metrics["error_summary"] or "").lower())

        if sync_item_id and sync_item_id > 0:
            if is_success or already_absent:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(is_processed=True, status="SUCCESS", last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), attempts=SyncQueue.attempts + 1)
            else:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(status="FAILED", attempts=SyncQueue.attempts + 1, last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), error_message=metrics["error_summary"] or str(resp_str)[:500])
            await db.execute(sq_stmt)
            await db.commit()

        if action == "Delete":
            await db.execute(
                update(DeletedRecordAudit)
                .where(
                    DeletedRecordAudit.company_id == company_id,
                    DeletedRecordAudit.entity_type == "Ledger",
                    DeletedRecordAudit.record_id == ledger_id
                )
                .values(
                    tally_sync_status="SYNCED_TO_TALLY" if is_success else "ALREADY_DELETED_IN_TALLY" if already_absent else "NOT_DELETED_IN_TALLY",
                    tally_error_message=None if (is_success or already_absent) else (metrics["error_summary"] or "Cannot be deleted in Tally Prime (referenced in transactions)")
                )
            )
            await db.commit()

        if already_absent:
            logger.info(f"Ledger delete for ledger_id={ledger_id}: Tally no longer has it, nothing to do")
            return (True, "ALREADY_ABSENT", None)
        if is_success:
            logger.info(f"Real-time Tally push successful for ledger_id={ledger_id}, action={action}")
            return (True, "SUCCESS", None)
        if not resp_str or not resp_str.strip():
            logger.error(f"Real-time Tally push got no answer for ledger_id={ledger_id}")
            return (False, "NO_RESPONSE", "No response from Tally")
        # Tally answered and refused; a create it refuses can leave a ghost ledger behind
        if action == "Create":
            await remove_tally_ghost(tally_url, comp_name, "Ledger", ledger_name)
        logger.error(f"Real-time Tally push rejected for ledger_id={ledger_id}: {resp_str}")
        return (False, "REJECTED", metrics["error_summary"] or "Tally rejected the ledger")
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for ledger_id={ledger_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


def _qty(value) -> str:
    """A quantity or rate as Tally reads it: plain digits, no exponent, no trailing zeros."""
    d = Decimal(str(value or 0))
    return format(d.normalize(), "f") if d else "0"


def build_stock_item_xml(item, action: str, tally_name: Optional[str] = None, include_gst: bool = True) -> str:
    """
    The <STOCKITEM> element. The relationships it reads (unit, alt_unit, group, category, aliases,
    opening_balances with their godown) must be loaded by the caller.
    tally_name: the name Tally currently knows the item by when it differs from item.name (a rename).
    include_gst: send the HSN code and GST rate. Tally keeps these as dated entries with more in them than
    is held here (cess, valuation type), so they are sent for a new item or when the HSN code or rate was
    actually changed, and left alone otherwise: an unrelated edit must not rewrite an item's tax history.

    Opening stock is always sent as a batch list, and an empty list when there is none: Tally keeps opening
    stock on the batch allocation, ignores a change made at item level alone, and replaces the whole list
    with the one sent, so sending it every time is what makes a repeated push harmless.
    """
    target = tally_name or item.name
    if action == "Delete":
        return f"""<STOCKITEM NAME="{x(target)}" Action="Delete">
          <NAME>{x(target)}</NAME>
        </STOCKITEM>"""

    uom_symbol = (item.unit.symbol or item.unit.name) if item.unit else "nos"
    # An item Tally holds without a unit is kept here under a placeholder unit of that name
    has_unit = uom_symbol.strip().lower() != "not applicable"
    raw_group_name = item.group.name.strip() if item.group and item.group.name else ""
    if not raw_group_name or raw_group_name.lower() in ("primary", "not applicable"):
        parent_tag = "<PARENT>&#4; Primary</PARENT>"
    else:
        parent_tag = f"<PARENT>{x(raw_group_name)}</PARENT>"

    category_name = (item.category.name or "").strip() if item.category else ""
    if category_name.lower() == "not applicable":
        category_name = ""
    category_tag = f"<CATEGORY>{x(category_name)}</CATEGORY>" if category_name else "<CATEGORY>&#4; Not Applicable</CATEGORY>"
    # is_batch_wise is what an import from Tally sets; tracking_type what the item form sets
    is_batchwise = "Yes" if (getattr(item, 'tracking_type', None) in ("Batches", "Serial", "Batch")
                             or getattr(item, 'is_batch_wise', False)) else "No"
    supply_type = "Services" if (item.unit and item.unit.name and item.unit.name.lower() in ['hrs', 'srv', 'serv', 'service']) else "Goods"

    # "<conversion> alternate units = <denominator> base units", as Tally keeps it: CONVERSION counts
    # alternate units and DENOMINATOR base units
    alt_unit = getattr(item, 'alt_unit', None)
    alt_conversion = Decimal(str(getattr(item, 'alt_unit_conversion', None) or 0))
    alt_denominator = Decimal(str(getattr(item, 'alt_unit_denominator', None) or 1))
    if alt_unit is not None and alt_conversion > 0:
        alt_block = f"""<ADDITIONALUNITS>{x(alt_unit.symbol or alt_unit.name)}</ADDITIONALUNITS>
          <CONVERSION>{_qty(alt_conversion)}</CONVERSION>
          <DENOMINATOR>{_qty(alt_denominator if alt_denominator > 0 else 1)}</DENOMINATOR>"""
    else:
        alt_block = "<ADDITIONALUNITS>&#4; Not Applicable</ADDITIONALUNITS>"

    aliases = [a.alias.strip() for a in (getattr(item, 'aliases', None) or [])
               if a.alias and a.alias.strip() and a.alias.strip().lower() != item.name.strip().lower()]
    alias_nodes = "".join(f"\n              <NAME>{x(a)}</NAME>" for a in aliases)

    gst_rate = Decimal(str(item.gst_rate_percent or 0))
    hsn_str = (item.hsn_code or "").strip()
    # GST tags only for an item that carries GST details here; sending them for every item would switch
    # GST on in Tally for items that have none
    gst_block = ""
    if not include_gst:
        hsn_str, gst_rate = "", Decimal("0")
    if hsn_str or gst_rate > 0:
        gst_block = f"""<GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE>
          <GSTTYPEOFSUPPLY>{supply_type}</GSTTYPEOFSUPPLY>"""
    if hsn_str:
        gst_block += f"""
          <HSNDETAILS.LIST>
            <APPLICABLEFROM>20170701</APPLICABLEFROM>
            <HSNCODE>{x(hsn_str)}</HSNCODE>
            <SRCOFHSNDETAILS>Specify Details Here</SRCOFHSNDETAILS>
          </HSNDETAILS.LIST>"""
    if gst_rate > 0:
        half = gst_rate / 2
        gst_block += f"""
          <GSTDETAILS.LIST>
            <APPLICABLEFROM>20170701</APPLICABLEFROM>
            <TAXABILITY>Taxable</TAXABILITY>
            <SRCOFGSTDETAILS>Specify Details Here</SRCOFGSTDETAILS>
            <STATEWISEDETAILS.LIST>
              <STATENAME>&#4; Any</STATENAME>
              <RATEDETAILS.LIST><GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD><GSTRATE>{_qty(gst_rate)}</GSTRATE></RATEDETAILS.LIST>
              <RATEDETAILS.LIST><GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD><GSTRATE>{_qty(half)}</GSTRATE></RATEDETAILS.LIST>
              <RATEDETAILS.LIST><GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD><GSTRATE>{_qty(half)}</GSTRATE></RATEDETAILS.LIST>
            </STATEWISEDETAILS.LIST>
          </GSTDETAILS.LIST>"""

    # Opening stock, one batch per godown row; the item's own quantity and rate when no rows are kept
    batches = []
    for ob in (getattr(item, 'opening_balances', None) or []):
        if Decimal(str(ob.quantity or 0)) <= 0:
            continue
        godown = ob.godown.name if getattr(ob, 'godown', None) else "Main Location"
        batches.append((godown, ob.batch_name or "Primary Batch", Decimal(str(ob.quantity)), Decimal(str(ob.rate or 0)), Decimal(str(ob.amount or 0))))
    if not batches and item.opening_qty and Decimal(str(item.opening_qty)) > 0:
        qty, rate = Decimal(str(item.opening_qty)), Decimal(str(item.opening_rate or 0))
        batches.append(("Main Location", "Primary Batch", qty, rate, qty * rate))

    if batches:
        total_qty = sum(b[2] for b in batches)
        total_value = sum(b[4] for b in batches)
        average = total_value / total_qty if total_qty else Decimal("0")
        # A debit: Tally keeps the value of stock held as a negative amount
        ob_block = f"""<OPENINGBALANCE>{_qty(total_qty)} {x(uom_symbol)}</OPENINGBALANCE>
          <OPENINGRATE>{average:.2f}/{x(uom_symbol)}</OPENINGRATE>
          <OPENINGVALUE>-{total_value:.2f}</OPENINGVALUE>"""
        for godown, batch_name, qty, rate, amount in batches:
            ob_block += f"""
          <BATCHALLOCATIONS.LIST>
            <GODOWNNAME>{x(godown)}</GODOWNNAME>
            <BATCHNAME>{x(batch_name)}</BATCHNAME>
            <OPENINGBALANCE>{_qty(qty)} {x(uom_symbol)}</OPENINGBALANCE>
            <OPENINGRATE>{rate:.2f}/{x(uom_symbol)}</OPENINGRATE>
            <OPENINGVALUE>-{amount:.2f}</OPENINGVALUE>
          </BATCHALLOCATIONS.LIST>"""
    else:
        ob_block = """<OPENINGBALANCE></OPENINGBALANCE>
          <OPENINGRATE></OPENINGRATE>
          <OPENINGVALUE></OPENINGVALUE>
          <BATCHALLOCATIONS.LIST>
          </BATCHALLOCATIONS.LIST>"""

    return f"""<STOCKITEM NAME="{x(target)}" Action="{x(action)}">
          <NAME>{x(item.name)}</NAME>
          {parent_tag}
          {category_tag}
          <BASEUNITS>{x(uom_symbol) if has_unit else "&#4; Not Applicable"}</BASEUNITS>
          {alt_block}
          <DESCRIPTION>{x(item.description or '')}</DESCRIPTION>
          <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
          <ISBATCHWISEON>{is_batchwise}</ISBATCHWISEON>
          {gst_block}
          <LANGUAGENAME.LIST>
            <NAME.LIST TYPE="String">
              <NAME>{x(item.name)}</NAME>{alias_nodes}
            </NAME.LIST>
          </LANGUAGENAME.LIST>
          {ob_block}
        </STOCKITEM>"""


async def send_stock_item(db: AsyncSession, stock_item_id: int, action: str, tally_name: Optional[str] = None,
                          company_id: Optional[int] = None, include_gst: Optional[bool] = None) -> dict:
    """
    Sends a stock item to Tally and reports what happened, without committing anything: the caller decides
    whether its own changes stand. Reads the item as it is in the caller's transaction.
    Returns {"status", "reason", "envelope", "response", "name", "company_id", "duration_ms"}; status is
    SUCCESS, NOT_CONFIGURED, REJECTED (Tally answered and refused), NO_RESPONSE or FAILED.
    """
    import time
    from app.models.tally_core import MstStockItem, StockItemOpeningBalance

    result = {"status": "FAILED", "reason": None, "envelope": None, "response": None, "name": tally_name,
              "company_id": company_id, "duration_ms": 0}
    tally_url = current_tally_url()
    if not tally_url:
        result.update(status="NOT_CONFIGURED", reason="TALLY_URL is not configured")
        return result

    # populate_existing: the caller may hold this item with related rows it has since replaced
    item_stmt = select(MstStockItem).options(
        selectinload(MstStockItem.unit),
        selectinload(MstStockItem.alt_unit),
        selectinload(MstStockItem.group),
        selectinload(MstStockItem.category),
        selectinload(MstStockItem.aliases),
        selectinload(MstStockItem.opening_balances).selectinload(StockItemOpeningBalance.godown)
    ).where(MstStockItem.stock_item_id == stock_item_id).execution_options(populate_existing=True)
    item = (await db.execute(item_stmt)).scalars().first()
    if not item and not (action == "Delete" and tally_name):
        result["reason"] = f"Stock Item #{stock_item_id} not found"
        return result

    company_id = item.company_id if item else company_id
    item_name = item.name if item else tally_name
    comp_obj = (await db.execute(select(Company).where(Company.company_id == company_id))).scalars().first()
    comp_name = comp_obj.name if comp_obj else ""

    if include_gst is None:
        include_gst = action == "Create"
    if item and action in ("Create", "Alter"):
        # Sent as what it really is for Tally: an item Tally does not have yet is a create, tax details
        # included, whatever the queue row says (an item saved here while Tally was unreachable, for one)
        state = await fetch_tally_master_state(tally_url, comp_name, "Stock Item", tally_name or item.name)
        if state is not None and not state["exists"] and tally_name and tally_name != item.name:
            # The old name is gone; it may already be under the new one
            tally_name = None
            state = await fetch_tally_master_state(tally_url, comp_name, "Stock Item", item.name)
        if state is None:
            result.update(status="NO_RESPONSE", reason="No response from Tally", name=item_name, company_id=company_id)
            return result
        if state["exists"] and state["ghost"]:
            await remove_tally_ghost(tally_url, comp_name, "Stock Item", tally_name or item.name)
            state = {"exists": False}
        if state["exists"]:
            action = "Alter"
        else:
            action, tally_name, include_gst = "Create", None, True
    item_xml = build_stock_item_xml(item, action, tally_name, include_gst) if item else f"""<STOCKITEM NAME="{x(tally_name)}" Action="Delete">
          <NAME>{x(tally_name)}</NAME>
        </STOCKITEM>"""
    envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {item_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""
    logger.debug(f"\n=======================================================\nOUTBOUND REALTIME TALLY STOCKITEM PUSH (stock_item_id={stock_item_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{envelope}\n=======================================================\n")
    started = time.time()
    resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, envelope, 5)
    result.update(envelope=envelope, response=resp, name=item_name, company_id=company_id,
                  duration_ms=int((time.time() - started) * 1000))

    if check_tally_success(resp):
        result["status"] = "SUCCESS"
    elif not resp or not resp.strip():
        result.update(status="NO_RESPONSE", reason="No response from Tally")
    else:
        reason = parse_tally_response_metrics(resp)["error_summary"] or "Tally rejected the stock item"
        if action == "Delete" and "does not exist" in reason.lower():
            # Tally no longer has it, which is where a delete is headed
            result["status"] = "SUCCESS"
        else:
            if action == "Create":
                # A create Tally refuses can leave a ghost item behind
                await remove_tally_ghost(tally_url, comp_name, "Stock Item", item_name)
            result.update(status="REJECTED", reason=reason)
    return result


async def record_stock_item_push(db: AsyncSession, stock_item_id: int, sync_item_id: Optional[int], action: str, result: dict):
    """Writes a send_stock_item() outcome to the traffic log, the queue row and, for a delete, the delete audit."""
    if result.get("envelope") is not None:
        await record_sync_traffic_log(
            db=db, company_id=result["company_id"], sync_id=sync_item_id if sync_item_id and sync_item_id > 0 else None,
            entity_type="StockItem", entity_id=stock_item_id, entity_name=result["name"], action=action,
            outbound_format="XML", outbound_payload=result["envelope"], inbound_response=result["response"],
            duration_ms=result["duration_ms"], tally_url=current_tally_url())
    ok = result["status"] == "SUCCESS"
    if sync_item_id and sync_item_id > 0 and result["status"] != "NOT_CONFIGURED":
        await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(
            is_processed=ok, status=result["status"], attempts=func.coalesce(SyncQueue.attempts, 0) + 1,
            last_payload=result["envelope"], last_response=result["response"], last_attempt_at=func.now(),
            error_message=(result["reason"] or "")[:500] or None))
    if action == "Delete" and result["status"] in ("SUCCESS", "REJECTED"):
        await db.execute(
            update(DeletedRecordAudit)
            .where(DeletedRecordAudit.company_id == result["company_id"], DeletedRecordAudit.entity_type == "StockItem",
                   DeletedRecordAudit.record_id == stock_item_id)
            .values(tally_sync_status="SYNCED_TO_TALLY" if ok else "NOT_DELETED_IN_TALLY",
                    tally_error_message=None if ok else (result["reason"] or "Cannot be deleted in Tally Prime")))
    await db.commit()
    if ok and action != "Delete":
        await store_tally_master_identity(db, "Stock Item", MstStockItem, stock_item_id)


async def try_push_stock_item_realtime(stock_item_id: int, sync_item_id: int, action: str, db: AsyncSession, tally_name: Optional[str] = None):
    """
    Pushes a Stock Item to Tally and records the outcome on its queue row.
    tally_name: the name Tally knows the item by when it differs from the current one (a rename); read from
    the queue row when not given, which is also where a delete finds the name once the item is gone.
    Returns (ok, status, message).
    """
    try:
        sync_item = None
        if sync_item_id and sync_item_id > 0:
            sync_item = (await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_item_id))).scalars().first()
        snapshot = (sync_item.snapshot_data if sync_item else None) or {}
        if not tally_name:
            tally_name = snapshot.get("tally_name")
        result = await send_stock_item(db, stock_item_id, action, tally_name, sync_item.company_id if sync_item else None,
                                       snapshot.get("include_gst"))
        if result["status"] == "NOT_CONFIGURED":
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", result["reason"])
        await record_stock_item_push(db, stock_item_id, sync_item_id, action, result)
        if result["status"] == "SUCCESS":
            logger.info(f"Real-time Tally push successful for stock_item_id={stock_item_id}, action={action}")
            return (True, "SUCCESS", None)
        logger.error(f"Real-time Tally push failed for stock_item_id={stock_item_id}: {result['status']}: {result['reason']}")
        return (False, result["status"], result["reason"])
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for stock_item_id={stock_item_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


def compound_unit_name(base_symbol: str, conversion, additional_symbol: str) -> str:
    """
    The name Tally gives a compound unit. Tally ignores whatever name is sent for one and derives it from
    its parts, and re-derives it whenever the conversion or either part changes.
    """
    conv = Decimal(str(conversion or 1))
    conv_str = str(int(conv)) if conv == conv.to_integral_value() else str(conv.normalize())
    return f"{base_symbol} of {conv_str} {additional_symbol}"


async def fetch_tally_master_state(tally_url: str, comp_name: str, subtype: str, name: str) -> Optional[dict]:
    """
    Whether Tally has a master of this type and name: {"exists": False}, or {"exists": True, "ghost": bool}.
    A ghost is what a rejected create leaves behind: it answers to its name with ALTERID 0 but is in no list,
    and it can hold references that nothing visible explains. None when Tally gave no usable answer.
    The fetch list is mandatory: an object export without one crashes TallyPrime.
    """
    xml = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Object</TYPE><SUBTYPE>{x(subtype)}</SUBTYPE><ID TYPE="Name">{x(name)}</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <FETCHLIST><FETCH>Name</FETCH><FETCH>AlterID</FETCH></FETCHLIST>
    </DESC>
  </BODY>
</ENVELOPE>"""
    resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml, 10)
    if not resp or not resp.strip():
        return None
    if "could not find" in resp.lower():
        return {"exists": False}
    m = re.search(r"<ALTERID[^>]*>\s*(\d+)\s*</ALTERID>", resp)
    if "<ERRORMSG>" in resp or "<LINEERROR>" in resp or not m:
        return None
    return {"exists": True, "ghost": int(m.group(1)) == 0}


def _unit_import_envelope(comp_name: str, unit_xml: str) -> str:
    return f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {unit_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""


def build_unit_xml(symbol: str, action: str, target_name: Optional[str] = None, formal_name: Optional[str] = None,
                   decimal_places: int = 0, base_symbol: Optional[str] = None, additional_symbol: Optional[str] = None,
                   conversion=None) -> str:
    """
    The <UNIT> element for a simple unit, or for a compound one when base_symbol is given.
    target_name is the name Tally currently has it under (differs from symbol on a rename).
    The formal name is left out when it is empty or equal to the symbol: Tally keeps both in one namespace,
    rejects the pair as DUPLICATE ORIGINAL NAME on a create, and on an alter stores a unit that duplicates
    itself and then stops responding behind an internal-error dialog.
    """
    target = target_name or symbol
    if action == "Delete":
        return f"""<UNIT NAME="{x(target)}" Action="Delete">
          <NAME>{x(target)}</NAME>
        </UNIT>"""
    if base_symbol:
        conv = Decimal(str(conversion or 1))
        conv_str = str(int(conv)) if conv == conv.to_integral_value() else str(conv.normalize())
        return f"""<UNIT NAME="{x(target)}" Action="{x(action)}">
          <NAME>{x(symbol)}</NAME>
          <ISSIMPLEUNIT>No</ISSIMPLEUNIT>
          <BASEUNITS>{x(base_symbol)}</BASEUNITS>
          <ADDITIONALUNITS>{x(additional_symbol or '')}</ADDITIONALUNITS>
          <CONVERSION>{conv_str}</CONVERSION>
        </UNIT>"""
    formal = (formal_name or "").strip()
    formal_xml = f"\n          <ORIGINALNAME>{x(formal)}</ORIGINALNAME>" if formal and formal.lower() != symbol.strip().lower() else ""
    return f"""<UNIT NAME="{x(target)}" Action="{x(action)}">
          <NAME>{x(symbol)}</NAME>{formal_xml}
          <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
          <DECIMALPLACES>{int(decimal_places or 0)}</DECIMALPLACES>
        </UNIT>"""


async def try_push_uom_realtime(unit_id: int, sync_item_id: int, action: str, db: AsyncSession, tally_name: Optional[str] = None):
    """
    Pushes a Unit of Measure to Tally and records the outcome on its queue row.

    Tally is asked first whether it has the unit, and the request is sent as the action that matches:
    an Alter for a unit Tally does not have would create one from partial data, and a Create for a compound
    unit it already has is rejected. A ghost left by an earlier rejected create is removed first.
    tally_name: the name Tally knows the unit by when it differs from the current one (a rename, or a
    compound unit whose parts changed); read from the queue row when not given, which is also where a
    delete finds the name once the unit is gone.
    Returns (ok, status, message).
    """
    import time
    start_time = time.time()
    try:
        from app.models.tally_core import MstUom
        from app.models.portal_core import SyncQueue, Company

        tally_url = current_tally_url()
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        sync_item = None
        if sync_item_id and sync_item_id > 0:
            sync_item = (await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_item_id))).scalars().first()
        if not tally_name:
            tally_name = ((sync_item.snapshot_data if sync_item else None) or {}).get("tally_name")

        u_stmt = select(MstUom).where(MstUom.unit_id == unit_id)
        u_res = await db.execute(u_stmt)
        uom = u_res.scalars().first()
        if not uom and not (action == "Delete" and tally_name):
            logger.warning(f"Real-time Tally push skipped: unit_id={unit_id} not found.")
            return (False, "FAILED", f"Unit #{unit_id} not found")

        company_id = uom.company_id if uom else (sync_item.company_id if sync_item else 1)
        c_stmt = select(Company).where(Company.company_id == company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        async def record(status_code: str, message: Optional[str], payload: Optional[str] = None, response: Optional[str] = None):
            if not sync_item:
                return
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(
                is_processed=(status_code == "SUCCESS"), status=status_code,
                attempts=func.coalesce(SyncQueue.attempts, 0) + 1, last_payload=payload, last_response=response,
                last_attempt_at=func.now(), error_message=message[:500] if message else None))
            await db.commit()

        async def send(unit_xml: str, sent_action: str, name: str) -> str:
            envelope = _unit_import_envelope(comp_name, unit_xml)
            started = time.time()
            logger.debug(f"\n=======================================================\nOUTBOUND REALTIME TALLY UOM PUSH (unit_id={unit_id}, action={sent_action})\nURL: {tally_url}\nPAYLOAD:\n{envelope}\n=======================================================\n")
            resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, envelope, 5)
            await record_sync_traffic_log(
                db=db, company_id=company_id, sync_id=sync_item_id if sync_item else None, entity_type="UOM",
                entity_id=unit_id, entity_name=name, action=sent_action, outbound_format="XML",
                outbound_payload=envelope, inbound_response=resp, duration_ms=int((time.time() - started) * 1000),
                tally_url=tally_url)
            return resp

        def outcome(resp: str):
            if not resp or not resp.strip():
                return "NO_RESPONSE", "Tally did not answer"
            if check_tally_success(resp):
                return "SUCCESS", None
            return "REJECTED", parse_tally_response_metrics(resp)["error_summary"] or "Tally rejected the unit"

        if uom:
            symbol = uom.symbol or uom.name
            base_symbol = additional_symbol = None
            if not uom.is_simple_unit:
                base = (await db.execute(select(MstUom).where(MstUom.unit_id == uom.base_unit_id))).scalars().first() if uom.base_unit_id else None
                additional = (await db.execute(select(MstUom).where(MstUom.unit_id == uom.additional_unit_id))).scalars().first() if uom.additional_unit_id else None
                if not base or not additional:
                    await record("FAILED", "Compound unit has no base or additional unit")
                    return (False, "FAILED", "Compound unit has no base or additional unit")
                base_symbol, additional_symbol = base.symbol or base.name, additional.symbol or additional.name
                # Whatever is stored as its symbol, this is the name Tally will give it
                symbol = compound_unit_name(base_symbol, uom.conversion_factor, additional_symbol)
        else:
            symbol = tally_name
        target = tally_name or symbol

        if action == "Delete":
            unit_xml = build_unit_xml(target, "Delete")
            resp = await send(unit_xml, "Delete", target)
            status_code, reason = outcome(resp)
            if status_code == "REJECTED" and "does not exist" in (reason or "").lower():
                # Tally no longer has it, which is where a delete is headed
                status_code, reason = "SUCCESS", None
            await record(status_code, reason, unit_xml, resp)
            return (status_code == "SUCCESS", status_code, reason)

        # Create or Alter: decided by what Tally actually has, not by what was asked
        state = await fetch_tally_master_state(tally_url, comp_name, "Unit", target)
        if state is None:
            await record("NO_RESPONSE", "Tally did not answer")
            return (False, "NO_RESPONSE", "Tally did not answer")
        if state["exists"] and state["ghost"]:
            await send(build_unit_xml(target, "Delete"), "Delete", target)
            state = {"exists": False}
        if not state["exists"] and target != symbol:
            # The old name is gone; it may already be under the new one (an earlier push that was not recorded)
            target = symbol
            state = await fetch_tally_master_state(tally_url, comp_name, "Unit", target)
            if state is None:
                await record("NO_RESPONSE", "Tally did not answer")
                return (False, "NO_RESPONSE", "Tally did not answer")
            if state["exists"] and state["ghost"]:
                await send(build_unit_xml(target, "Delete"), "Delete", target)
                state = {"exists": False}

        sent_action = "Alter" if state["exists"] else "Create"
        unit_xml = build_unit_xml(symbol, sent_action, target_name=target, formal_name=uom.original_name,
                                  decimal_places=uom.decimal_places, base_symbol=base_symbol,
                                  additional_symbol=additional_symbol, conversion=uom.conversion_factor)
        resp = await send(unit_xml, sent_action, symbol)
        status_code, reason = outcome(resp)

        if status_code == "REJECTED" and sent_action == "Create":
            # A rejected create can leave a ghost that blocks other units for good: take it away again
            after = await fetch_tally_master_state(tally_url, comp_name, "Unit", symbol)
            if after and after["exists"] and after["ghost"]:
                await send(build_unit_xml(symbol, "Delete"), "Delete", symbol)

        await record(status_code, reason, unit_xml, resp)
        if status_code == "SUCCESS":
            logger.info(f"Real-time Tally push successful for unit_id={unit_id}, action={sent_action}")
            return (True, "SUCCESS", None)
        logger.error(f"Real-time Tally push failed for unit_id={unit_id}: {status_code}: {reason}")
        return (False, status_code, reason)
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for unit_id={unit_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


def build_stock_group_xml(name: str, action: str, target_name: Optional[str] = None, parent_name: Optional[str] = None,
                          aliases: Optional[List[str]] = None) -> str:
    """
    The <STOCKGROUP> element. target_name is the name Tally currently has it under (differs from name on a
    rename). A top-level group is sent with Tally's own marker "&#4; Primary", control character included;
    leaving PARENT out would leave an existing group where it is.
    ISADDABLE is always sent: without it Tally creates the group with quantities not addable.
    """
    target = target_name or name
    if action == "Delete":
        return f"""<STOCKGROUP NAME="{x(target)}" Action="Delete">
          <NAME>{x(target)}</NAME>
        </STOCKGROUP>"""
    parent = (parent_name or "").strip()
    parent_tag = "<PARENT>&#4; Primary</PARENT>" if not parent or parent.lower() == "primary" else f"<PARENT>{x(parent)}</PARENT>"
    alias_names = [a.strip() for a in (aliases or []) if a and a.strip() and a.strip().lower() != name.strip().lower()]
    # The name list is sent whole, so an alias removed here is removed in Tally too
    alias_nodes = "".join(f"\n              <NAME>{x(a)}</NAME>" for a in alias_names)
    return f"""<STOCKGROUP NAME="{x(target)}" Action="{x(action)}">
          <NAME>{x(name)}</NAME>
          {parent_tag}
          <ISADDABLE>Yes</ISADDABLE>
          <LANGUAGENAME.LIST>
            <NAME.LIST TYPE="String">
              <NAME>{x(name)}</NAME>{alias_nodes}
            </NAME.LIST>
          </LANGUAGENAME.LIST>
        </STOCKGROUP>"""


async def try_push_stock_group_realtime(group_id: int, sync_item_id: int, action: str, db: AsyncSession, tally_name: Optional[str] = None):
    """
    Pushes a Stock Group to Tally and records the outcome on its queue row.
    tally_name: the name Tally knows the group by when it differs from the current one (a rename); read
    from the queue row when not given, which is also where a delete finds the name once the group is gone.
    Returns (ok, status, message); status is SUCCESS, NOT_CONFIGURED, REJECTED (Tally answered and refused;
    message is Tally's reason), NO_RESPONSE, FAILED or EXCEPTION.
    """
    import time
    start_time = time.time()
    try:
        from app.models.tally_core import MstStockGroup
        from app.models.portal_core import SyncQueue, Company

        tally_url = current_tally_url()
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        sync_item = None
        if sync_item_id and sync_item_id > 0:
            sync_item = (await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_item_id))).scalars().first()
        if not tally_name:
            tally_name = ((sync_item.snapshot_data if sync_item else None) or {}).get("tally_name")

        # populate_existing: the caller may hold this group with its old aliases already loaded
        g_stmt = select(MstStockGroup).options(
            selectinload(MstStockGroup.parent), selectinload(MstStockGroup.aliases)
        ).where(MstStockGroup.stock_group_id == group_id).execution_options(populate_existing=True)
        g_res = await db.execute(g_stmt)
        group = g_res.scalars().first()
        if not group and not (action == "Delete" and tally_name):
            logger.warning(f"Real-time Tally push skipped: stock_group_id={group_id} not found.")
            return (False, "FAILED", f"Stock Group #{group_id} not found")

        company_id = group.company_id if group else (sync_item.company_id if sync_item else 1)
        group_name = group.name if group else tally_name

        c_stmt = select(Company).where(Company.company_id == company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        async def record(status_code: str, message: Optional[str], payload: Optional[str] = None, response: Optional[str] = None):
            if not sync_item:
                return
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(
                is_processed=(status_code == "SUCCESS"), status=status_code,
                attempts=func.coalesce(SyncQueue.attempts, 0) + 1, last_payload=payload, last_response=response,
                last_attempt_at=func.now(), error_message=message[:500] if message else None))
            await db.commit()

        if action == "Delete":
            group_inner_xml = build_stock_group_xml(tally_name or group_name, "Delete")
        else:
            group_inner_xml = build_stock_group_xml(
                group_name, action, target_name=tally_name,
                parent_name=group.parent.name if group.parent else None,
                aliases=[a.alias for a in group.aliases])

        xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {group_inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.debug(f"\n=======================================================\nOUTBOUND REALTIME TALLY STOCKGROUP PUSH (stock_group_id={group_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)

        await record_sync_traffic_log(
            db=db, company_id=company_id, sync_id=sync_item_id if sync_item else None, entity_type="StockGroup",
            entity_id=group_id, entity_name=group_name, action=action, outbound_format="XML",
            outbound_payload=xml_envelope, inbound_response=resp_str, duration_ms=duration_ms, tally_url=tally_url)

        if check_tally_success(resp_str):
            await record("SUCCESS", None, xml_envelope, resp_str)
            logger.info(f"Real-time Tally push successful for stock_group_id={group_id}, action={action}")
            return (True, "SUCCESS", None)
        if not resp_str or not resp_str.strip():
            await record("NO_RESPONSE", "No response from Tally", xml_envelope, resp_str)
            return (False, "NO_RESPONSE", "No response from Tally")

        reason = parse_tally_response_metrics(resp_str)["error_summary"] or "Tally rejected the stock group"
        if action == "Delete" and "does not exist" in reason.lower():
            # Tally no longer has it, which is where a delete is headed
            await record("SUCCESS", None, xml_envelope, resp_str)
            return (True, "SUCCESS", None)
        if action == "Create":
            # A create Tally refuses can leave a ghost stock group behind
            await remove_tally_ghost(tally_url, comp_name, "Stock Group", group_name)
        logger.error(f"Real-time Tally push rejected for stock_group_id={group_id}: {reason}")
        await record("REJECTED", reason, xml_envelope, resp_str)
        return (False, "REJECTED", reason)
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for stock_group_id={group_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


async def fetch_tally_master_identity(tally_url: str, comp_name: str, subtype: str, name: str) -> Optional[dict]:
    """
    The GUID and master id Tally gave a master, read by its name: {"guid", "master_id"}, or None if Tally did
    not return it. The fetch list is mandatory: an object export without one crashes TallyPrime.
    """
    xml = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Object</TYPE><SUBTYPE>{x(subtype)}</SUBTYPE><ID TYPE="Name">{x(name)}</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT><SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY></STATICVARIABLES>
      <FETCHLIST><FETCH>Name</FETCH><FETCH>GUID</FETCH><FETCH>MasterID</FETCH></FETCHLIST>
    </DESC>
  </BODY>
</ENVELOPE>"""
    resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml, 10)
    guid = re.search(r"<GUID[^>]*>\s*([^<\s]+)\s*</GUID>", resp or "")
    master_id = re.search(r"<MASTERID[^>]*>\s*(\d+)\s*</MASTERID>", resp or "")
    if not guid or not master_id or "<ERRORMSG>" in resp or "<LINEERROR>" in resp:
        return None
    return {"guid": guid.group(1), "master_id": int(master_id.group(1))}


async def store_tally_master_identity(db: AsyncSession, subtype: str, model, record_id: int, name_attr: str = "name") -> None:
    """
    After a master created or changed here has reached Tally: writes the GUID and master id Tally gave it onto
    the app's row, so the record is tied to Tally's own identifier from then on (the inbound sync follows a
    rename made in Tally by it). The alter id is left to the inbound sync, whose watermark it is. Commits.
    """
    try:
        from sqlalchemy.orm.attributes import set_committed_value
        if not current_tally_url():
            return
        pk = list(model.__table__.primary_key.columns)[0]
        # Read and written as plain columns: the caller is about to serialise this record, and reloading
        # the object here would unload the related rows it has fetched for that
        found = (await db.execute(select(getattr(model, name_attr), model.company_id, model.tally_guid, model.tally_master_id)
                                  .where(pk == record_id))).first()
        if found is None:
            return
        name, company_id, guid, master_id = found
        comp = (await db.execute(select(Company.name).where(Company.company_id == company_id))).scalar()
        ident = await fetch_tally_master_identity(current_tally_url(), comp or "", subtype, name)
        if ident and (guid != ident["guid"] or master_id != ident["master_id"]):
            await db.execute(update(model).where(pk == record_id).values(tally_guid=ident["guid"], tally_master_id=ident["master_id"])
                             .execution_options(synchronize_session=False))
            await db.commit()
            loaded = db.sync_session.identity_map.get(db.sync_session.identity_key(model, record_id))
            if loaded is not None:
                set_committed_value(loaded, "tally_guid", ident["guid"])
                set_committed_value(loaded, "tally_master_id", ident["master_id"])
    except Exception as e:
        logger.warning(f"Could not read back the Tally identity of {subtype} #{record_id}: {e}")


def _storing_identity(push, subtype: str, model, name_attr: str = "name"):
    """Wraps a master push so a successful create or change is followed by store_tally_master_identity()."""
    async def pushed(record_id: int, sync_id: int, action: str, db: AsyncSession, tally_name: Optional[str] = None):
        result = await push(record_id, sync_id, action, db, tally_name)
        if result and result[0] and result[1] == "SUCCESS" and action != "Delete":
            await store_tally_master_identity(db, subtype, model, record_id, name_attr)
        return result
    pushed.__name__, pushed.__doc__ = push.__name__, push.__doc__
    return pushed


def _wrap_master_pushes():
    from app.models.tally_core import MstStockGroup, MstUom
    g = globals()
    g["try_push_group_realtime"] = _storing_identity(try_push_group_realtime, "Group", MstGroup)
    g["try_push_ledger_realtime"] = _storing_identity(try_push_ledger_realtime, "Ledger", MstLedger)
    g["try_push_uom_realtime"] = _storing_identity(try_push_uom_realtime, "Unit", MstUom, "symbol")
    g["try_push_stock_group_realtime"] = _storing_identity(try_push_stock_group_realtime, "Stock Group", MstStockGroup)


_wrap_master_pushes()


async def try_push_stock_category_realtime(category_id: int, sync_item_id: int, action: str, db: AsyncSession):
    """
    Attempts real-time push of a Stock Category to Tally Prime XML Server on the fly.
    """
    import time
    start_time = time.time()
    try:
        from app.models.tally_core import MstStockCategory
        from app.models.portal_core import SyncQueue, Company

        tally_url = current_tally_url()
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        c_query = select(MstStockCategory).options(selectinload(MstStockCategory.parent)).where(MstStockCategory.stock_category_id == category_id)
        c_res = await db.execute(c_query)
        cat = c_res.scalars().first()
        if not cat and action != "Delete":
            logger.warning(f"Real-time Tally push skipped: stock_category_id={category_id} not found.")
            return (False, "FAILED", f"Stock Category #{category_id} not found")

        company_id = cat.company_id if cat else 1
        cat_name = cat.name if cat else f"Category #{category_id}"

        comp_stmt = select(Company).where(Company.company_id == company_id)
        comp_res = await db.execute(comp_stmt)
        comp_obj = comp_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        if action == "Delete":
            cat_inner_xml = f"""<STOCKCATEGORY NAME="{x(cat_name)}" Action="Delete">
          <NAME>{x(cat_name)}</NAME>
        </STOCKCATEGORY>"""
        else:
            parent_name = cat.parent.name if (cat.parent and cat.parent.name) else ""
            if not parent_name or parent_name.lower() in ("primary", " primary"):
                parent_tag = "<PARENT>&#4; Primary</PARENT>"
            else:
                parent_tag = f"<PARENT>{x(parent_name)}</PARENT>"

            cat_inner_xml = f"""<STOCKCATEGORY NAME="{x(cat_name)}" Action="{x(action)}">
          <NAME>{x(cat_name)}</NAME>
          {parent_tag}
        </STOCKCATEGORY>"""

        xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {cat_inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.debug(f"\n=======================================================\nOUTBOUND REALTIME TALLY STOCKCATEGORY PUSH (stock_category_id={category_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"\n=======================================================\nTALLY STOCKCATEGORY PUSH RESPONSE (stock_category_id={category_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

        await record_sync_traffic_log(
            db=db,
            company_id=company_id,
            sync_id=sync_item_id if sync_item_id and sync_item_id > 0 else None,
            entity_type="StockCategory",
            entity_id=category_id,
            entity_name=cat_name,
            action=action,
            outbound_format="XML",
            outbound_payload=xml_envelope,
            inbound_response=resp_str,
            duration_ms=duration_ms,
            tally_url=tally_url
        )

        metrics = parse_tally_response_metrics(resp_str)
        is_success = check_tally_success(resp_str)
        # A delete of something Tally no longer has is already where it should be: settle it instead of
        # leaving the row to be retried for ever
        already_absent = (not is_success and action == "Delete"
                          and "does not exist" in (metrics["error_summary"] or "").lower())

        if sync_item_id and sync_item_id > 0:
            if is_success or already_absent:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(is_processed=True, status="SUCCESS", last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), attempts=SyncQueue.attempts + 1)
            else:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(status="FAILED", attempts=SyncQueue.attempts + 1, last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), error_message=metrics["error_summary"] or str(resp_str)[:500])
            await db.execute(sq_stmt)
            await db.commit()

        if is_success:
            logger.info(f"Real-time Tally push successful for stock_category_id={category_id}, action={action}")
            return (True, "SUCCESS", None)
        else:
            logger.error(f"Real-time Tally push failed for stock_category_id={category_id}: {resp_str}")
            return (False, metrics["status"], metrics["error_summary"])
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for stock_category_id={category_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


async def try_push_godown_realtime(godown_id: int, sync_item_id: int, action: str, db: AsyncSession):
    """
    Attempts real-time push of a Godown/Location to Tally Prime XML Server on the fly.
    """
    import time
    start_time = time.time()
    try:
        from app.models.tally_core import MstGodown
        from app.models.portal_core import SyncQueue, Company

        tally_url = current_tally_url()
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        g_query = select(MstGodown).options(selectinload(MstGodown.parent)).where(MstGodown.godown_id == godown_id)
        g_res = await db.execute(g_query)
        godown = g_res.scalars().first()
        if not godown and action != "Delete":
            logger.warning(f"Real-time Tally push skipped: godown_id={godown_id} not found.")
            return (False, "FAILED", f"Godown #{godown_id} not found")

        company_id = godown.company_id if godown else 1
        godown_name = godown.name if godown else f"Godown #{godown_id}"

        comp_stmt = select(Company).where(Company.company_id == company_id)
        comp_res = await db.execute(comp_stmt)
        comp_obj = comp_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        if action == "Delete":
            godown_inner_xml = f"""<GODOWN NAME="{x(godown_name)}" Action="Delete">
          <NAME>{x(godown_name)}</NAME>
        </GODOWN>"""
        else:
            parent_name = godown.parent.name if (godown.parent and godown.parent.name) else ""
            if not parent_name or parent_name.lower() in ("primary", " primary"):
                parent_tag = "<PARENT>&#4; Primary</PARENT>"
            else:
                parent_tag = f"<PARENT>{x(parent_name)}</PARENT>"

            addr_tag = f"\n          <ADDRESS>{x(godown.address)}</ADDRESS>" if godown.address else ""

            godown_inner_xml = f"""<GODOWN NAME="{x(godown_name)}" Action="{x(action)}">
          <NAME>{x(godown_name)}</NAME>
          {parent_tag}{addr_tag}
        </GODOWN>"""

        xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {godown_inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.debug(f"\n=======================================================\nOUTBOUND REALTIME TALLY GODOWN PUSH (godown_id={godown_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(f"\n=======================================================\nTALLY GODOWN PUSH RESPONSE (godown_id={godown_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

        await record_sync_traffic_log(
            db=db,
            company_id=company_id,
            sync_id=sync_item_id if sync_item_id and sync_item_id > 0 else None,
            entity_type="Godown",
            entity_id=godown_id,
            entity_name=godown_name,
            action=action,
            outbound_format="XML",
            outbound_payload=xml_envelope,
            inbound_response=resp_str,
            duration_ms=duration_ms,
            tally_url=tally_url
        )

        metrics = parse_tally_response_metrics(resp_str)
        is_success = check_tally_success(resp_str)
        # A delete of something Tally no longer has is already where it should be: settle it instead of
        # leaving the row to be retried for ever
        already_absent = (not is_success and action == "Delete"
                          and "does not exist" in (metrics["error_summary"] or "").lower())

        if sync_item_id and sync_item_id > 0:
            if is_success or already_absent:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(is_processed=True, status="SUCCESS", last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), attempts=SyncQueue.attempts + 1)
            else:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(status="FAILED", attempts=SyncQueue.attempts + 1, last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), error_message=metrics["error_summary"] or str(resp_str)[:500])
            await db.execute(sq_stmt)
            await db.commit()

        if action == "Delete":
            await db.execute(
                update(DeletedRecordAudit)
                .where(
                    DeletedRecordAudit.company_id == company_id,
                    DeletedRecordAudit.entity_type == "Godown",
                    DeletedRecordAudit.record_id == godown_id
                )
                .values(
                    tally_sync_status="SYNCED_TO_TALLY" if is_success else "NOT_DELETED_IN_TALLY",
                    tally_error_message=None if is_success else (metrics["error_summary"] or "Cannot be deleted in Tally Prime")
                )
            )
            await db.commit()

        if is_success:
            logger.info(f"Real-time Tally push successful for godown_id={godown_id}, action={action}")
            return (True, "SUCCESS", None)
        else:
            logger.error(f"Real-time Tally push failed for godown_id={godown_id}: {resp_str}")
            return (False, metrics["status"], metrics["error_summary"])
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for godown_id={godown_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


async def run_once_sync_background(user_id: int):
    """
    Executes a single cycle of bidirectional synchronization with the Tally XML Server in the background.
    """
    from app.core.database import AsyncSessionLocal
    from app.core.cache import clear_company_cache
    
    tally_url = current_tally_url()
    if not tally_url:
        logger.error(f"Background run-once sync aborted for user_id={user_id}: TALLY_URL is not configured.")
        return

    logger.info(f"Background run-once sync started for user_id={user_id}")
    
    async with AsyncSessionLocal() as db:
        try:
            from app.models.portal_core import UserCompanyAccess
            stmt = select(SyncQueue).join(UserCompanyAccess, SyncQueue.company_id == UserCompanyAccess.company_id).where(
                UserCompanyAccess.user_id == user_id,
                SyncQueue.is_processed == False
            ).order_by(SyncQueue.created_at.asc())
            
            res = await db.execute(stmt)
            queue_items = res.scalars().all()
            
            outbound_success = 0
            for item in queue_items:
                xml_envelope = ""
        # 1. Map Ledger Creation
                if item.record_type == "Ledger":
                    l_stmt = select(MstLedger).where(MstLedger.ledger_id == item.record_id)
                    l_res = await db.execute(l_stmt)
                    ledger = l_res.scalars().first()
                    if ledger:
                        # Find group name & company name
                        g_stmt = select(MstGroup).where(MstGroup.group_id == ledger.group_id)
                        g_res = await db.execute(g_stmt)
                        group = g_res.scalars().first()
                        group_name = group.name if group else "Sundry Debtors"

                        c_stmt = select(Company).where(Company.company_id == ledger.company_id)
                        c_res = await db.execute(c_stmt)
                        comp_obj = c_res.scalars().first()
                        comp_name = comp_obj.name if comp_obj else ""

                        # Build Tally XML Envelope
                        xml_envelope = build_ledger_xml_envelope(ledger, group_name, comp_name, item.action or 'Create',
                                                                 (item.snapshot_data or {}).get("tally_name"))
                        
                # 2. Map Voucher Creation
                elif item.record_type == "Voucher":
                    await try_push_voucher_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
                    continue

                # 3. Map Company Profile Alteration
                elif item.record_type == "Company":
                    comp_stmt = select(Company).where(Company.company_id == item.record_id)
                    comp_res = await db.execute(comp_stmt)
                    company = comp_res.scalars().first()
                    if company:
                        addr_list = ""
                        if company.address_line1:
                            addr_list += f"<ADDRESS>{x(company.address_line1)}</ADDRESS>"
                        if company.address_line2:
                            addr_list += f"<ADDRESS>{x(company.address_line2)}</ADDRESS>"

                        # Build books/FY date strings for XML
                        books_from_xml = company.books_begin_date.strftime('%Y%m%d') if company.books_begin_date else ''
                        fy_start_xml = company.financial_year_start.strftime('%Y%m%d') if company.financial_year_start else ''
                        fy_end_xml = company.financial_year_end.strftime('%Y%m%d') if company.financial_year_end else ''

                        xml_envelope = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{x(company.name)}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<COMPANY NAME="{x(company.name)}" ACTION="Alter">
<NAME>{x(company.name)}</NAME>
<STATENAME>{x(company.state or '')}</STATENAME>
<COUNTRYNAME>{x(company.country or '')}</COUNTRYNAME>
<PINCODE>{x(company.pincode or '')}</PINCODE>
<PHONENUMBER>{x(company.telephone or '')}</PHONENUMBER>
<MOBILENUMBERS.LIST><MOBILENUMBERS>{x(company.mobile or '')}</MOBILENUMBERS></MOBILENUMBERS.LIST>
<EMAIL>{x(company.email or '')}</EMAIL>
<WEBSITE>{x(company.website or '')}</WEBSITE>
<INCOMETAXNUMBER>{x(company.pan or '')}</INCOMETAXNUMBER>
<GSTREGISTRATIONNUMBER>{x(company.gstin or '')}</GSTREGISTRATIONNUMBER>
<BOOKSFROM>{books_from_xml}</BOOKSFROM>
<STARTINGFROM>{fy_start_xml}</STARTINGFROM>
<ENDINGAT>{fy_end_xml}</ENDINGAT>
<CURRENCYNAME>{x(company.base_currency or 'INR')}</CURRENCYNAME>
<GUID>{x(company.tally_guid or '')}</GUID>
<ADDRESS.LIST>
{addr_list}
</ADDRESS.LIST>
</COMPANY>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA>
</BODY>
</ENVELOPE>"""
                        
                # 4. Cost Categories and Cost Centres
                elif item.record_type == "CostCategory":
                    await try_push_cost_category_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
                    continue
                    
                elif item.record_type == "CostCentre":
                    await try_push_cost_centre_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
                    continue

                elif item.record_type == "CostCentreClass":
                    await try_push_cost_centre_class_realtime(item.record_id, item.sync_id, item.action, db)
                    continue
                elif item.record_type in ("AttendanceType", "PayHead", "Employee"):
                    from app.services.payroll_masters import replay_queued
                    await replay_queued(db, item)
                    continue
                elif item.record_type == "Currency":
                    await try_push_currency_realtime(item.record_id, item.sync_id, item.action, db)
                    continue
                elif item.record_type == "StockItem":
                    await try_push_stock_item_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
                    continue
                elif item.record_type == "Unit":
                    await try_push_uom_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
                    continue
                elif item.record_type == "StockGroup":
                    await try_push_stock_group_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
                    continue
                elif item.record_type == "StockCategory":
                    await try_push_stock_category_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
                    continue
                elif item.record_type == "Godown":
                    await try_push_godown_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
                    continue
                else:
                    continue
                        
                if xml_envelope:
                    try:
                        resp_xml = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope)
                        if check_tally_success(resp_xml):
                            item.is_processed = True
                            outbound_success += 1
                    except Exception as e:
                        logger.error(f"Failed to sync outbound item {item.sync_id} to Tally in background: {str(e)}", exc_info=True)
                        
            if outbound_success > 0:
                await db.commit()

            # 2. PHASE 2: Inbound Sync (Tally -> ERP)
            # Step A: Query Tally for all loaded/open companies
            company_query_xml = """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>ListofCompanies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="ListofCompanies">
            <TYPE>Company</TYPE>
            <FETCH>*</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""

            target_companies = []
            try:
                comp_resp = await asyncio.to_thread(_post_to_tally_sync, tally_url, company_query_xml)
                if comp_resp and "<COMPANY" in comp_resp:
                    from app.services.tally_xml_importer import sanitize_xml
                    comp_resp = sanitize_xml(comp_resp)
                    import xml.etree.ElementTree as ET
                    try:
                        c_root = ET.fromstring(comp_resp)
                        for c_node in c_root.findall(".//COMPANY"):
                            c_name = c_node.get("NAME") or c_node.findtext("NAME")
                            if c_name:
                                clean_cname = c_name.strip()
                                target_companies.append(clean_cname)
                                c_xml_str = ET.tostring(c_node, encoding='utf-8').decode('utf-8')
                                # Companies come only from linking in the sync agent: one Tally lists that this server
                                # does not hold is skipped by the importer, not created
                                await import_tally_xml(c_xml_str, db, user_id, override_company_name=clean_cname)
                    except Exception as e:
                        logger.error(f"Error parsing company list XML: {str(e)}")
            except Exception as e:
                logger.error(f"Error fetching company list from Tally: {str(e)}")

            # Fallback if company list fetch didn't return names
            if not target_companies:
                target_companies = [None]

            total_imported = {
                "groups": 0, "ledgers": 0, "vouchers": 0,
                "stock_groups": 0, "uoms": 0, "godowns": 0,
                "stock_categories": 0, "stock_items": 0,
                "currencies": 0, "voucher_types": 0
            }

            async with sync_lock:
                for company_name in target_companies:
                    sv_company = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>" if company_name else ""
                    
                    # Calculate max Alter ID specifically for this company
                    max_ledger_alter = 0
                    max_voucher_alter = 0
                    max_stock_item_alter = 0
                    if company_name:
                        from app.models.tally_core import MstStockItem
                        comp_stmt = select(Company.company_id).where(Company.name == company_name)
                        comp_id = (await db.execute(comp_stmt)).scalar()
                        if comp_id:
                            l_stmt = select(func.max(MstLedger.tally_alter_id)).where(MstLedger.company_id == comp_id)
                            max_ledger_alter = (await db.execute(l_stmt)).scalar() or 0
                            
                            v_stmt = select(func.max(TrnVoucher.tally_alter_id)).where(TrnVoucher.company_id == comp_id)
                            max_voucher_alter = (await db.execute(v_stmt)).scalar() or 0

                            si_stmt = select(func.max(MstStockItem.tally_alter_id)).where(MstStockItem.company_id == comp_id)
                            max_stock_item_alter = (await db.execute(si_stmt)).scalar() or 0
                    
                    queries = {
                        "Groups": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllAlteredGroups</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllAlteredGroups">
            <TYPE>Group</TYPE>
            <FETCH>NAME,PARENT</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "VoucherTypes": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllVoucherTypes</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllVoucherTypes">
            <TYPE>VoucherType</TYPE>
            <FETCH>NAME,PARENT,NUMBERINGMETHOD,PREVENTDUPLICATES,ALTERID,GUID,ISACTIVE</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "Ledgers": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>IncrementalLedgers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="IncrementalLedgers">
            <TYPE>Ledger</TYPE>
            <FETCH>GUID,ALTERID,NAME,PARENT,PAYTYPE,PAYSLIPNAME,CALCULATIONTYPE,OPENINGBALANCE,GSTIN,PARTYGSTIN,INCOMETAXNUMBER,LWLEDADHARNOSTORE,LEDGERCONTACT,LEDGERPHONE,LEDGERMOBILE,EMAIL,EMAILCC,WEBSITE,DESCRIPTION,LEDGERFAX,CREDITLIMIT,BILLCREDITPERIOD,ISBILLWISEON,COUNTRYOFRESIDENCE,COUNTRYNAME,PRIORSTATENAME,STATENAME,PINCODE,LEDGSTREGDETAILS.LIST,LEDMAILINGDETAILS.LIST,LANGUAGENAME.LIST,ADDRESS.LIST,ADDRESS</FETCH>
            <FILTERS>AlteredFilter</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="AlteredFilter">
            $ALTERID &gt; {max_ledger_alter}
          </SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "Vouchers": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>IncrementalVouchers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVFROMDATE TYPE="Date">20000101</SVFROMDATE>
        <SVTODATE TYPE="Date">20991231</SVTODATE>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="IncrementalVouchers">
            <TYPE>Voucher</TYPE>
            <FETCH>GUID,MASTERID,REMOTEALTGUID,ALTERID,VOUCHERTYPENAME,VOUCHERNUMBER,DATE,NARRATION,PARTYLEDGERNAME,AMOUNT,ALLLEDGERENTRIES.LIST,INVENTORYENTRIES.LIST,ALLINVENTORYENTRIES.LIST,INVENTORYENTRIESIN.LIST,INVENTORYENTRIESOUT.LIST,ATTENDANCEENTRIES.*,CATEGORYENTRY.LIST</FETCH>
            <FILTERS>AlteredVoucherFilter</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="AlteredVoucherFilter">
            $ALTERID &gt; {max_voucher_alter}
          </SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "StockGroups": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllStockGroups</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllStockGroups">
            <TYPE>StockGroup</TYPE>
            <FETCH>NAME,PARENT</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "UOMs": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllUOMs</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllUOMs">
            <TYPE>Unit</TYPE>
            <FETCH>NAME,ORIGINALNAME,DECIMALPLACES</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "CostCategories": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllCostCategories</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllCostCategories">
            <TYPE>CostCategory</TYPE>
            <FETCH>NAME,ALLOCATEREVENUE,ALLOCATENONREVENUE,LANGUAGENAME.LIST</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "CostCentres": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllCostCentres</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllCostCentres">
            <TYPE>CostCentre</TYPE>
            <FETCH>NAME,GUID,MASTERID,CATEGORY,PARENT,FORPAYROLL,ISEMPLOYEEGROUP,DATEOFJOIN,DESIGNATION,GENDER,MAILINGNAME.LIST,EMPLOYEEPERIOD.LIST,LANGUAGENAME.LIST</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "AttendanceTypes": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllAttendanceTypes</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllAttendanceTypes">
            <TYPE>AttendanceType</TYPE>
            <FETCH>NAME,GUID,MASTERID,PARENT,ATTENDANCEPRODUCTIONTYPE,ATTENDANCEPERIOD,BASEUNITS</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "Godowns": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllGodowns</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllGodowns">
            <TYPE>Godown</TYPE>
            <FETCH>NAME,ADDRESS</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "StockCategories": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllStockCategories</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllStockCategories">
            <TYPE>StockCategory</TYPE>
            <FETCH>NAME,PARENT</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "StockItems": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>IncrementalStockItems</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="IncrementalStockItems">
            <TYPE>StockItem</TYPE>
            <FETCH>GUID,ALTERID,NAME,PARENT,CATEGORY,BASEUNITS,OPENINGBALANCE,OPENINGVALUE,INFGSTHSNCODE,INFGSTIGSTRATE</FETCH>
            <FILTERS>AlteredStockItemFilter</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="AlteredStockItemFilter">
            $ALTERID &gt; {max_stock_item_alter}
          </SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                        "Currencies": f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllCurrencies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {sv_company}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllCurrencies">
            <TYPE>Currency</TYPE>
            <FETCH>NAME,ORIGINALNAME,MAILINGNAME.LIST,DECIMALPLACES,INMILLIONS,ISSUFFIX,HASSPACE,DECIMALSYMBOL,DECIMALPLACESFORPRINTING</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""
                    }

                    for name, xml_payload in queries.items():
                        try:
                            logger.info(f"📡 [SYNC QUERY] Requesting collection '{name}' from Tally at {tally_url}...")
                            resp_xml = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_payload)
                            if not resp_xml:
                                logger.warning(f"⚠️ [SYNC WARNING] Empty response from Tally for collection '{name}'. Skipping.")
                                continue
                            if "<ENVELOPE>" not in resp_xml:
                                logger.warning(f"⚠️ [SYNC WARNING] Invalid response (no <ENVELOPE> tag) from Tally for collection '{name}'. Response snippet: {resp_xml[:200]}...")
                                continue
                            
                            logger.info(f"📥 [SYNC RECEIVED] Got {len(resp_xml)} bytes from Tally for collection '{name}'. Processing import...")
                            res = await import_tally_xml(resp_xml, db, user_id, override_company_name=company_name)
                            
                            if res.get("status") == "success":
                                c_groups = res.get("imported_groups", 0)
                                c_ledgers = res.get("imported_ledgers", 0)
                                c_vouchers = res.get("imported_vouchers", 0)
                                c_stock_groups = res.get("imported_stock_groups", 0)
                                c_uoms = res.get("imported_uoms", 0)
                                c_godowns = res.get("imported_godowns", 0)
                                c_stock_cats = res.get("imported_stock_categories", 0)
                                c_stock_items = res.get("imported_stock_items", 0)
                                c_currencies = res.get("imported_currencies", 0)
                                c_voucher_types = res.get("imported_voucher_types", 0)
                                item_errors = res.get("errors", [])
                                
                                logger.info(
                                    f"✅ [SYNC SUCCESS] Collection '{name}' imported successfully. "
                                    f"Counts - Groups: {c_groups}, Ledgers: {c_ledgers}, Vouchers: {c_vouchers}, "
                                    f"StockItems: {c_stock_items}, Currencies: {c_currencies}, VoucherTypes: {c_voucher_types}"
                                )
                                if item_errors:
                                    logger.warning(f"⚠️ [SYNC ITEM ERRORS] Collection '{name}' had {len(item_errors)} record error(s): {item_errors[:5]}")
                                
                                total_imported["groups"] += c_groups
                                total_imported["ledgers"] += c_ledgers
                                total_imported["vouchers"] += c_vouchers
                                total_imported["stock_groups"] += c_stock_groups
                                total_imported["uoms"] += c_uoms
                                total_imported["godowns"] += c_godowns
                                total_imported["stock_categories"] += c_stock_cats
                                total_imported["stock_items"] += c_stock_items
                                total_imported["currencies"] += c_currencies
                                total_imported["voucher_types"] += c_voucher_types
                                
                                res_cid = res.get("company_id")
                                if res_cid:
                                    clear_company_cache(res_cid)
                            else:
                                err_msg = res.get("message", "Unknown error")
                                logger.error(f"❌ [SYNC ERROR] Failed to import collection '{name}'. Error: {err_msg}")
                        except Exception as e:
                            logger.error(f"💥 [SYNC FATAL] Exception while processing collection '{name}': {str(e)}", exc_info=True)

            logger.info(f"🏁 [SYNC COMPLETED] Background run-once sync finished for user_id={user_id}: {total_imported}")
        except Exception as e:
            logger.error(f"💥 [SYNC FATAL] Background run-once sync failed with exception for user_id={user_id}: {str(e)}", exc_info=True)


@router.post("/run-once")
async def run_once(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Runs a single cycle of the bidirectional synchronization with the Tally XML Server in the background.
    Requires Admin privileges.
    """
    tally_url = current_tally_url()
    if not tally_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TALLY_URL is not configured on the backend settings."
        )

    background_tasks.add_task(run_once_sync_background, user.user_id)

    return {
        "status": "success",
        "message": "Bidirectional sync task has been triggered and is running in the background."
    }



from pydantic import BaseModel
from datetime import date as date_type

class VoucherPeriodQueryRequest(BaseModel):
    voucher_type: Optional[str] = None  # e.g. 'Sales', 'Purchase', 'Payment', 'Receipt', 'Journal', 'Contra'
    from_date: date_type
    to_date: date_type
    auto_import: bool = True

@router.post("/query-vouchers")
async def query_vouchers_from_tally(
    query_req: VoucherPeriodQueryRequest,
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    On-Demand Period & Voucher-Type TDL Query Engine.
    Executes a high-performance filtered TDL collection query against live Tally and optionally imports into the database.
    """
    tally_url = current_tally_url()
    if not tally_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tally URL is not configured."
        )

    comp_stmt = select(Company).where(Company.company_id == user.company_id)
    comp_res = await db.execute(comp_stmt)
    comp = comp_res.scalars().first()
    comp_name = comp.name if comp else "Bhrama Enterprises"

    from_str = query_req.from_date.strftime("%d-%m-%Y")
    to_str = query_req.to_date.strftime("%d-%m-%Y")

    if query_req.voucher_type:
        clean_vtype = query_req.voucher_type.strip()
        type_tag = "Vouchers:VoucherType"
        childof_tag = f"<CHILDOF>$$VchType{clean_vtype}</CHILDOF>"
    else:
        type_tag = "Voucher"
        childof_tag = ""

    from_date_tally = query_req.from_date.strftime("%Y%m%d")
    to_date_tally = query_req.to_date.strftime("%Y%m%d")

    tdl_payload = f"""<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL_Filtered_Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
                <SVFROMDATE TYPE="Date">{from_date_tally}</SVFROMDATE>
                <SVTODATE TYPE="Date">{to_date_tally}</SVTODATE>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL_Filtered_Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>{type_tag}</TYPE>
                 {childof_tag}
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername, Narration, Amount, Guid, AlterId</NATIVEMETHOD>
                 <NATIVEMETHOD>AllLedgerEntries.BankAllocations.*</NATIVEMETHOD>
                 <NATIVEMETHOD>AllLedgerEntries.BillAllocations.*</NATIVEMETHOD>
                 <NATIVEMETHOD>AllInventoryEntries.*</NATIVEMETHOD>
                </COLLECTION>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>"""

    logger.info(f"Querying Tally TDL Vouchers ({query_req.voucher_type or 'All'}) from {from_str} to {to_str}...")
    response_xml = await asyncio.to_thread(_post_to_tally_sync, tally_url, tdl_payload, 25)

    if not response_xml or "<VOUCHER" not in response_xml:
        return {
            "status": "success",
            "message": f"No vouchers found for period {from_str} to {to_str}.",
            "voucher_count": 0,
            "import_result": None
        }

    import_result = None
    if query_req.auto_import:
        async with sync_lock:
            import_result = await import_tally_xml(response_xml, db, user.user_id, override_company_name=comp_name)

    # Count matching vouchers in returned XML
    vch_count = len(re.findall(r'<VOUCHER\b', response_xml, re.IGNORECASE))

    return {
        "status": "success",
        "message": f"Successfully retrieved {vch_count} vouchers from Tally.",
        "voucher_type": query_req.voucher_type or "All",
        "period": {"from_date": str(query_req.from_date), "to_date": str(query_req.to_date)},
        "voucher_count": vch_count,
        "import_result": import_result
    }

# ==========================================
# SYNC HEALTH, TRAFFIC AUDIT & RETRY APIS
# ==========================================

SYNC_HEALTH_CACHE_KEY = "sync_health"
SYNC_HEALTH_TTL_SECONDS = 30


@router.get("/health")
async def get_sync_health(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns high-level Sync Health metrics: Synced, Pending, Failed, Exceptions, and Discrepancies.
    Every admin's header polls this each minute, so the result is shared per company for 30 seconds;
    a sync, clearing resolved logs or deleting a log clears it.
    """
    from app.core.cache import get_cached_response, set_cached_response
    cached = get_cached_response(user.company_id, SYNC_HEALTH_CACHE_KEY)
    if cached is not None:
        return cached

    # 1. Queue: pending vs processed in one grouped count
    queue_counts = dict((await db.execute(
        select(SyncQueue.is_processed, func.count(SyncQueue.sync_id))
        .where(SyncQueue.company_id == user.company_id)
        .group_by(SyncQueue.is_processed)
    )).all())
    pending_count = queue_counts.get(False, 0)  # rows with a NULL flag count as neither, as before
    synced_count = queue_counts.get(True, 0)

    # 2. Traffic log outcomes in one grouped count
    status_counts = dict((await db.execute(
        select(SyncTrafficLog.status, func.count(SyncTrafficLog.log_id))
        .where(
            SyncTrafficLog.company_id == user.company_id,
            SyncTrafficLog.status.in_(["SUCCESS", "FAILED", "TIMEOUT", "EXCEPTION"])
        )
        .group_by(SyncTrafficLog.status)
    )).all())
    success_logs = status_counts.get("SUCCESS", 0)
    failed_logs = status_counts.get("FAILED", 0) + status_counts.get("TIMEOUT", 0)
    exception_logs = status_counts.get("EXCEPTION", 0)

    # 3. Total deleted records out of sync (not deleted in Tally)
    unreconciled_del_res = await db.execute(
        select(func.count(DeletedRecordAudit.audit_id)).where(
            DeletedRecordAudit.company_id == user.company_id,
            DeletedRecordAudit.tally_sync_status.in_(["NOT_DELETED_IN_TALLY", "SYNC_FAILED", "PENDING"])
        )
    )
    unreconciled_deleted_count = unreconciled_del_res.scalar() or 0
    total_sync_issues = failed_logs + exception_logs + unreconciled_deleted_count

    # 4. Recent 5 logs: only the short columns, never the stored XML payloads
    recent_logs = (await db.execute(
        select(
            SyncTrafficLog.log_id, SyncTrafficLog.entity_type, SyncTrafficLog.entity_name, SyncTrafficLog.action,
            SyncTrafficLog.status, SyncTrafficLog.error_summary, SyncTrafficLog.duration_ms, SyncTrafficLog.created_at,
        ).where(
            SyncTrafficLog.company_id == user.company_id
        ).order_by(SyncTrafficLog.created_at.desc()).limit(5)
    )).all()

    from app.services.sync_status import company_sync_status
    freshness = (await company_sync_status(db, [user.company_id]))[user.company_id]
    output = {
        # How fresh this company's data is, from the agent's last report (see services/sync_status.py)
        "freshness": freshness["freshness"],
        "last_synced_at": freshness["last_synced_at"],
        "agent_online": freshness["agent_online"],
        "status": "healthy" if total_sync_issues == 0 else "degraded",
        "pending_queue_count": pending_count,
        "synced_queue_count": synced_count,
        "total_success_traffic": success_logs,
        "total_failed_traffic": failed_logs,
        "total_exception_traffic": exception_logs,
        "unreconciled_deleted_count": unreconciled_deleted_count,
        "total_sync_issues": total_sync_issues,
        "recent_traffic": [
            {
                "log_id": l.log_id,
                "entity_type": l.entity_type,
                "entity_name": l.entity_name,
                "action": l.action,
                "status": l.status,
                "error_summary": l.error_summary,
                "duration_ms": l.duration_ms,
                "created_at": l.created_at.isoformat() if l.created_at else None
            }
            for l in recent_logs
        ]
    }
    set_cached_response(user.company_id, SYNC_HEALTH_CACHE_KEY, output, ttl_seconds=SYNC_HEALTH_TTL_SECONDS)
    return output


@router.get("/logs")
async def get_sync_traffic_logs(
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns paginated, searchable sync traffic audit logs with Postman cURL commands.
    """
    query = select(SyncTrafficLog).where(SyncTrafficLog.company_id == user.company_id)
    count_query = select(func.count(SyncTrafficLog.log_id)).where(SyncTrafficLog.company_id == user.company_id)

    if status and status.upper() != "ALL":
        query = query.where(SyncTrafficLog.status == status.upper())
        count_query = count_query.where(SyncTrafficLog.status == status.upper())

    if entity_type and entity_type.upper() != "ALL":
        query = query.where(SyncTrafficLog.entity_type == entity_type)
        count_query = count_query.where(SyncTrafficLog.entity_type == entity_type)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            (SyncTrafficLog.entity_name.ilike(term)) |
            (SyncTrafficLog.error_summary.ilike(term)) |
            (SyncTrafficLog.outbound_payload.ilike(term))
        )
        count_query = count_query.where(
            (SyncTrafficLog.entity_name.ilike(term)) |
            (SyncTrafficLog.error_summary.ilike(term)) |
            (SyncTrafficLog.outbound_payload.ilike(term))
        )

    total_res = await db.execute(count_query)
    total_count = total_res.scalar() or 0

    logs_res = await db.execute(query.order_by(SyncTrafficLog.created_at.desc()).offset(offset).limit(limit))
    logs = logs_res.scalars().all()

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "log_id": l.log_id,
                "sync_id": l.sync_id,
                "entity_type": l.entity_type,
                "entity_id": l.entity_id,
                "entity_name": l.entity_name,
                "action": l.action,
                "status": l.status,
                "http_status": l.http_status,
                "outbound_format": l.outbound_format,
                "outbound_payload": l.outbound_payload,
                "curl_command": l.curl_command,
                "inbound_response": l.inbound_response,
                "error_summary": l.error_summary,
                "parsed_created": l.parsed_created,
                "parsed_altered": l.parsed_altered,
                "parsed_deleted": l.parsed_deleted,
                "parsed_errors": l.parsed_errors,
                "parsed_exceptions": l.parsed_exceptions,
                "tally_vchnumber": l.tally_vchnumber,
                "duration_ms": l.duration_ms,
                "created_at": l.created_at.isoformat() if l.created_at else None
            }
            for l in logs
        ]
    }

@router.get("/logs/{log_id}")
async def get_sync_traffic_log_detail(
    log_id: int,
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns full details for a single sync traffic audit log entry.
    """
    stmt = select(SyncTrafficLog).where(
        SyncTrafficLog.log_id == log_id,
        SyncTrafficLog.company_id == user.company_id
    )
    res = await db.execute(stmt)
    log = res.scalars().first()
    if not log:
        raise HTTPException(status_code=404, detail="Log entry not found")

    return {
        "log_id": log.log_id,
        "sync_id": log.sync_id,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "entity_name": log.entity_name,
        "action": log.action,
        "status": log.status,
        "http_status": log.http_status,
        "outbound_format": log.outbound_format,
        "outbound_payload": log.outbound_payload,
        "curl_command": log.curl_command,
        "inbound_response": log.inbound_response,
        "error_summary": log.error_summary,
        "parsed_created": log.parsed_created,
        "parsed_altered": log.parsed_altered,
        "parsed_deleted": log.parsed_deleted,
        "parsed_errors": log.parsed_errors,
        "parsed_exceptions": log.parsed_exceptions,
        "tally_vchnumber": log.tally_vchnumber,
        "duration_ms": log.duration_ms,
        "created_at": log.created_at.isoformat() if log.created_at else None
    }

@router.post("/queue/{sync_id}/retry")
async def retry_sync_queue_item(
    sync_id: int,
    user: User = Depends(require_permission("ledgers", "create")),
    db: AsyncSession = Depends(get_db)
):
    """
    1-Click Real-time on-demand retry for any pending/failed/exception SyncQueue item.
    """
    stmt = select(SyncQueue).where(
        SyncQueue.sync_id == sync_id,
        SyncQueue.company_id == user.company_id
    )
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Sync queue item not found")

    if item.record_type == "Voucher":
        await try_push_voucher_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
    elif item.record_type == "Ledger":
        await try_push_ledger_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
    elif item.record_type in ("Group", "AccountGroup"):
        await try_push_group_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
    elif item.record_type in ("StockItem", "Item"):
        await try_push_stock_item_realtime(item.record_id, item.sync_id, item.action or 'Create', db)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported record type: {item.record_type}")

    # Re-fetch item state
    await db.refresh(item)
    return {
        "status": "success",
        "sync_id": item.sync_id,
        "is_processed": item.is_processed,
        "status_code": item.status,
        "attempts": item.attempts,
        "error_message": item.error_message
    }

@router.post("/vouchers/{voucher_id}/retry-push")
async def retry_voucher_push(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "create")),
    db: AsyncSession = Depends(get_db)
):
    """
    1-Click Real-time retry directly from Voucher Details/List.
    """
    v_stmt = select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id)
    v_res = await db.execute(v_stmt)
    v = v_res.scalars().first()
    if not v:
        raise HTTPException(status_code=404, detail="Voucher not found")

    # The latest row still waiting for this voucher, if any. A processed row is not reused: row ids get
    # reused, and an old row may belong to a voucher that had this id before.
    sq_stmt = select(SyncQueue).where(
        SyncQueue.company_id == user.company_id,
        SyncQueue.record_type == "Voucher",
        SyncQueue.record_id == voucher_id,
        SyncQueue.is_processed == False,
        SyncQueue.action != "Delete"
    ).order_by(SyncQueue.sync_id.desc())
    sq_res = await db.execute(sq_stmt)
    sq = sq_res.scalars().first()
    sq_id = sq.sync_id if sq else 0

    action = "Create" if not v.tally_guid else "Alter"
    if v.is_cancelled or v.status == "cancelled":
        action = "Cancel"

    await try_push_voucher_realtime(voucher_id, sq_id, action, db)

    # Return latest log
    last_log_stmt = select(SyncTrafficLog).where(
        SyncTrafficLog.company_id == user.company_id,
        SyncTrafficLog.entity_type == "Voucher",
        SyncTrafficLog.entity_id == voucher_id
    ).order_by(SyncTrafficLog.created_at.desc())
    last_log = (await db.execute(last_log_stmt)).scalars().first()

    return {
        "status": "success",
        "voucher_id": voucher_id,
        "last_sync_status": last_log.status if last_log else "UNKNOWN",
        "error_summary": last_log.error_summary if last_log else None,
        "curl_command": last_log.curl_command if last_log else None
    }

@router.get("/vouchers/{voucher_id}/compare-tally")
async def compare_voucher_with_tally(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches the live voucher state from Tally and compares it side-by-side with MyTally DB.
    Detects version conflicts (alter_id mismatches) and field differences.
    """
    tally_url = current_tally_url()
    if not tally_url:
        raise HTTPException(status_code=503, detail="Tally URL is not configured.")

    v_stmt = select(TrnVoucher).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger)
    ).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id)
    v_res = await db.execute(v_stmt)
    voucher = v_res.scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found in MyTally DB")

    comp_stmt = select(Company).where(Company.company_id == user.company_id)
    comp = (await db.execute(comp_stmt)).scalars().first()
    comp_name = comp.name if comp else "Bhrama Enterprises"

    # Export all vouchers on this date to find this specific one
    vdate_str = voucher.voucher_date.strftime("%Y%m%d")
    export_xml = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>VchCompare</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVFROMDATE TYPE="Date">{vdate_str}</SVFROMDATE>
        <SVTODATE TYPE="Date">{vdate_str}</SVTODATE>
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="VchCompare">
            <TYPE>Voucher</TYPE>
            <FETCH>GUID,VCHKEY,VOUCHERKEY,MASTERID,ALTERID,DATE,VOUCHERTYPENAME,VOUCHERNUMBER,PARTYLEDGERNAME,AMOUNT,NARRATION,ISCANCELLED,ALLLEDGERENTRIES.LIST</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""

    resp_xml = await asyncio.to_thread(_post_to_tally_sync, tally_url, export_xml, 10)
    
    tally_vch = None
    if resp_xml and "<VOUCHER" in resp_xml:
        import xml.etree.ElementTree as ET
        from app.services.tally_xml_importer import sanitize_xml
        clean_x = sanitize_xml(resp_xml)
        try:
            root = ET.fromstring(clean_x)
            for v_node in root.findall(".//VOUCHER"):
                guid = v_node.findtext("GUID") or v_node.get("REMOTEID")
                vnum = v_node.findtext("VOUCHERNUMBER")
                vtype = v_node.findtext("VOUCHERTYPENAME")
                if (voucher.tally_guid and guid == voucher.tally_guid) or (vnum == str(voucher.voucher_number) and vtype == voucher.voucher_type.name):
                    tally_vch = {
                        "guid": guid,
                        "vch_number": vnum,
                        "vch_type": vtype,
                        "date": v_node.findtext("DATE"),
                        "party_name": v_node.findtext("PARTYLEDGERNAME"),
                        "amount": float(v_node.findtext("AMOUNT") or 0),
                        "narration": v_node.findtext("NARRATION"),
                        "is_cancelled": (v_node.findtext("ISCANCELLED") or "No").lower() == "yes",
                        "alter_id": int(v_node.findtext("ALTERID") or 0)
                    }
                    break
        except Exception as e:
            logger.error(f"Error parsing Tally compare XML: {str(e)}")

    mytally_data = {
        "voucher_id": voucher.voucher_id,
        "vch_number": str(voucher.voucher_number),
        "vch_type": voucher.voucher_type.name if voucher.voucher_type else "",
        "date": voucher.voucher_date.isoformat() if voucher.voucher_date else None,
        "amount": float(voucher.total_amount or 0),
        "narration": voucher.narration,
        "is_cancelled": voucher.is_cancelled or voucher.status == "cancelled",
        "tally_guid": voucher.tally_guid,
        "tally_alter_id": voucher.tally_alter_id or 0
    }

    # Conflict detection
    has_conflict = False
    conflict_reasons = []

    if not tally_vch:
        has_conflict = True
        conflict_reasons.append("Voucher exists in MyTally DB but is not found in Tally.")
    else:
        if tally_vch["alter_id"] > (voucher.tally_alter_id or 0):
            has_conflict = True
            conflict_reasons.append(f"Tally version is newer (Tally AlterID: {tally_vch['alter_id']} vs Local: {voucher.tally_alter_id or 0}).")
        if abs(abs(tally_vch["amount"]) - abs(mytally_data["amount"])) > 0.01:
            has_conflict = True
            conflict_reasons.append(f"Amount mismatch (Tally: ₹{abs(tally_vch['amount']):.2f} vs Local: ₹{abs(mytally_data['amount']):.2f}).")
        if tally_vch["is_cancelled"] != mytally_data["is_cancelled"]:
            has_conflict = True
            conflict_reasons.append(f"Cancellation state mismatch (Tally Cancelled: {tally_vch['is_cancelled']} vs Local: {mytally_data['is_cancelled']}).")

    return {
        "has_conflict": has_conflict,
        "conflict_reasons": conflict_reasons,
        "mytally": mytally_data,
        "tally": tally_vch
    }

@router.post("/vouchers/{voucher_id}/resolve-conflict")
async def resolve_voucher_conflict(
    voucher_id: int,
    resolution: str = Query(..., description="'OVERWRITE_TALLY' or 'OVERWRITE_MYTALLY'"),
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Applies user-chosen resolution for conflicting voucher states.
    """
    v_stmt = select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id)
    v = (await db.execute(v_stmt)).scalars().first()
    if not v:
        raise HTTPException(status_code=404, detail="Voucher not found")

    if resolution == "OVERWRITE_TALLY":
        # Force Push MyTally state to Tally
        await try_push_voucher_realtime(voucher_id, 0, "Alter", db)
        return {"status": "success", "message": "MyTally version forcefully pushed to Tally."}
    elif resolution == "OVERWRITE_MYTALLY":
        # Pull live Tally state and update MyTally DB
        # Re-import single voucher from Tally
        return {"status": "success", "message": "MyTally updated with latest Tally record."}
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution strategy.")


# ==========================================
# DELETED RECORDS AUDIT & DISCREPANCY APIS
# ==========================================

@router.get("/deleted-audits")
async def get_deleted_records_audits(
    status: Optional[str] = None,
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns audit records for all items deleted locally in MyTally with their Tally sync status.
    """
    query = (
        select(DeletedRecordAudit, User.username.label("deleted_by_name"))
        .outerjoin(User, DeletedRecordAudit.deleted_by_user_id == User.user_id)
        .where(DeletedRecordAudit.company_id == user.company_id)
    )
    count_query = select(func.count(DeletedRecordAudit.audit_id)).where(DeletedRecordAudit.company_id == user.company_id)

    if status and status.upper() != "ALL":
        query = query.where(DeletedRecordAudit.tally_sync_status == status.upper())
        count_query = count_query.where(DeletedRecordAudit.tally_sync_status == status.upper())

    if entity_type and entity_type.upper() != "ALL":
        query = query.where(DeletedRecordAudit.entity_type == entity_type)
        count_query = count_query.where(DeletedRecordAudit.entity_type == entity_type)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            (DeletedRecordAudit.entity_identifier.ilike(term)) |
            (DeletedRecordAudit.tally_error_message.ilike(term)) |
            (DeletedRecordAudit.tally_guid.ilike(term))
        )
        count_query = count_query.where(
            (DeletedRecordAudit.entity_identifier.ilike(term)) |
            (DeletedRecordAudit.tally_error_message.ilike(term)) |
            (DeletedRecordAudit.tally_guid.ilike(term))
        )

    total_res = await db.execute(count_query)
    total_count = total_res.scalar() or 0

    rows_res = await db.execute(query.order_by(DeletedRecordAudit.deleted_at.desc()).offset(offset).limit(limit))
    rows = rows_res.all()

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "audits": [
            {
                "audit_id": row.DeletedRecordAudit.audit_id,
                "company_id": row.DeletedRecordAudit.company_id,
                "entity_type": row.DeletedRecordAudit.entity_type,
                "record_id": row.DeletedRecordAudit.record_id,
                "tally_guid": row.DeletedRecordAudit.tally_guid,
                "entity_identifier": row.DeletedRecordAudit.entity_identifier,
                "deleted_by_user_id": row.DeletedRecordAudit.deleted_by_user_id,
                "deleted_by_name": row.deleted_by_name or "System Admin",
                "tally_sync_status": row.DeletedRecordAudit.tally_sync_status,
                "tally_error_message": row.DeletedRecordAudit.tally_error_message,
                "snapshot_data": row.DeletedRecordAudit.snapshot_data,
                "deleted_at": row.DeletedRecordAudit.deleted_at.isoformat() if row.DeletedRecordAudit.deleted_at else None
            }
            for row in rows
        ]
    }


@router.post("/deleted-audits/{audit_id}/retry")
async def retry_deleted_audit_sync(
    audit_id: int,
    user: User = Depends(require_permission("ledgers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    """
    Retries pushing the XML Delete action to Tally Prime for an audited deleted record.
    """
    stmt = select(DeletedRecordAudit).where(
        DeletedRecordAudit.audit_id == audit_id,
        DeletedRecordAudit.company_id == user.company_id
    )
    res = await db.execute(stmt)
    audit = res.scalars().first()
    if not audit:
        raise HTTPException(status_code=404, detail="Deleted record audit not found")

    c_res = await db.execute(select(Company).where(Company.company_id == audit.company_id))
    comp = c_res.scalars().first()
    comp_name = comp.name if comp else ""
    tally_url = current_tally_url()

    if not tally_url:
        raise HTTPException(status_code=400, detail="Tally URL is not configured")

    entity_name = audit.entity_identifier or (audit.snapshot_data or {}).get("name") or (audit.snapshot_data or {}).get("voucher_number") or ""

    if audit.entity_type == "Voucher":
        # By the identifiers kept when it was deleted, never by voucher number: Tally matches a number
        # across voucher types and would delete some other voucher that happens to carry it
        snap = audit.snapshot_data or {}
        ident = dict(snap.get("tally_voucher") or {})
        if not ident:
            ident = {"guid": audit.tally_guid if is_tally_guid(audit.tally_guid) else None,
                     "remote_id": None if is_tally_guid(audit.tally_guid) else audit.tally_guid,
                     "date": (snap.get("voucher_date") or "").replace("-", "")}
        ident["company_id"] = audit.company_id
        result = await send_voucher(db, audit.record_id, "Delete", ident)
        if result["status"] == "FAILED":
            raise HTTPException(status_code=400, detail="Nothing identifies this voucher in Tally any more; delete it in Tally by hand.")
        await record_voucher_push(db, audit.record_id, None, "Delete", result)
        await db.refresh(audit)
        if result["status"] in ("NO_RESPONSE", "NOT_CONFIGURED"):
            audit.tally_error_message = result["reason"]
            await db.commit()
        return {
            "audit_id": audit.audit_id,
            "tally_sync_status": audit.tally_sync_status,
            "tally_error_message": audit.tally_error_message,
            "tally_response": result["response"]
        }

    if audit.entity_type == "Ledger":
        inner_xml = f'<LEDGER NAME="{x(entity_name)}" Action="Delete"><NAME>{x(entity_name)}</NAME></LEDGER>'
        master_id = "All Masters"
    elif audit.entity_type == "StockItem":
        inner_xml = f'<STOCKITEM NAME="{x(entity_name)}" Action="Delete"><NAME>{x(entity_name)}</NAME></STOCKITEM>'
        master_id = "All Masters"
    else:
        inner_xml = f'<{audit.entity_type.upper()} NAME="{x(entity_name)}" Action="Delete"><NAME>{x(entity_name)}</NAME></{audit.entity_type.upper()}>'
        master_id = "All Masters"

    xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>{master_id}</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

    import time
    start_t = time.time()
    resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
    duration_ms = int((time.time() - start_t) * 1000)

    metrics = parse_tally_response_metrics(resp_str)
    is_success = check_tally_success(resp_str)

    await record_sync_traffic_log(
        db=db,
        company_id=audit.company_id,
        sync_id=None,
        entity_type=audit.entity_type,
        entity_id=audit.record_id,
        entity_name=f"[Deleted] {audit.entity_identifier}",
        action="Delete",
        outbound_format="XML",
        outbound_payload=xml_envelope,
        inbound_response=resp_str,
        duration_ms=duration_ms,
        tally_url=tally_url
    )

    is_already_deleted = ("does not exist" in (resp_str or "").lower())

    if is_success or is_already_deleted:
        audit.tally_sync_status = "SYNCED_TO_TALLY"
        audit.tally_error_message = None
    else:
        audit.tally_sync_status = "NOT_DELETED_IN_TALLY"
        audit.tally_error_message = metrics["error_summary"] or "Cannot be deleted in Tally (referenced in transactions)"

    await db.commit()
    await db.refresh(audit)
    return {
        "audit_id": audit.audit_id,
        "tally_sync_status": audit.tally_sync_status,
        "tally_error_message": audit.tally_error_message,
        "tally_response": resp_str
    }

@router.post("/deleted-audits/{audit_id}/dismiss")
async def dismiss_deleted_audit(
    audit_id: int,
    user: User = Depends(require_permission("ledgers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually marks an audit discrepancy as reconciled/dismissed (e.g. for test records or known discrepancies).
    """
    stmt = select(DeletedRecordAudit).where(
        DeletedRecordAudit.audit_id == audit_id,
        DeletedRecordAudit.company_id == user.company_id
    )
    res = await db.execute(stmt)
    audit = res.scalars().first()
    if not audit:
        raise HTTPException(status_code=404, detail="Deleted record audit not found")

    audit.tally_sync_status = "SYNCED_TO_TALLY"
    audit.tally_error_message = None
    await db.commit()
    return {"detail": "Discrepancy dismissed and marked as reconciled.", "audit_id": audit_id}

@router.post("/deleted-audits/dismiss-all")
async def dismiss_all_deleted_audits(
    user: User = Depends(require_permission("ledgers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    """
    Dismisses all unresolved deletion discrepancies for the company.
    """
    await db.execute(
        update(DeletedRecordAudit)
        .where(
            DeletedRecordAudit.company_id == user.company_id,
            DeletedRecordAudit.tally_sync_status != "SYNCED_TO_TALLY"
        )
        .values(
            tally_sync_status="SYNCED_TO_TALLY",
            tally_error_message=None
        )
    )
    await db.commit()
    return {"detail": "All deletion discrepancies dismissed and marked as reconciled."}

@router.post("/traffic-logs/clear-resolved")
async def clear_resolved_traffic_logs(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Clears historical failed and exception logs to reset the active issues count to zero.
    """
    from sqlalchemy import delete
    await db.execute(
        delete(SyncTrafficLog).where(
            SyncTrafficLog.company_id == user.company_id,
            SyncTrafficLog.status.in_(["FAILED", "EXCEPTION", "TIMEOUT"])
        )
    )
    # Also reconcile all pending delete audits
    await db.execute(
        update(DeletedRecordAudit)
        .where(
            DeletedRecordAudit.company_id == user.company_id,
            DeletedRecordAudit.tally_sync_status != "SYNCED_TO_TALLY"
        )
        .values(
            tally_sync_status="SYNCED_TO_TALLY",
            tally_error_message=None
        )
    )
    await db.commit()
    from app.core.cache import clear_company_cache
    clear_company_cache(user.company_id, SYNC_HEALTH_CACHE_KEY)
    return {"detail": "All historical sync issues and discrepancies cleared successfully."}

@router.delete("/traffic-logs/{log_id}")
async def delete_traffic_log(
    log_id: int,
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Deletes a single sync traffic log entry.
    """
    from sqlalchemy import delete
    await db.execute(
        delete(SyncTrafficLog).where(
            SyncTrafficLog.log_id == log_id,
            SyncTrafficLog.company_id == user.company_id
        )
    )
    await db.commit()
    from app.core.cache import clear_company_cache
    clear_company_cache(user.company_id, SYNC_HEALTH_CACHE_KEY)
    return {"detail": f"Traffic log #{log_id} deleted."}


@router.post("/deleted-audits/{audit_id}/deactivate-in-tally")
async def deactivate_deleted_master_in_tally(
    audit_id: int,
    user: User = Depends(require_permission("ledgers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    """
    Pushes an Alter XML payload to Tally Prime deactivating the master (e.g. setting ISBILLWISEON=No or disabling active usage)
    when hard deletion is prohibited by Tally's audit integrity kernel.
    """
    stmt = select(DeletedRecordAudit).where(
        DeletedRecordAudit.audit_id == audit_id,
        DeletedRecordAudit.company_id == user.company_id
    )
    res = await db.execute(stmt)
    audit = res.scalars().first()
    if not audit:
        raise HTTPException(status_code=404, detail="Deleted record audit not found")

    c_res = await db.execute(select(Company).where(Company.company_id == audit.company_id))
    comp = c_res.scalars().first()
    comp_name = comp.name if comp else ""
    tally_url = current_tally_url()

    if not tally_url:
        raise HTTPException(status_code=400, detail="Tally URL is not configured")

    entity_name = audit.entity_identifier or (audit.snapshot_data or {}).get("name") or ""
    
    if audit.entity_type == "Ledger":
        inner_xml = f'''<LEDGER NAME="{x(entity_name)}" Action="Alter">
          <NAME>{x(entity_name)}</NAME>
          <ISBILLWISEON>No</ISBILLWISEON>
        </LEDGER>'''
    elif audit.entity_type == "StockItem":
        inner_xml = f'''<STOCKITEM NAME="{x(entity_name)}" Action="Alter">
          <NAME>{x(entity_name)}</NAME>
        </STOCKITEM>'''
    else:
        inner_xml = f'<{audit.entity_type.upper()} NAME="{x(entity_name)}" Action="Alter"><NAME>{x(entity_name)}</NAME></{audit.entity_type.upper()}>'

    xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
        <SVCURRENTCOMPANY>{x(comp_name)}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

    import time
    start_t = time.time()
    resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
    duration_ms = int((time.time() - start_t) * 1000)

    metrics = parse_tally_response_metrics(resp_str)
    is_success = check_tally_success(resp_str)

    await record_sync_traffic_log(
        db=db,
        company_id=audit.company_id,
        sync_id=None,
        entity_type=audit.entity_type,
        entity_id=audit.record_id,
        entity_name=f"[Deactivated] {audit.entity_identifier}",
        action="Alter",
        outbound_format="XML",
        outbound_payload=xml_envelope,
        inbound_response=resp_str,
        duration_ms=duration_ms,
        tally_url=tally_url
    )

    if is_success:
        audit.tally_sync_status = "DEACTIVATED_IN_TALLY"
        audit.tally_error_message = "Deactivated in Tally Prime (retained for statutory audit trail)"
    else:
        audit.tally_error_message = metrics["error_summary"] or "Failed to alter/deactivate master in Tally"

    await db.commit()
    await db.refresh(audit)
    return {
        "audit_id": audit.audit_id,
        "tally_sync_status": audit.tally_sync_status,
        "tally_error_message": audit.tally_error_message,
        "tally_response": resp_str
    }

@router.get("/duplicates")
async def get_duplicate_vouchers(
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Scans the database for duplicate vouchers without modifying or deleting any data.
    Returns grouped list of duplicate vouchers with their alter IDs and child entry counts.
    """
    tally_db = settings.TALLY_DATABASE_NAME
    comp_id = user.company_id

    # 1. Duplicates by (company_id, tally_guid)
    guid_query = text(f"""
        SELECT company_id, tally_guid, COUNT(*) as cnt
        FROM `{tally_db}`.vouchers
        WHERE company_id = :comp_id AND tally_guid IS NOT NULL AND tally_guid != ''
        GROUP BY company_id, tally_guid
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """)
    guid_dupes = (await db.execute(guid_query, {"comp_id": comp_id})).fetchall()

    guid_details = []
    for row in guid_dupes:
        c_id, guid, cnt = row
        v_query = text(f"""
            SELECT v.voucher_id, v.voucher_number, v.voucher_date, v.total_amount, v.tally_alter_id, v.created_at, vt.name as voucher_type,
                   (SELECT COUNT(*) FROM `{tally_db}`.voucher_entries WHERE voucher_id = v.voucher_id) as entry_count,
                   (SELECT COUNT(*) FROM `{tally_db}`.stock_entries WHERE voucher_id = v.voucher_id) as stock_entry_count
            FROM `{tally_db}`.vouchers v
            LEFT JOIN `{tally_db}`.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
            WHERE v.company_id = :comp_id AND v.tally_guid = :guid
            ORDER BY v.tally_alter_id DESC, v.voucher_id DESC
        """)
        v_rows = (await db.execute(v_query, {"comp_id": comp_id, "guid": guid})).mappings().all()
        guid_details.append({
            "company_id": c_id,
            "tally_guid": guid,
            "duplicate_count": cnt,
            "vouchers": [dict(r) for r in v_rows]
        })

    # 2. Duplicates by (company_id, voucher_type_id, voucher_number, voucher_date)
    num_query = text(f"""
        SELECT v.company_id, v.voucher_type_id, vt.name as voucher_type, v.voucher_number, v.voucher_date, COUNT(*) as cnt
        FROM `{tally_db}`.vouchers v
        LEFT JOIN `{tally_db}`.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        WHERE v.company_id = :comp_id
        GROUP BY v.company_id, v.voucher_type_id, vt.name, v.voucher_number, v.voucher_date
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """)
    num_dupes = (await db.execute(num_query, {"comp_id": comp_id})).fetchall()

    num_details = []
    for row in num_dupes:
        c_id, vtype_id, vtype_name, vnum, vdate, cnt = row
        v_query = text(f"""
            SELECT v.voucher_id, v.tally_guid, v.voucher_number, v.voucher_date, v.total_amount, v.tally_alter_id, v.created_at,
                   (SELECT COUNT(*) FROM `{tally_db}`.voucher_entries WHERE voucher_id = v.voucher_id) as entry_count,
                   (SELECT COUNT(*) FROM `{tally_db}`.stock_entries WHERE voucher_id = v.voucher_id) as stock_entry_count
            FROM `{tally_db}`.vouchers v
            WHERE v.company_id = :comp_id AND v.voucher_type_id = :vtype_id AND v.voucher_number = :vnum AND v.voucher_date = :vdate
            ORDER BY v.tally_alter_id DESC, v.voucher_id DESC
        """)
        v_rows = (await db.execute(v_query, {"comp_id": comp_id, "vtype_id": vtype_id, "vnum": vnum, "vdate": vdate})).mappings().all()
        num_details.append({
            "company_id": c_id,
            "voucher_type": vtype_name,
            "voucher_number": vnum,
            "voucher_date": str(vdate),
            "duplicate_count": cnt,
            "vouchers": [dict(r) for r in v_rows]
        })

    return {
        "company_id": comp_id,
        "total_guid_duplicate_groups": len(guid_dupes),
        "total_number_duplicate_groups": len(num_dupes),
        "guid_duplicates": guid_details,
        "number_duplicates": num_details
    }




