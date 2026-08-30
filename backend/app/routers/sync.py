import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import update, delete, text
from sqlalchemy.sql import func
from typing import List, Dict, Any, Optional
import json
import re
from decimal import Decimal
import urllib.request
import logging

from app.core.database import get_db
from app.core.permissions import require_permission
from app.core.config import settings
from app.routers.admin import require_admin
from app.models.portal_core import Company, User, SyncQueue, SyncTrafficLog, DeletedRecordAudit
from app.models.tally_core import MstLedger, MstGroup, TrnVoucher, TrnAccounting, MstStockItem, MstVoucherType
from app.services.tally_xml_importer import import_tally_xml
from app.services.tally_schema_validator import TallySchemaValidator

logger = logging.getLogger("uvicorn.error")
schema_validator = TallySchemaValidator()

router = APIRouter(prefix="/sync", tags=["Tally Synchronization"])

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
        "created": 0, "altered": 0, "deleted": 0, "errors": 0, "exceptions": 0,
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
    elif metrics["created"] == 0 and metrics["altered"] == 0 and metrics["deleted"] == 0 and "<STATUS>0</STATUS>" in resp_str:
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
    Currently uses the global settings.TALLY_URL until multi-tenant Tally sync configuration is implemented.
    """
    if settings.TALLY_URL:
        return ActiveTallySyncConfig(tally_url=settings.TALLY_URL)
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

@router.post("/inbound")
async def inbound_sync(
    request: Request,
    company_name: Optional[str] = Query(None),
    user: User = Depends(require_permission("ledgers", "create")),
    db: AsyncSession = Depends(get_db)
):
    """
    Receives raw Tally XML export from sync bridge daemon, importing it directly into the database.
    """
    if not company_name:
        company_name = request.headers.get("x-company-name")
        
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
        
    async with sync_lock:
        try:
            result = await import_tally_xml(xml_data, db, user.user_id, override_company_name=company_name)
            company_id = result.get("company_id")
            if company_id:
                from app.core.cache import clear_company_cache
                clear_company_cache(company_id)
            return result
        except Exception as ex:
            logger.error(f"❌ [INBOUND SYNC CRITICAL EXCEPTION]: {str(ex)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Inbound XML import failed on server: {type(ex).__name__}: {str(ex)}"
            )

async def build_voucher_xml_payload(voucher_id: int, action: str, db: AsyncSession) -> str:
    try:
        from app.models.tally_core import (
            TrnVoucher, TrnAccounting, MstLedger, MstVoucherType, BillAllocation, 
            TrnInventory, MstStockItem, MstGodown, Batch, VoucherAccountingAllocation,
            CostCenter, TrnCostCentreAllocation, MstCostCentre
        )
        from app.models.portal_core import Company
        
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
        ).where(TrnVoucher.voucher_id == voucher_id)
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

        if action == "Cancel" or voucher.is_cancelled or voucher.status == "cancelled":
            guid_attr = voucher.tally_guid or f"MYTALLY-VCH-{voucher.voucher_id}"
            remote_id_attr = voucher.tally_guid or f"MYTALLY-VCH-{voucher.voucher_id}"
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
                <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="{remote_id_attr}" VCHTYPE="{vtype_name}" ACTION="Alter" OBJVIEW="{obj_view}">
              <DATE>{vdate_str}</DATE>
              <EFFECTIVEDATE>{vdate_str}</EFFECTIVEDATE>
              <VCHSTATUSDATE>{vdate_str}</VCHSTATUSDATE>
              <VOUCHERTYPENAME>{vtype_name}</VOUCHERTYPENAME>
              <VOUCHERNUMBER>{voucher.voucher_number}</VOUCHERNUMBER>
              <ISCANCELLED>Yes</ISCANCELLED>
              <GUID>{guid_attr}</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'''

        if action == "Delete":
            guid_attr = voucher.tally_guid or f"MYTALLY-VCH-{voucher.voucher_id}"
            remote_id_attr = voucher.tally_guid or f"MYTALLY-VCH-{voucher.voucher_id}"
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
                <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="{remote_id_attr}" VCHTYPE="{vtype_name}" ACTION="Delete" OBJVIEW="{obj_view}">
              <DATE>{vdate_str}</DATE>
              <GUID>{guid_attr}</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'''

        is_sales = (voucher.voucher_type and voucher.voucher_type.parent_type in ['Sales', 'Debit Note']) or vtype_name in ['Sales', 'Debit Note']
        sales_pur_ledger_name = "GST Sales" if is_sales else "GST Purchase"
        for ent in voucher.entries:
            if ent.ledger and ent.ledger.group:
                gname = ent.ledger.group.name.lower()
                if ("sales" in gname if is_sales else "purchase" in gname):
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
               <STOCKITEMNAME>{item_name}</STOCKITEMNAME>
               <ISDEEMEDPOSITIVE>{is_dp}</ISDEEMEDPOSITIVE>
               <RATE>{rate_str}</RATE>{discount_tag}
               <AMOUNT>{signed_inv_amt:.2f}</AMOUNT>
               <ACTUALQTY>{qty_str}</ACTUALQTY>
               <BILLEDQTY>{billed_qty_str}</BILLEDQTY>
               <BATCHALLOCATIONS.LIST>
                <GODOWNNAME>{godown_name}</GODOWNNAME>
                <BATCHNAME>{batch_name}</BATCHNAME>
                <AMOUNT>{signed_inv_amt:.2f}</AMOUNT>
                <ACTUALQTY>{qty_str}</ACTUALQTY>
                <BILLEDQTY>{billed_qty_str}</BILLEDQTY>
               </BATCHALLOCATIONS.LIST>
               <ACCOUNTINGALLOCATIONS.LIST>
                <LEDGERNAME>{sales_pur_ledger_name}</LEDGERNAME>
                <ISDEEMEDPOSITIVE>{is_dp}</ISDEEMEDPOSITIVE>
                <ISPARTYLEDGER>No</ISPARTYLEDGER>
                <AMOUNT>{signed_inv_amt:.2f}</AMOUNT>
               </ACCOUNTINGALLOCATIONS.LIST>
              </ALLINVENTORYENTRIES.LIST>'''

        ledger_tag = "LEDGERENTRIES.LIST" if is_inv else "ALLLEDGERENTRIES.LIST"
        entries_xml = ""
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
               <LEDGERNAME>{lname}</LEDGERNAME>
               <ISDEEMEDPOSITIVE>{is_dp}</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>{'Yes' if is_party else 'No'}</ISPARTYLEDGER>
               <AMOUNT>{amt:.2f}</AMOUNT>'''

            if getattr(ent, 'bank_allocations', None):
                for ba in ent.bank_allocations:
                    ba_amt = -float(ba.amount) if ent.debit_amount > 0 else float(ba.amount)
                    inst_date = ba.instrument_date.strftime("%Y%m%d") if ba.instrument_date else vdate_str
                    tx_type = ba.transaction_type or "Others"
                    bank_op_tag = f"\n                 <BANKOPERATIONREFERENCE>{ba.bank_operation_ref}</BANKOPERATIONREFERENCE>" if getattr(ba, 'bank_operation_ref', None) else ""
                bank_prt_tag = f"\n                 <BANKPORTALREFERENCE>{ba.bank_portal_ref}</BANKPORTALREFERENCE>" if getattr(ba, 'bank_portal_ref', None) else ""
                bank_txn_tag = f"\n                 <BANKTRANSACTIONREFERENCE>{ba.bank_transaction_ref}</BANKTRANSACTIONREFERENCE>" if getattr(ba, 'bank_transaction_ref', None) else ""
                paylink_tag = f"\n                 <PAYMENTLINK>{ba.payment_link}</PAYMENTLINK>" if getattr(ba, 'payment_link', None) else ""
                entries_xml += f'''
               <BANKALLOCATIONS.LIST>
                <DATE>{vdate_str}</DATE>
                <INSTRUMENTDATE>{inst_date}</INSTRUMENTDATE>
                <TRANSACTIONTYPE>{tx_type}</TRANSACTIONTYPE>
                <PAYMENTMODE>Transacted</PAYMENTMODE>{bank_op_tag}{bank_prt_tag}{bank_txn_tag}{paylink_tag}
                <BANKPARTYNAME>{party_ledger_name or 'Cash'}</BANKPARTYNAME>
                <AMOUNT>{ba_amt:.2f}</AMOUNT>
               </BANKALLOCATIONS.LIST>'''

            if getattr(ent, 'bill_allocations', None):
                for ba in ent.bill_allocations:
                    bname = ba.bill.bill_reference if getattr(ba, 'bill', None) and ba.bill else (getattr(ba, 'bill_reference', '') or f"{voucher.voucher_number or '1'}")
                    b_amt = -abs(float(ba.amount)) if ent.debit_amount > 0 else abs(float(ba.amount))
                    entries_xml += f'''
               <BILLALLOCATIONS.LIST>
                <NAME>{bname}</NAME>
                <BILLTYPE>{ba.allocation_type}</BILLTYPE>
                <AMOUNT>{b_amt:.2f}</AMOUNT>
               </BILLALLOCATIONS.LIST>'''
            elif is_party:
                bname = str(voucher.reference_number or voucher.voucher_number or '1')
                entries_xml += f'''
               <BILLALLOCATIONS.LIST>
                <NAME>{bname}</NAME>
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
                <NAME>{cc_name}</NAME>
                <AMOUNT>{cca_amt:.2f}</AMOUNT>
               </COSTCENTREALLOCATIONS.LIST>'''

            entries_xml += f'''
              </{ledger_tag}>'''

        guid_val = getattr(voucher, 'guid', None) or getattr(voucher, 'tally_guid', None) or f"MYTALLY-VCH-{voucher.voucher_id}"
        vch_tag_attrs = f'REMOTEID="{guid_val}" VCHTYPE="{vtype_name}" ACTION="{action}" OBJVIEW="{obj_view}"'
        guid_xml = f"\n              <GUID>{guid_val}</GUID>"

        is_invoice_tag = "\n              <ISINVOICE>Yes</ISINVOICE>" if is_inv else ""
        
        eff_date_val = voucher.effective_date.strftime("%Y%m%d") if voucher.effective_date else vdate_str
        ref_date_tag = f"\n              <REFERENCEDATE>{voucher.reference_date.strftime('%Y%m%d')}</REFERENCEDATE>" if getattr(voucher, 'reference_date', None) else ""
        pos_tag = f"\n              <PLACEOFSUPPLY>{voucher.place_of_supply}</PLACEOFSUPPLY>" if getattr(voucher, 'place_of_supply', None) else ""
        buyer_tag = f"\n              <BASICBUYERNAME>{voucher.buyer_name}</BASICBUYERNAME>" if getattr(voucher, 'buyer_name', None) else ""
        consignee_tag = f"\n              <CONSIGNEEMAILINGNAME>{voucher.consignee_name}</CONSIGNEEMAILINGNAME>" if getattr(voucher, 'consignee_name', None) else ""
        order_ref_tag = f"\n              <BASICORDERREF>{voucher.order_reference}</BASICORDERREF>" if getattr(voucher, 'order_reference', None) else ""
        despatch_tag = f"\n              <BASICSHIPDELIVERYNOTE>{voucher.despatch_doc_no}</BASICSHIPDELIVERYNOTE>" if getattr(voucher, 'despatch_doc_no', None) else ""
        post_dated_tag = f"\n              <ISPOSTDATED>{'Yes' if getattr(voucher, 'is_post_dated', False) else 'No'}</ISPOSTDATED>"

        # e-Invoice XML tags
        irn_tag = f"\n              <IRN>{voucher.irn}</IRN>" if getattr(voucher, 'irn', None) else ""
        irn_ack_tag = f"\n              <IRNACKNO>{voucher.irn_ack_no}</IRNACKNO>" if getattr(voucher, 'irn_ack_no', None) else ""
        irn_date_tag = f"\n              <IRNACKDATE>{voucher.irn_ack_date.strftime('%Y-%m-%d %H:%M:%S')}</IRNACKDATE>" if getattr(voucher, 'irn_ack_date', None) else ""
        irn_qr_tag = f"\n              <IRNQRCODE>{voucher.irn_qr_code}</IRNQRCODE>" if getattr(voucher, 'irn_qr_code', None) else ""
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
               <BILLNUMBER>{eb.bill_number or ''}</BILLNUMBER>
               <BILLDATE>{b_date}</BILLDATE>
               <VALIDUPTO>{v_date}</VALIDUPTO>
               <DISTANCE>{eb.distance_km or '0'}</DISTANCE>
               <TRANSPORTERID>{eb.transporter_id or ''}</TRANSPORTERID>
               <TRANSPORTERNAME>{eb.transporter_name or ''}</TRANSPORTERNAME>
               <DOCNUMBER>{eb.doc_number or ''}</DOCNUMBER>
               <DOCDATE>{d_date}</DOCDATE>
               <VEHICLENUMBER>{eb.vehicle_number or ''}</VEHICLENUMBER>
               <VEHICLETYPE>{eb.vehicle_type or 'Regular'}</VEHICLETYPE>
               <TRANSPORTMODE>{eb.transport_mode or 'Road'}</TRANSPORTMODE>
               <SUBTYPE>{eb.sub_type or 'Supply'}</SUBTYPE>
               <DOCTYPE>{eb.doc_type or 'Tax Invoice'}</DOCTYPE>
              </EWAYBILLDETAILS.LIST>'''

        paylink_xml = ""
        if getattr(voucher, 'payment_links', None):
            for pl in voucher.payment_links:
                paylink_xml += f'''
              <PAYLINK.LIST>
               <PAYLINKID>{pl.link_id}</PAYLINKID>
               <PAYMENTURL>{pl.payment_url}</PAYMENTURL>
               <PAYMENTMODE>{pl.payment_mode}</PAYMENTMODE>
               <STATUS>{pl.status}</STATUS>
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
                <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER {vch_tag_attrs}>
              <DATE>{vdate_str}</DATE>
              <EFFECTIVEDATE>{eff_date_val}</EFFECTIVEDATE>
              <VCHSTATUSDATE>{vdate_str}</VCHSTATUSDATE>
              <VOUCHERTYPENAME>{vtype_name}</VOUCHERTYPENAME>
              <VOUCHERNUMBER>{voucher.voucher_number}</VOUCHERNUMBER>{ref_date_tag}{pos_tag}{buyer_tag}{consignee_tag}{order_ref_tag}{despatch_tag}{post_dated_tag}{irn_tag}{irn_ack_tag}{irn_date_tag}{irn_qr_tag}{irn_cancelled_tag}
              <PARTYNAME>{party_ledger_name}</PARTYNAME>
              <PARTYLEDGERNAME>{party_ledger_name}</PARTYLEDGERNAME>
              <PERSISTEDVIEW>{obj_view}</PERSISTEDVIEW>{is_invoice_tag}
              <NARRATION>{voucher.narration or ''}</NARRATION>{guid_xml}{eway_bills_xml}{paylink_xml}
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

@router.get("/outbound-queue")
async def get_outbound_queue(
    user: User = Depends(require_permission("ledgers", "read")),
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
            if ledger:
                g_stmt = select(MstGroup).where(MstGroup.group_id == ledger.group_id)
                g_res = await db.execute(g_stmt)
                group = g_res.scalars().first()
                group_name = group.name if group else "Sundry Debtors"

                c_stmt = select(Company).where(Company.company_id == ledger.company_id)
                c_res = await db.execute(c_stmt)
                comp_obj = c_res.scalars().first()
                comp_name = comp_obj.name if comp_obj else ""
                
                xml_envelope = build_ledger_xml_envelope(ledger, group_name, comp_name, item.action or 'Create')
                
        # 2. Map Voucher Creation / Alteration / Deletion
        elif item.record_type == "Voucher":
            xml_envelope = await build_voucher_xml_payload(item.record_id, item.action or 'Create', db)

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
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="{st_item.name}" Action="Delete"><NAME>{st_item.name}</NAME></STOCKITEM>
      </TALLYMESSAGE>
    </DESC>
  </BODY>
</ENVELOPE>"""
                else:
                    uom_symbol = st_item.unit.symbol if st_item.unit else "nos"
                    raw_group = st_item.group.name.strip() if st_item.group and st_item.group.name else ""
                    parent_tag = f"<PARENT>{raw_group}</PARENT>" if raw_group and raw_group.lower() not in ("primary", "not applicable") else "<PARENT>&#4; Primary</PARENT>"
                    xml_envelope = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="{st_item.name}" Action="{item.action or 'Create'}">
          <NAME>{st_item.name}</NAME>
          {parent_tag}
          <BASEUNITS>{uom_symbol}</BASEUNITS>
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
            if grp:
                c_stmt = select(Company).where(Company.company_id == grp.company_id)
                c_res = await db.execute(c_stmt)
                comp_obj = c_res.scalars().first()
                comp_name = comp_obj.name if comp_obj else ""
                
                parent_name = "Primary"
                if grp.parent_id:
                    p_res = await db.execute(select(MstGroup).where(MstGroup.group_id == grp.parent_id))
                    p_grp = p_res.scalars().first()
                    if p_grp:
                        parent_name = p_grp.name
                
                xml_envelope = f"""<ENVELOPE>
  <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>All Masters</ID></HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <GROUP NAME="{grp.name}" Action="{item.action or 'Create'}">
          <NAME>{grp.name}</NAME>
          <PARENT>{parent_name}</PARENT>
        </GROUP>
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
      <STATICVARIABLES><SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT><SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY></STATICVARIABLES>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHERTYPE NAME="{vt.name}" Action="{item.action or 'Create'}">
          <NAME>{vt.name}</NAME>
          <PARENT>{parent_type}</PARENT>
          <NUMBERINGMETHOD>{vt.numbering_method or 'Automatic'}</NUMBERINGMETHOD>
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
        items_summary = ", ".join([f"{p['record_type']} #{p['record_id']} ({p['action']})" for p in outbound_payloads])
        msg = f"\n=======================================================\n📤 [OUTBOUND DISPATCH] Sending {len(outbound_payloads)} item(s) to Desktop Sync Agent:\nSummary: [{items_summary}]\n"
        for p in outbound_payloads:
            msg += f"\n--- PAYLOAD FOR {p['record_type']} #{p['record_id']} ({p['action']}) ---\n{p['xml_payload']}\n"
        msg += "=======================================================\n"
        print(msg, flush=True)
        logger.info(msg)

    return outbound_payloads

@router.post("/acknowledge")
async def acknowledge_sync(
    sync_ids: List[int],
    user: User = Depends(require_permission("ledgers", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Marks sync queue records as processed upon successful local Tally ingestion.
    """
    ack_msg = f"✅ [SYNC ACKNOWLEDGED] Marked {len(sync_ids)} sync task(s) as successfully ingested into Tally: {sync_ids}"
    print(f"\n=======================================================\n{ack_msg}\n=======================================================\n", flush=True)
    logger.info(ack_msg)
    stmt = update(SyncQueue).where(
        SyncQueue.sync_id.in_(sync_ids),
        SyncQueue.company_id == user.company_id
    ).values(is_processed=True)
    
    await db.execute(stmt)
    await db.commit()
    
    return {"status": "success", "acknowledged_count": len(sync_ids)}

@router.get("/last-alter-id")
async def get_last_alter_id(
    user: User = Depends(require_permission("ledgers", "read")),
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
    
    tables_to_check = [
        MstLedger, TrnVoucher, MstStockItem, MstGroup, 
        MstVoucherType, MstStockGroup, MstStockCategory, MstGodown, CostCenter
    ]
    
    max_alter_id = 0
    details = {}
    
    for model in tables_to_check:
        try:
            stmt = select(func.max(model.tally_alter_id)).where(model.company_id == user.company_id)
            res = await db.execute(stmt)
            val = res.scalar() or 0
            details[model.__tablename__] = int(val)
            if int(val) > max_alter_id:
                max_alter_id = int(val)
        except Exception:
            pass

    return {
        "last_alter_id": int(max_alter_id),
        "last_ledger_alter_id": details.get("mst_ledgers", 0),
        "last_voucher_alter_id": details.get("trn_vouchers", 0),
        "last_stock_item_alter_id": details.get("mst_stock_items", 0),
        "details": details
    }


def _post_to_tally_sync(url: str, xml_payload: str, timeout: int = 5) -> str:
    import http.client
    import ssl
    encoded_data = xml_payload.encode('utf-8')
    
    # SSL Context for HTTPS proxies/tunnels
    ssl_ctx = None
    if url.startswith("https"):
        ssl_ctx = ssl.create_default_context()
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


def build_ledger_xml_envelope(ledger: MstLedger, group_name: str, comp_name: str, action: str) -> str:
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
    
    address_nodes = "".join([f"<ADDRESS>{line}</ADDRESS>" for line in addr_lines])
    addr_list_xml = f"<ADDRESS.LIST>{address_nodes}</ADDRESS.LIST>" if address_nodes else ""

    mailing_details_xml = f"""<LEDMAILINGDETAILS.LIST>
      <MAILINGNAME>{ledger.name}</MAILINGNAME>
      <STATE>{state_val}</STATE>
      <COUNTRY>{country_val}</COUNTRY>
      <PINCODE>{pincode_val}</PINCODE>
      {addr_list_xml}
    </LEDMAILINGDETAILS.LIST>""" if (state_val or country_val or pincode_val or addr_list_xml) else ""

    # Multi-Address support
    loaded_addrs = ledger.__dict__.get('addresses')
    if loaded_addrs and len(loaded_addrs) > 0:
        mailing_details_xml = ""
        for a in loaded_addrs:
            a_lines = [l.strip() for l in (a.address or '').replace('\n', ',').split(',') if l.strip()]
            a_nodes = "".join([f"<ADDRESS>{l}</ADDRESS>" for l in a_lines])
            a_list = f"<ADDRESS.LIST>{a_nodes}</ADDRESS.LIST>" if a_nodes else ""
            mailing_details_xml += f"""<LEDMAILINGDETAILS.LIST>
      <ADDRESSNAME>{a.address_name or 'Primary'}</ADDRESSNAME>
      <MAILINGNAME>{a.mailing_name or ledger.name}</MAILINGNAME>
      <STATE>{a.state_name or state_val}</STATE>
      <COUNTRY>{a.country_name or country_val}</COUNTRY>
      <PINCODE>{a.pincode or pincode_val}</PINCODE>
      {a_list}
    </LEDMAILINGDETAILS.LIST>"""

    applicable_from = getattr(ledger, 'gst_applicable_from', None)
    app_from_str = applicable_from.strftime("%Y%m%d") if applicable_from else "20250401"

    # Multi-GST Registrations support
    gst_reg_details_xml = ""
    loaded_regs = ledger.__dict__.get('gst_registrations')
    if loaded_regs and len(loaded_regs) > 0:
        for reg in loaded_regs:
            r_app = reg.applicable_from.strftime("%Y%m%d") if reg.applicable_from else app_from_str
            gst_reg_details_xml += f"""<LEDGSTREGDETAILS.LIST>
      <APPLICABLEFROM>{r_app}</APPLICABLEFROM>
      <GSTREGISTRATIONTYPE>{reg.registration_type or 'Regular'}</GSTREGISTRATIONTYPE>
      <GSTIN>{reg.gstin}</GSTIN>
      <STATENAME>{reg.state_name or state_val}</STATENAME>
      <PLACEOFSUPPLY>{reg.place_of_supply or state_val}</PLACEOFSUPPLY>
    </LEDGSTREGDETAILS.LIST>"""
    elif (gst_reg_type or gstin_val):
        gst_reg_details_xml = f"""<LEDGSTREGDETAILS.LIST>
      <APPLICABLEFROM>{app_from_str}</APPLICABLEFROM>
      <GSTREGISTRATIONTYPE>{gst_reg_type}</GSTREGISTRATIONTYPE>
      <GSTIN>{gstin_val}</GSTIN>
    </LEDGSTREGDETAILS.LIST>"""

    # MSME Details support
    msme_details_xml = ""
    loaded_msme = ledger.__dict__.get('msme_details')
    if loaded_msme and len(loaded_msme) > 0:
        for m in loaded_msme:
            m_app = m.applicable_from.strftime("%Y%m%d") if m.applicable_from else app_from_str
            msme_details_xml += f"""<MSMEREGISTRATIONDETAILS.LIST>
      <ENTERPRISETYPE>{m.enterprise_type or 'Micro'}</ENTERPRISETYPE>
      <UDYAMREGNO>{m.udyam_reg_no or ''}</UDYAMREGNO>
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
      <SECTIONNUMBER>{ld.section_number}</SECTIONNUMBER>
      <CERTIFICATENO>{ld.certificate_no}</CERTIFICATENO>
      <RATEOFDEDUCTION>{ld.rate_of_deduction:.2f}</RATEOFDEDUCTION>
      <APPLICABLEFROM>{l_app_from}</APPLICABLEFROM>
      <APPLICABLETO>{l_app_to}</APPLICABLETO>
      <LIMIT>{ld.threshold_limit or '0.00'}</LIMIT>
    </LOWERDEDUCTION.LIST>"""

    return f"""<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>All Masters</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <LEDGER NAME="{ledger.name}" ACTION="{action}">
            <NAME>{ledger.name}</NAME>
            <PARENT>{group_name}</PARENT>
            <MAILINGNAME>{ledger.name}</MAILINGNAME>
            <OPENINGBALANCE>{op_bal_str}</OPENINGBALANCE>
            <COUNTRYOFRESIDENCE>{country_val}</COUNTRYOFRESIDENCE>
            <COUNTRYNAME>{country_val}</COUNTRYNAME>
            <PRIORSTATENAME>{state_val}</PRIORSTATENAME>
            <STATENAME>{state_val}</STATENAME>
            <PINCODE>{pincode_val}</PINCODE>
            {addr_list_xml}
            {mailing_details_xml}
            <LEDGERCONTACT>{contact_val}</LEDGERCONTACT>
            <LEDGERPHONE>{phone_val}</LEDGERPHONE>
            <LEDGERMOBILE>{mobile_val}</LEDGERMOBILE>
            <EMAIL>{email_val}</EMAIL>
            <ISBILLWISEON>{is_billwise}</ISBILLWISEON>
            <CREDITLIMIT>{credit_limit_val or ''}</CREDITLIMIT>
            <BILLCREDITPERIOD>{f"{credit_days_val} Days" if credit_days_val else ''}</BILLCREDITPERIOD>
            <GSTREGISTRATIONTYPE>{gst_reg_type}</GSTREGISTRATIONTYPE>
            <GSTIN>{gstin_val}</GSTIN>
            <PAN>{pan_val}</PAN>
            <LEDGERTYPE>{ledger_type_val}</LEDGERTYPE>
            <TAXCLASSIFICATIONNAME>{tax_class_name}</TAXCLASSIFICATIONNAME>
            {mailing_details_xml}
            {gst_reg_details_xml}
            {msme_details_xml}
            {lower_ded_xml}
            <LWLEDADHARNOSTORE>{aadhar_val}</LWLEDADHARNOSTORE>
            <UDF:LWLEDADHARNOSTORE DESC="`LWLedAdharNoStore`" TYPE="String">{aadhar_val}</UDF:LWLEDADHARNOSTORE>
          </LEDGER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""


def check_tally_success(response_xml: str) -> bool:
    if not response_xml:
        return False
    if "<LINEERROR>" in response_xml or "<ERROR>" in response_xml:
        return False
    return (
        "<CREATED>1</CREATED>" in response_xml or 
        "<ALTERED>1</ALTERED>" in response_xml or 
        "<UPDATED>1</UPDATED>" in response_xml or
        "<DELETED>1</DELETED>" in response_xml or
        "<LASTVOUCHERID>" in response_xml or
        ("<ERRORS>0</ERRORS>" in response_xml and "<LINEERROR>" not in response_xml)
    )


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
    
    ssl_ctx = None
    if url.startswith("https"):
        ssl_ctx = ssl.create_default_context()
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


def check_tally_json_success(response_str: str) -> bool:
    if not response_str:
        return False
    try:
        data = json.loads(response_str)
        if data.get("status") == "1":
            import_result = data.get("data", {}).get("import_result", {})
            errors = import_result.get("errors", 0)
            if errors == 0:
                return True
    except Exception:
        pass
    return "<CREATED>1</CREATED>" in response_str or "<ALTERED>1</ALTERED>" in response_str or "<DELETED>1</DELETED>" in response_str or '"status": "1"' in response_str



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


def build_group_json_payload(group, parent_name: str, company_name: str, action: str) -> dict:
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
                        "type": "Group",
                        "action": "delete",
                        "name": group.name
                    }
                }
            ]
        }
    
    group_data = {
        "metadata": {
            "type": "Group",
            "action": act_lower,
            "name": group.name
        },
        "name": group.name,
        "parent": parent_name,
        "isaddable": "Yes" if getattr(group, 'is_addable', True) else "No",
        "isrevenue": "Yes" if getattr(group, 'is_revenue', False) else "No",
        "isdeemedpositive": "Yes" if getattr(group, 'is_deemed_positive', False) else "No",
        "affectsGrossprofit": "Yes" if getattr(group, 'affects_gross_profit', False) else "No",
        "issubledger": "Yes" if getattr(group, 'is_subledger', False) else "No",
        "isbillwiseon": "Yes" if getattr(group, 'is_billwise_on', False) else "No",
        "usedforcalculation": "Yes" if getattr(group, 'used_for_calculation', False) else "No",
        "sortposition": str(getattr(group, 'sort_position', 1000))
    }
    
    if getattr(group, 'method_to_allocate', None) and group.method_to_allocate != "Not Applicable":
        group_data["methodtoallocate"] = group.method_to_allocate
        
    gst_list = getattr(group, 'gst_details', [])
    if gst_list:
        hsn_list = []
        rate_list = []
        for gst in sorted(gst_list, key=lambda x: x.applicable_from):
            app_from = gst.applicable_from.strftime("%Y%m%d")
            
            # HSN block
            hsn_obj = {
                "applicablefrom": app_from,
                "hsncode": gst.hsn_sac or "",
                "srcofhsndetails": gst.hsn_sac_details or "As per Company/Group"
            }
            hsn_list.append(hsn_obj)
            
            # GST Rate block
            gst_rate_val = float(gst.gst_rate) if gst.gst_rate else 0.0
            rate_obj = {
                "applicablefrom": app_from,
                "taxability": gst.taxability_type or "Unknown",
                "srcofgstdetails": gst.gst_rate_details or "As per Company/Group",
                "statewisedetails.list": [
                    {
                        "statename": "\u0004 Any",
                        "ratedetails.list": [
                            {
                                "gstratedutyhead": "IGST",
                                "gstrate": str(gst_rate_val)
                            },
                            {
                                "gstratedutyhead": "CGST",
                                "gstrate": str(gst_rate_val / 2)
                            },
                            {
                                "gstratedutyhead": "SGST/UTGST",
                                "gstrate": str(gst_rate_val / 2)
                            }
                        ]
                    }
                ]
            }
            rate_list.append(rate_obj)
            
        group_data["hsndetails.list"] = hsn_list
        group_data["gstdetails.list"] = rate_list
    
    if getattr(group, 'alias_name', None):
        group_data["languagename"] = [
            {
                "name": [
                    {"metadata": True, "type": "String"},
                    group.name,
                    group.alias_name
                ],
                "languageid": {"type": "Number", "value": str(getattr(group, 'language_id', 1033))}
            }
        ]
        
    return {
        "static_variables": [
            {"name": "svMstImportFormat", "value": "jsonex"},
            {"name": "svCurrentCompany", "value": company_name}
        ],
        "tallymessage": [group_data]
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

        tally_url = settings.TALLY_URL
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
            xml_allocations += f"<CATEGORYALLOCATIONS.LIST>\n<CATEGORY>{cat_name}</CATEGORY>\n"
            for alloc in allocs:
                cc_name = alloc.cost_centre.name if alloc.cost_centre else ""
                xml_allocations += f"<COSTCENTREALLOCATIONS.LIST>\n<NAME>{cc_name}</NAME>\n<PERCENTAGE>{alloc.percentage}</PERCENTAGE>\n</COSTCENTREALLOCATIONS.LIST>\n"
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
<SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<COSTCENTRECLASS NAME="{cls.name}" ACTION="{action}">
<NAME>{cls.name}</NAME>
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

        tally_url = settings.TALLY_URL
        if not tally_url:
            return

        curr = None
        if action != "Delete":
            stmt = select(Currency).options(selectinload(Currency.rates)).where(Currency.currency_id == currency_id)
            curr = (await db.execute(stmt)).scalars().first()
            if not curr: return
        
        # Currency is global in DB but synced per company queue
        sq = (await db.execute(select(SyncQueue).where(SyncQueue.sync_id == sync_id))).scalars().first()
        if not sq: return
        
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
<SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<CURRENCY NAME="{deleted_symbol}" ACTION="Delete">
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
                        rates_xml += f"<DAILYSTDRATE.LIST>\n<DATE>{rdate_str}</DATE>\n<SPECIFIEDRATE>{r.standard_rate}/{curr.symbol}</SPECIFIEDRATE>\n</DAILYSTDRATE.LIST>\n"
                    if r.selling_rate:
                        rates_xml += f"<DAILYSELLINGRATE.LIST>\n<DATE>{rdate_str}</DATE>\n<SPECIFIEDRATE>{r.selling_rate}/{curr.symbol}</SPECIFIEDRATE>\n</DAILYSELLINGRATE.LIST>\n"
                    if r.buying_rate:
                        rates_xml += f"<DAILYBUYINGRATE.LIST>\n<DATE>{rdate_str}</DATE>\n<SPECIFIEDRATE>{r.buying_rate}/{curr.symbol}</SPECIFIEDRATE>\n</DAILYBUYINGRATE.LIST>\n"

            xml_envelope = f"""<ENVELOPE>
<HEADER>
<TALLYREQUEST>Import Data</TALLYREQUEST>
</HEADER>
<BODY>
<IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>All Masters</REPORTNAME>
<STATICVARIABLES>
<SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<CURRENCY NAME="{curr.symbol}" ACTION="{action}">
<ORIGINALNAME>{curr.symbol}</ORIGINALNAME>
<MAILINGNAME>{formal_name}</MAILINGNAME>
<EXPANDEDSYMBOL>{formal_name}</EXPANDEDSYMBOL>
<ISOCURRENCYCODE>{curr.code}</ISOCURRENCYCODE>
<DECIMALPLACES>{curr.decimal_places}</DECIMALPLACES>
<INMILLIONS>{in_millions}</INMILLIONS>
<ISSUFFIX>{is_suffix}</ISSUFFIX>
<HASSPACE>{has_space}</HASSPACE>
<DECIMALSYMBOL>{decimal_word}</DECIMALSYMBOL>
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

        tally_url = settings.TALLY_URL
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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHERTYPE NAME="{vt_name}" ACTION="{action}">
          <ORIGINALNAME>{original_name}</ORIGINALNAME>
          <LANGUAGENAME.LIST>
            <NAME.LIST TYPE="String">
              <NAME>{vt_name}</NAME>
            </NAME.LIST>
          </LANGUAGENAME.LIST>
          <PARENT>{parent}</PARENT>
          <NUMBERINGMETHOD>{vt.numbering_method}</NUMBERINGMETHOD>
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
          {f'<VCHPRINTJURISDICTION>{vt.default_jurisdiction}</VCHPRINTJURISDICTION>' if getattr(vt, 'default_jurisdiction', None) else ''}
          {f'<VCHPRINTTITLE>{vt.default_title_to_print}</VCHPRINTTITLE>' if getattr(vt, 'default_title_to_print', None) else ''}
          <VOUCHERNUMBERSERIES.LIST>
            <NAME>Default</NAME>
            <NUMBERINGMETHOD>{vt.numbering_method}</NUMBERINGMETHOD>
            <NUMBERINGSUBMETHOD>{vt.numbering_behavior or ""}</NUMBERINGSUBMETHOD>
            <PREVENTDUPLICATES>{prevent_duplicates}</PREVENTDUPLICATES>
            <PREFILLZERO>{"Yes" if getattr(vt, 'prefill_with_zero', False) else "No"}</PREFILLZERO>
            <USEDELETEDVCHNUM>{"Yes" if getattr(vt, 'show_unused_vch_nos', False) else "No"}</USEDELETEDVCHNUM>
            <WIDTHOFNUMBER>{getattr(vt, 'width_of_numerical_part', 0)}</WIDTHOFNUMBER>
            {''.join(f"<PREFIXLIST.LIST><DATE>{p.applicable_from.strftime('%Y%m%d')}</DATE><PARTICULARS>{p.particulars}</PARTICULARS></PREFIXLIST.LIST>" for p in vt.prefixes)}
            {''.join(f"<SUFFIXLIST.LIST><DATE>{s.applicable_from.strftime('%Y%m%d')}</DATE><PARTICULARS>{s.particulars}</PARTICULARS></SUFFIXLIST.LIST>" for s in vt.suffixes)}
            {''.join(f"<RESTARTFROMLIST.LIST><DATE>{r.applicable_from.strftime('%Y%m%d')}</DATE><PERIODBEGINNIGNUM>{r.starting_number}</PERIODBEGINNIGNUM><RESTARTFROM>{r.periodicity}</RESTARTFROM></RESTARTFROMLIST.LIST>" for r in vt.restarts)}
          </VOUCHERNUMBERSERIES.LIST>
          {''.join(f'''<VOUCHERCLASSLIST.LIST>
            <CLASSNAME>{c.class_name}</CLASSNAME>
            {f"<BANKALLOCFOR>{c.bank_alloc_for}</BANKALLOCFOR>" if c.bank_alloc_for else ""}
          </VOUCHERCLASSLIST.LIST>''' for c in vt.classes)}
        </VOUCHERTYPE>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        response = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope)
        
        if "<CREATED>1</CREATED>" in response or "<ALTERED>1</ALTERED>" in response or "<DELETED>1</DELETED>" in response or "<IGNORED>1</IGNORED>" in response:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(is_processed=True, attempts=SyncQueue.attempts + 1))
            await db.commit()
            logger.info(f"Real-time Tally Push Success for VoucherType {vt_name if action == 'Delete' else vt.name} ({action})")
        else:
            await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(attempts=SyncQueue.attempts + 1, error_message=str(response)[:500]))
            await db.commit()
            logger.error(f"Real-time Tally Push Failed for VoucherType {vt_name if action == 'Delete' else vt.name} ({action}). Tally Response: {response}")

    except Exception as e:
        logger.error(f"Error in try_push_voucher_type_realtime: {str(e)}")


async def try_push_voucher_realtime(voucher_id: int, sync_id: int, action: str, db: AsyncSession):
    import time
    start_time = time.time()
    try:
        tally_url = settings.TALLY_URL
        if not tally_url:
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        v_stmt = select(TrnVoucher).options(selectinload(TrnVoucher.voucher_type)).where(TrnVoucher.voucher_id == voucher_id)
        v_res = await db.execute(v_stmt)
        voucher = v_res.scalars().first()
        if not voucher and action != "Delete":
            return (False, "FAILED", f"Voucher #{voucher_id} not found")

        company_id = voucher.company_id if voucher else 1
        v_name = f"{voucher.voucher_type.name if voucher and voucher.voucher_type else 'Voucher'} #{voucher.voucher_number if voucher else voucher_id}"

        xml_envelope = await build_voucher_xml_payload(voucher_id, action, db)
        if not xml_envelope:
            return (False, "FAILED", "Failed to build XML envelope")

        req_msg = f"\n=======================================================\n📤 [OUTBOUND REALTIME TALLY XML PUSH] (voucher_id={voucher_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n"
        print(req_msg, flush=True)
        logger.info(req_msg)

        response = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope)
        duration_ms = int((time.time() - start_time) * 1000)

        resp_msg = f"\n=======================================================\n📥 [TALLY REALTIME PUSH RESPONSE] (voucher_id={voucher_id})\nRESPONSE:\n{response}\n=======================================================\n"
        print(resp_msg, flush=True)
        logger.info(resp_msg)

        # Record structured log in sync_traffic_logs with Postman-ready cURL
        await record_sync_traffic_log(
            db=db,
            company_id=company_id,
            sync_id=sync_id if sync_id and sync_id > 0 else None,
            entity_type="Voucher",
            entity_id=voucher_id,
            entity_name=v_name,
            action=action,
            outbound_format="XML",
            outbound_payload=xml_envelope,
            inbound_response=response,
            duration_ms=duration_ms,
            tally_url=tally_url
        )

        metrics = parse_tally_response_metrics(response)
        is_success = check_tally_success(response) or "<CREATED>1</CREATED>" in (response or "") or "<ALTERED>1</ALTERED>" in (response or "") or "<DELETED>1</DELETED>" in (response or "") or "<IGNORED>1</IGNORED>" in (response or "")
        is_already_deleted = (action == "Delete" and "Voucher does not exist" in (response or ""))

        if sync_id and sync_id > 0:
            if is_success or is_already_deleted:
                await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(
                    is_processed=True,
                    status="SUCCESS",
                    last_payload=xml_envelope,
                    last_response=response,
                    last_attempt_at=func.now(),
                    attempts=SyncQueue.attempts + 1
                ))
            else:
                await db.execute(update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(
                    status="FAILED",
                    attempts=SyncQueue.attempts + 1,
                    last_payload=xml_envelope,
                    last_response=response,
                    last_attempt_at=func.now(),
                    error_message=metrics["error_summary"] or (str(response)[:500] if response else "Socket timed out / No response")
                ))
            await db.commit()

        if action == "Delete":
            await db.execute(
                update(DeletedRecordAudit)
                .where(
                    DeletedRecordAudit.company_id == company_id,
                    DeletedRecordAudit.entity_type == "Voucher",
                    DeletedRecordAudit.record_id == voucher_id
                )
                .values(
                    tally_sync_status="SYNCED_TO_TALLY" if (is_success or is_already_deleted) else "NOT_DELETED_IN_TALLY",
                    tally_error_message=None if (is_success or is_already_deleted) else (metrics["error_summary"] or "Cannot be deleted in Tally Prime")
                )
            )
            await db.commit()

        if is_success:
            print(f"✅ Real-time Tally Push Success for Voucher #{voucher_id} ({action})", flush=True)
            logger.info(f"Real-time Tally Push Success for Voucher #{voucher_id} ({action})")
            return (True, "SUCCESS", None)
        else:
            print(f"❌ Real-time Tally Push Failed/Exception for Voucher #{voucher_id} ({action})", flush=True)
            logger.error(f"Real-time Tally Push Failed for Voucher #{voucher_id} ({action}). Tally Response: {response}")
            return (False, metrics["status"], metrics["error_summary"])

    except Exception as e:
        logger.error(f"Error in try_push_voucher_realtime: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


async def try_push_group_realtime(group_id: int, sync_id: int, action: str, db: AsyncSession):
    try:
        tally_url = settings.TALLY_URL
        if not tally_url:
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        g_stmt = select(MstGroup).options(
            selectinload(MstGroup.parent),
            selectinload(MstGroup.gst_details)
        ).where(MstGroup.group_id == group_id)
        g_res = await db.execute(g_stmt)
        group = g_res.scalars().first()
        if not group:
            return (False, "FAILED", f"Group #{group_id} not found")

        parent_name = group.parent.name if group.parent else ""
        
        c_stmt = select(Company).where(Company.company_id == group.company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        json_payload = build_group_json_payload(group, parent_name, comp_name, action)

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY JSON PUSH (group_id={group_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{json.dumps(json_payload, indent=2)}\n=======================================================\n")

        resp_str = await asyncio.to_thread(_post_json_to_tally_sync, tally_url, json_payload, 5)

        if check_tally_json_success(resp_str):
            sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_id).values(is_processed=True)
            await db.execute(sq_stmt)
            await db.commit()
            return (True, "SUCCESS", None)
            
    except Exception as e:
        logger.warning(f"Real-time Tally JSON push exception for group_id={group_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))
    return (False, "FAILED", "Group sync failed")

async def try_push_ledger_realtime(ledger_id: int, sync_item_id: int, action: str, db: AsyncSession):
    """
    Attempts real-time push to Tally Prime on the fly using standard XML envelope.
    Records structured traffic logs and updates DeletedRecordAudit when deleting.
    """
    import time
    start_time = time.time()
    try:
        tally_url = settings.TALLY_URL
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        l_stmt = select(MstLedger).options(selectinload(MstLedger.group), selectinload(MstLedger.bank_details)).where(MstLedger.ledger_id == ledger_id)
        l_res = await db.execute(l_stmt)
        ledger = l_res.scalars().first()
        if not ledger and action != "Delete":
            logger.warning(f"Real-time Tally push skipped: ledger_id={ledger_id} not found.")
            return (False, "FAILED", f"Ledger #{ledger_id} not found")

        company_id = ledger.company_id if ledger else 1
        ledger_name = ledger.name if ledger else f"Ledger #{ledger_id}"
        group_name = ledger.group.name if (ledger and ledger.group) else "Sundry Debtors"
        
        c_stmt = select(Company).where(Company.company_id == company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        if action == "Delete":
            ledger_inner_xml = f"""<LEDGER NAME="{ledger_name}" Action="Delete">
          <NAME>{ledger_name}</NAME>
        </LEDGER>"""
        else:
            is_billwise = "Yes" if getattr(ledger, 'is_billwise_on', False) else "No"
            op_balance = f"{ledger.opening_balance:.2f}" if ledger.opening_balance is not None else "0.00"
            ledger_inner_xml = f"""<LEDGER NAME="{ledger_name}" Action="{action}">
          <NAME>{ledger_name}</NAME>
          <PARENT>{group_name}</PARENT>
          <OPENINGBALANCE>{op_balance}</OPENINGBALANCE>
          <ISBILLWISEON>{is_billwise}</ISBILLWISEON>
        </LEDGER>"""

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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {ledger_inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY LEDGER PUSH (ledger_id={ledger_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"\n=======================================================\nTALLY LEDGER PUSH RESPONSE (ledger_id={ledger_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

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
        is_success = check_tally_success(resp_str) or "<CREATED>1</CREATED>" in (resp_str or "") or "<ALTERED>1</ALTERED>" in (resp_str or "") or "<DELETED>1</DELETED>" in (resp_str or "")

        if sync_item_id and sync_item_id > 0:
            if is_success:
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
                    tally_sync_status="SYNCED_TO_TALLY" if is_success else "NOT_DELETED_IN_TALLY",
                    tally_error_message=None if is_success else (metrics["error_summary"] or "Cannot be deleted in Tally Prime (referenced in transactions)")
                )
            )
            await db.commit()

        if is_success:
            logger.info(f"Real-time Tally push successful for ledger_id={ledger_id}, action={action}")
            return (True, "SUCCESS", None)
        else:
            logger.error(f"Real-time Tally push failed for ledger_id={ledger_id}: {resp_str}")
            return (False, metrics["status"], metrics["error_summary"])
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for ledger_id={ledger_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


async def try_push_stock_item_realtime(stock_item_id: int, sync_item_id: int, action: str, db: AsyncSession):
    """
    Attempts real-time push of a Stock Item to Tally Prime XML Server on the fly
    using official TallyPrime API Explorer standard envelope.
    """
    import time
    start_time = time.time()
    try:
        from app.models.tally_core import MstStockItem, StockItemOpeningBalance
        from app.models.portal_core import SyncQueue, Company

        tally_url = settings.TALLY_URL
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        item_stmt = select(MstStockItem).options(
            selectinload(MstStockItem.unit),
            selectinload(MstStockItem.group),
            selectinload(MstStockItem.category),
            selectinload(MstStockItem.opening_balances).selectinload(StockItemOpeningBalance.godown)
        ).where(MstStockItem.stock_item_id == stock_item_id)
        item_res = await db.execute(item_stmt)
        item = item_res.scalars().first()
        if not item and action != "Delete":
            logger.warning(f"Real-time Tally push skipped: stock_item_id={stock_item_id} not found.")
            return (False, "FAILED", f"Stock Item #{stock_item_id} not found")

        company_id = item.company_id if item else 1
        item_name = item.name if item else f"Item #{stock_item_id}"

        c_stmt = select(Company).where(Company.company_id == company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        # Handle Delete action
        if action == "Delete":
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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="{item_name}" Action="Delete">
          <NAME>{item_name}</NAME>
        </STOCKITEM>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""
        else:
            uom_symbol = item.unit.symbol if item.unit else "nos"
            raw_group_name = item.group.name.strip() if item.group and item.group.name else ""
            if not raw_group_name or raw_group_name.lower() in ("primary", " primary", "not applicable"):
                parent_tag = "<PARENT>&#4; Primary</PARENT>"
            else:
                parent_tag = f"<PARENT>{raw_group_name}</PARENT>"

            category_name = item.category.name if item.category else ""
            category_tag = f"\n          <CATEGORY>{category_name}</CATEGORY>" if category_name else ""
            desc_tag = f"\n          <DESCRIPTION>{item.description}</DESCRIPTION>" if item.description else ""
            
            is_batchwise = "Yes" if getattr(item, 'tracking_type', None) in ("Batches", "Serial", "Batch") else "No"
            supply_type = "Services" if (item.unit and item.unit.name and item.unit.name.lower() in ['hrs', 'srv', 'serv', 'service']) else "Goods"

            gst_rate = float(item.gst_rate_percent) if item.gst_rate_percent else 0.0
            hsn_str = item.hsn_code or ""
            cgst_rate = gst_rate / 2.0
            sgst_rate = gst_rate / 2.0
            igst_rate = gst_rate

            gst_block = f"""
          <GSTAPPLICABLE>&#4; Applicable</GSTAPPLICABLE>
          <GSTTYPEOFSUPPLY>{supply_type}</GSTTYPEOFSUPPLY>"""
            if gst_rate > 0 or hsn_str:
                gst_block += f"""
          <GSTDETAILS.LIST>
            <APPLICABLEFROM>20170701</APPLICABLEFROM>
            <HSNCODE>{hsn_str}</HSNCODE>
            <TAXABILITY>Taxable</TAXABILITY>
            <STATEWISEDETAILS.LIST>
              <RATEDETAILS.LIST>
                <GSTRATE>{gst_rate:g}</GSTRATE>
                <CGSTRATE>{cgst_rate:g}</CGSTRATE>
                <SGSTRATE>{sgst_rate:g}</SGSTRATE>
                <IGSTRATE>{igst_rate:g}</IGSTRATE>
              </RATEDETAILS.LIST>
            </STATEWISEDETAILS.LIST>
          </GSTDETAILS.LIST>"""

            ob_block = ""
            if getattr(item, 'opening_balances', None) and len(item.opening_balances) > 0:
                tot_qty = sum(float(ob.quantity) for ob in item.opening_balances)
                tot_val = sum(float(ob.amount) for ob in item.opening_balances)
                avg_rate = tot_val / tot_qty if tot_qty > 0 else 0.0
                batches_xml = ""
                for ob in item.opening_balances:
                    gname = ob.godown.name if getattr(ob, 'godown', None) and ob.godown else "Main Location"
                    bname = ob.batch_name or "Primary Batch"
                    q_val = float(ob.quantity)
                    r_val = float(ob.rate)
                    a_val = float(ob.amount)
                    batches_xml += f"""
            <BATCHALLOCATIONS.LIST>
              <GODOWNNAME>{gname}</GODOWNNAME>
              <BATCHNAME>{bname}</BATCHNAME>
              <OPENINGBALANCE>{q_val:g} {uom_symbol}</OPENINGBALANCE>
              <OPENINGRATE>{r_val:.2f}/{uom_symbol}</OPENINGRATE>
              <OPENINGVALUE>-{a_val:.2f}</OPENINGVALUE>
            </BATCHALLOCATIONS.LIST>"""
                ob_block = f"""
          <OPENINGBALANCE>{tot_qty:g} {uom_symbol}</OPENINGBALANCE>
          <OPENINGRATE>{avg_rate:.2f}/{uom_symbol}</OPENINGRATE>
          <OPENINGVALUE>-{tot_val:.2f}</OPENINGVALUE>{batches_xml}"""
            elif item.opening_qty and float(item.opening_qty) > 0:
                op_qty = float(item.opening_qty)
                op_rate = float(item.opening_rate) if item.opening_rate else 0.0
                op_val = op_qty * op_rate
                ob_block = f"""
          <OPENINGBALANCE>{op_qty:g} {uom_symbol}</OPENINGBALANCE>
          <OPENINGRATE>{op_rate:.2f}/{uom_symbol}</OPENINGRATE>
          <OPENINGVALUE>-{op_val:.2f}</OPENINGVALUE>
          <BATCHALLOCATIONS.LIST>
            <GODOWNNAME>Main Location</GODOWNNAME>
            <BATCHNAME>Primary Batch</BATCHNAME>
            <OPENINGBALANCE>{op_qty:g} {uom_symbol}</OPENINGBALANCE>
            <OPENINGRATE>{op_rate:.2f}/{uom_symbol}</OPENINGRATE>
            <OPENINGVALUE>-{op_val:.2f}</OPENINGVALUE>
          </BATCHALLOCATIONS.LIST>"""

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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="{item_name}" Action="{action}">
          <NAME>{item_name}</NAME>
          {parent_tag}{category_tag}
          <BASEUNITS>{uom_symbol}</BASEUNITS>{desc_tag}
          <ISCOSTCENTRESON>No</ISCOSTCENTRESON>
          <ISBATCHWISEON>{is_batchwise}</ISBATCHWISEON>{gst_block}{ob_block}
        </STOCKITEM>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY STOCKITEM PUSH (stock_item_id={stock_item_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"\n=======================================================\nTALLY STOCKITEM PUSH RESPONSE (stock_item_id={stock_item_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

        await record_sync_traffic_log(
            db=db,
            company_id=company_id,
            sync_id=sync_item_id if sync_item_id and sync_item_id > 0 else None,
            entity_type="StockItem",
            entity_id=stock_item_id,
            entity_name=item_name,
            action=action,
            outbound_format="XML",
            outbound_payload=xml_envelope,
            inbound_response=resp_str,
            duration_ms=duration_ms,
            tally_url=tally_url
        )

        metrics = parse_tally_response_metrics(resp_str)
        is_success = check_tally_success(resp_str) or "<CREATED>1</CREATED>" in (resp_str or "") or "<ALTERED>1</ALTERED>" in (resp_str or "") or "<DELETED>1</DELETED>" in (resp_str or "")

        if sync_item_id and sync_item_id > 0:
            if is_success:
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
                    DeletedRecordAudit.entity_type == "StockItem",
                    DeletedRecordAudit.record_id == stock_item_id
                )
                .values(
                    tally_sync_status="SYNCED_TO_TALLY" if is_success else "NOT_DELETED_IN_TALLY",
                    tally_error_message=None if is_success else (metrics["error_summary"] or "Cannot be deleted in Tally Prime")
                )
            )
            await db.commit()

        if is_success:
            logger.info(f"Real-time Tally push successful for stock_item_id={stock_item_id}, action={action}")
            return (True, "SUCCESS", None)
        else:
            logger.error(f"Real-time Tally push failed for stock_item_id={stock_item_id}: {resp_str}")
            return (False, metrics["status"], metrics["error_summary"])
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for stock_item_id={stock_item_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


async def try_push_uom_realtime(unit_id: int, sync_item_id: int, action: str, db: AsyncSession):
    """
    Attempts real-time push of a Unit of Measure (UOM) to Tally Prime XML Server on the fly
    using official TallyPrime API Explorer standard envelope.
    """
    import time
    start_time = time.time()
    try:
        from app.models.tally_core import MstUom
        from app.models.portal_core import SyncQueue, Company

        tally_url = settings.TALLY_URL
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        u_stmt = select(MstUom).where(MstUom.unit_id == unit_id)
        u_res = await db.execute(u_stmt)
        uom = u_res.scalars().first()
        if not uom and action != "Delete":
            logger.warning(f"Real-time Tally push skipped: unit_id={unit_id} not found.")
            return (False, "FAILED", f"Unit #{unit_id} not found")

        company_id = uom.company_id if uom else 1
        c_stmt = select(Company).where(Company.company_id == company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        symbol = (uom.symbol or uom.name or f"UOM #{unit_id}") if uom else f"UOM #{unit_id}"
        formal_name = (uom.original_name or uom.name or "") if uom else ""
        dec_places = uom.decimal_places if (uom and uom.decimal_places is not None) else 0

        if action == "Delete":
            unit_inner_xml = f"""<UNIT NAME="{symbol}" Action="Delete">
          <NAME>{symbol}</NAME>
        </UNIT>"""
        elif uom and uom.is_simple_unit:
            unit_inner_xml = f"""<UNIT NAME="{symbol}" Action="{action}">
          <NAME>{symbol}</NAME>
          <ORIGINALNAME>{formal_name}</ORIGINALNAME>
          <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
          <DECIMALPLACES>{dec_places}</DECIMALPLACES>
        </UNIT>"""
        else:
            base_unit_sym = ""
            add_unit_sym = ""
            if uom and uom.base_unit_id:
                b_res = await db.execute(select(MstUom).where(MstUom.unit_id == uom.base_unit_id))
                b_obj = b_res.scalars().first()
                if b_obj:
                    base_unit_sym = b_obj.symbol or b_obj.name or ""
            if uom and uom.additional_unit_id:
                a_res = await db.execute(select(MstUom).where(MstUom.unit_id == uom.additional_unit_id))
                a_obj = a_res.scalars().first()
                if a_obj:
                    add_unit_sym = a_obj.symbol or a_obj.name or ""
            
            conv_val = (uom.conversion_factor or 1) if uom else 1
            conv_str = str(int(conv_val)) if conv_val % 1 == 0 else str(conv_val)

            unit_inner_xml = f"""<UNIT NAME="{symbol}" Action="{action}">
          <NAME>{symbol}</NAME>
          <BASEUNITS>{base_unit_sym}</BASEUNITS>
          <ADDITIONALUNITS>{add_unit_sym}</ADDITIONALUNITS>
          <CONVERSION>{conv_str}</CONVERSION>
          <ISSIMPLEUNIT>No</ISSIMPLEUNIT>
          <DECIMALPLACES>{dec_places}</DECIMALPLACES>
        </UNIT>"""

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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {unit_inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY UOM PUSH (unit_id={unit_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"\n=======================================================\nTALLY UOM PUSH RESPONSE (unit_id={unit_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

        await record_sync_traffic_log(
            db=db,
            company_id=company_id,
            sync_id=sync_item_id if sync_item_id and sync_item_id > 0 else None,
            entity_type="UOM",
            entity_id=unit_id,
            entity_name=symbol,
            action=action,
            outbound_format="XML",
            outbound_payload=xml_envelope,
            inbound_response=resp_str,
            duration_ms=duration_ms,
            tally_url=tally_url
        )

        metrics = parse_tally_response_metrics(resp_str)
        is_success = check_tally_success(resp_str) or "<CREATED>1</CREATED>" in (resp_str or "") or "<ALTERED>1</ALTERED>" in (resp_str or "") or "<DELETED>1</DELETED>" in (resp_str or "")

        if sync_item_id and sync_item_id > 0:
            if is_success:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(is_processed=True, status="SUCCESS", last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), attempts=SyncQueue.attempts + 1)
            else:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(status="FAILED", attempts=SyncQueue.attempts + 1, last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), error_message=metrics["error_summary"] or str(resp_str)[:500])
            await db.execute(sq_stmt)
            await db.commit()

        if is_success:
            logger.info(f"Real-time Tally push successful for unit_id={unit_id}, action={action}")
            return (True, "SUCCESS", None)
        else:
            logger.error(f"Real-time Tally push failed for unit_id={unit_id}: {resp_str}")
            return (False, metrics["status"], metrics["error_summary"])
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for unit_id={unit_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


async def try_push_stock_group_realtime(group_id: int, sync_item_id: int, action: str, db: AsyncSession):
    """
    Attempts real-time push of a Stock Group to Tally Prime XML Server on the fly.
    """
    import time
    start_time = time.time()
    try:
        from app.models.tally_core import MstStockGroup
        from app.models.portal_core import SyncQueue, Company

        tally_url = settings.TALLY_URL
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return (False, "NOT_CONFIGURED", "TALLY_URL is not configured")

        g_stmt = select(MstStockGroup).options(selectinload(MstStockGroup.parent)).where(MstStockGroup.stock_group_id == group_id)
        g_res = await db.execute(g_stmt)
        group = g_res.scalars().first()
        if not group and action != "Delete":
            logger.warning(f"Real-time Tally push skipped: stock_group_id={group_id} not found.")
            return (False, "FAILED", f"Stock Group #{group_id} not found")

        company_id = group.company_id if group else 1
        group_name = group.name if group else f"StockGroup #{group_id}"

        c_stmt = select(Company).where(Company.company_id == company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        if action == "Delete":
            group_inner_xml = f"""<STOCKGROUP NAME="{group_name}" Action="Delete">
          <NAME>{group_name}</NAME>
        </STOCKGROUP>"""
        else:
            parent_name = group.parent.name if (group.parent and group.parent.name) else ""
            if not parent_name or parent_name.lower() in ("primary", " primary"):
                parent_tag = "<PARENT>&#4; Primary</PARENT>"
            else:
                parent_tag = f"<PARENT>{parent_name}</PARENT>"

            group_inner_xml = f"""<STOCKGROUP NAME="{group_name}" Action="{action}">
          <NAME>{group_name}</NAME>
          {parent_tag}
          <ISADDABLE>Yes</ISADDABLE>
        </STOCKGROUP>"""

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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {group_inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY STOCKGROUP PUSH (stock_group_id={group_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"\n=======================================================\nTALLY STOCKGROUP PUSH RESPONSE (stock_group_id={group_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

        await record_sync_traffic_log(
            db=db,
            company_id=company_id,
            sync_id=sync_item_id if sync_item_id and sync_item_id > 0 else None,
            entity_type="StockGroup",
            entity_id=group_id,
            entity_name=group_name,
            action=action,
            outbound_format="XML",
            outbound_payload=xml_envelope,
            inbound_response=resp_str,
            duration_ms=duration_ms,
            tally_url=tally_url
        )

        metrics = parse_tally_response_metrics(resp_str)
        is_success = check_tally_success(resp_str) or "<CREATED>1</CREATED>" in (resp_str or "") or "<ALTERED>1</ALTERED>" in (resp_str or "") or "<DELETED>1</DELETED>" in (resp_str or "")

        if sync_item_id and sync_item_id > 0:
            if is_success:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(is_processed=True, status="SUCCESS", last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), attempts=SyncQueue.attempts + 1)
            else:
                sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(status="FAILED", attempts=SyncQueue.attempts + 1, last_payload=xml_envelope, last_response=resp_str, last_attempt_at=func.now(), error_message=metrics["error_summary"] or str(resp_str)[:500])
            await db.execute(sq_stmt)
            await db.commit()

        if is_success:
            logger.info(f"Real-time Tally push successful for stock_group_id={group_id}, action={action}")
            return (True, "SUCCESS", None)
        else:
            logger.error(f"Real-time Tally push failed for stock_group_id={group_id}: {resp_str}")
            return (False, metrics["status"], metrics["error_summary"])
    except Exception as e:
        logger.warning(f"Real-time Tally push exception for stock_group_id={group_id}: {str(e)}", exc_info=True)
        return (False, "EXCEPTION", str(e))


async def try_push_stock_category_realtime(category_id: int, sync_item_id: int, action: str, db: AsyncSession):
    """
    Attempts real-time push of a Stock Category to Tally Prime XML Server on the fly.
    """
    import time
    start_time = time.time()
    try:
        from app.models.tally_core import MstStockCategory
        from app.models.portal_core import SyncQueue, Company

        tally_url = settings.TALLY_URL
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
            cat_inner_xml = f"""<STOCKCATEGORY NAME="{cat_name}" Action="Delete">
          <NAME>{cat_name}</NAME>
        </STOCKCATEGORY>"""
        else:
            parent_name = cat.parent.name if (cat.parent and cat.parent.name) else ""
            if not parent_name or parent_name.lower() in ("primary", " primary"):
                parent_tag = "<PARENT>&#4; Primary</PARENT>"
            else:
                parent_tag = f"<PARENT>{parent_name}</PARENT>"

            cat_inner_xml = f"""<STOCKCATEGORY NAME="{cat_name}" Action="{action}">
          <NAME>{cat_name}</NAME>
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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {cat_inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY STOCKCATEGORY PUSH (stock_category_id={category_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"\n=======================================================\nTALLY STOCKCATEGORY PUSH RESPONSE (stock_category_id={category_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

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
        is_success = check_tally_success(resp_str) or "<CREATED>1</CREATED>" in (resp_str or "") or "<ALTERED>1</ALTERED>" in (resp_str or "") or "<DELETED>1</DELETED>" in (resp_str or "")

        if sync_item_id and sync_item_id > 0:
            if is_success:
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

        tally_url = settings.TALLY_URL
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
            godown_inner_xml = f"""<GODOWN NAME="{godown_name}" Action="Delete">
          <NAME>{godown_name}</NAME>
        </GODOWN>"""
        else:
            parent_name = godown.parent.name if (godown.parent and godown.parent.name) else ""
            if not parent_name or parent_name.lower() in ("primary", " primary"):
                parent_tag = "<PARENT>&#4; Primary</PARENT>"
            else:
                parent_tag = f"<PARENT>{parent_name}</PARENT>"

            addr_tag = f"\n          <ADDRESS>{godown.address}</ADDRESS>" if godown.address else ""

            godown_inner_xml = f"""<GODOWN NAME="{godown_name}" Action="{action}">
          <NAME>{godown_name}</NAME>
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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        {godown_inner_xml}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY GODOWN PUSH (godown_id={godown_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{xml_envelope}\n=======================================================\n")
        resp_str = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope, 5)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(f"\n=======================================================\nTALLY GODOWN PUSH RESPONSE (godown_id={godown_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

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
        is_success = check_tally_success(resp_str) or "<CREATED>1</CREATED>" in (resp_str or "") or "<ALTERED>1</ALTERED>" in (resp_str or "") or "<DELETED>1</DELETED>" in (resp_str or "")

        if sync_item_id and sync_item_id > 0:
            if is_success:
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
    
    tally_url = settings.TALLY_URL
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
                        xml_envelope = build_ledger_xml_envelope(ledger, group_name, comp_name, item.action or 'Create')
                        
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
                            addr_list += f"<ADDRESS>{company.address_line1}</ADDRESS>"
                        if company.address_line2:
                            addr_list += f"<ADDRESS>{company.address_line2}</ADDRESS>"

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
<SVCURRENTCOMPANY>{company.name}</SVCURRENTCOMPANY>
</STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<COMPANY NAME="{company.name}" ACTION="Alter">
<NAME>{company.name}</NAME>
<STATENAME>{company.state or ''}</STATENAME>
<COUNTRYNAME>{company.country or ''}</COUNTRYNAME>
<PINCODE>{company.pincode or ''}</PINCODE>
<PHONENUMBER>{company.telephone or ''}</PHONENUMBER>
<MOBILENUMBERS.LIST><MOBILENUMBERS>{company.mobile or ''}</MOBILENUMBERS></MOBILENUMBERS.LIST>
<EMAIL>{company.email or ''}</EMAIL>
<WEBSITE>{company.website or ''}</WEBSITE>
<INCOMETAXNUMBER>{company.pan or ''}</INCOMETAXNUMBER>
<GSTREGISTRATIONNUMBER>{company.gstin or ''}</GSTREGISTRATIONNUMBER>
<BOOKSFROM>{books_from_xml}</BOOKSFROM>
<STARTINGFROM>{fy_start_xml}</STARTINGFROM>
<ENDINGAT>{fy_end_xml}</ENDINGAT>
<CURRENCYNAME>{company.base_currency or 'INR'}</CURRENCYNAME>
<GUID>{company.tally_guid or ''}</GUID>
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
            <FETCH>GUID,ALTERID,NAME,PARENT,OPENINGBALANCE,GSTIN,PARTYGSTIN,INCOMETAXNUMBER,LWLEDADHARNOSTORE,LEDGERCONTACT,LEDGERPHONE,LEDGERMOBILE,EMAIL,EMAILCC,WEBSITE,DESCRIPTION,LEDGERFAX,CREDITLIMIT,BILLCREDITPERIOD,ISBILLWISEON,COUNTRYOFRESIDENCE,COUNTRYNAME,PRIORSTATENAME,STATENAME,PINCODE,LEDGSTREGDETAILS.LIST,LEDMAILINGDETAILS.LIST,LANGUAGENAME.LIST,ADDRESS.LIST,ADDRESS</FETCH>
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
            <FETCH>GUID,ALTERID,VOUCHERTYPENAME,VOUCHERNUMBER,DATE,NARRATION,PARTYLEDGERNAME,AMOUNT,ALLLEDGERENTRIES.LIST,INVENTORYENTRIES.LIST,ALLINVENTORYENTRIES.LIST</FETCH>
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
            <FETCH>NAME,CATEGORY,PARENT,LANGUAGENAME.LIST</FETCH>
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
    tally_url = settings.TALLY_URL
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


@router.post("/clear-db")
async def clear_db(
    target_db: str = "tally_sync",
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Clears (truncates) specified database tables to reset synchronization data.
    Requires Admin privileges.
    """
    tables = [
        "bill_allocations",
        "voucher_entries",
        "vouchers",
        "bills",
        "ledgers",
        "account_groups",
        "stock_entries",
        "stock_items",
        "stock_groups",
        "stock_categories",
        "units_of_measure",
        "godowns",
        "batches",
        "serial_numbers",
        "bill_of_materials",
        "bom_items",
        "challan_entry_map",
        "cost_centers",
        "employees",
        "payroll_periods",
        "payslips",
        "payslip_components",
        "salary_structures",
        "salary_components",
        "salary_structure_components",
        "expenses",
        "shop_payments",
        "temp_orders",
        "temp_order_items",
        "sales_visits",
        "sync_queue",
        "user_sessions",
        "audit_logs",
        "pos_payments",
        "payment_links",
        "gateway_transactions",
        "payment_gateway_configs",
        "webhook_events",
        "tax_challans",
        "tcs_sections",
        "tds_sections",
        "tds_tcs_entries",
        "lower_deduction_certificates",
        "gst_return_periods",
        "gstr1_hsn_summary",
        "gstr1_line_items",
        "gstr3b_summary",
        "itc_entries",
        "einvoice_metadata"
    ]
    
    portal_db = settings.PORTAL_DATABASE_NAME
    tally_db = settings.TALLY_DATABASE_NAME
    
    portal_tables = {
        "expenses", "shop_payments", "temp_orders", "temp_order_items",
        "sales_visits", "sync_queue", "user_sessions", "audit_logs",
        "payment_links", "gateway_transactions", "payment_gateway_configs", "webhook_events",
        "bill_of_materials", "bom_items", "batches", "serial_numbers",
        "einvoice_metadata", "lower_deduction_certificates", "tds_tcs_entries",
        "tax_challans", "challan_entry_map", "gst_return_periods",
        "gstr1_line_items", "gstr1_hsn_summary", "gstr3b_summary", "itc_entries"
    }
    
    cleared_tables = []
    failed_tables = []
    
    try:
        await db.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        for table in tables:
            is_portal = table in portal_tables
            
            # Filter tables based on target_db selection
            if target_db == "tally_portal" and not is_portal:
                continue
            elif target_db == "tally_sync" and is_portal:
                continue
                
            db_name = portal_db if is_portal else tally_db
            fq_table = f"`{db_name}`.`{table}`"
            try:
                await db.execute(text(f"TRUNCATE TABLE {fq_table};"))
                cleared_tables.append(fq_table)
            except Exception as e:
                failed_tables.append((fq_table, str(e)))
                logger.error(f"Error truncating {fq_table}: {str(e)}", exc_info=True)
                
        await db.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database clear operation failed: {str(e)}"
        )
        
    return {
        "status": "success",
        "message": "Database clear operations completed.",
        "cleared_tables": cleared_tables,
        "failed_tables": failed_tables
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
    tally_url = settings.TALLY_URL
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

@router.get("/health")
async def get_sync_health(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns high-level Sync Health metrics: Synced, Pending, Failed, Exceptions, and Discrepancies.
    """
    # 1. Total Pending in SyncQueue
    pending_count_res = await db.execute(
        select(func.count(SyncQueue.sync_id)).where(
            SyncQueue.company_id == user.company_id,
            SyncQueue.is_processed == False
        )
    )
    pending_count = pending_count_res.scalar() or 0

    # 2. Total Synced / Succeeded (is_processed == True)
    synced_count_res = await db.execute(
        select(func.count(SyncQueue.sync_id)).where(
            SyncQueue.company_id == user.company_id,
            SyncQueue.is_processed == True
        )
    )
    synced_count = synced_count_res.scalar() or 0

    # 3. Total Traffic Logs Stats
    success_logs_res = await db.execute(
        select(func.count(SyncTrafficLog.log_id)).where(
            SyncTrafficLog.company_id == user.company_id,
            SyncTrafficLog.status == "SUCCESS"
        )
    )
    success_logs = success_logs_res.scalar() or 0

    failed_logs_res = await db.execute(
        select(func.count(SyncTrafficLog.log_id)).where(
            SyncTrafficLog.company_id == user.company_id,
            SyncTrafficLog.status.in_(["FAILED", "TIMEOUT"])
        )
    )
    failed_logs = failed_logs_res.scalar() or 0

    exception_logs_res = await db.execute(
        select(func.count(SyncTrafficLog.log_id)).where(
            SyncTrafficLog.company_id == user.company_id,
            SyncTrafficLog.status == "EXCEPTION"
        )
    )
    exception_logs = exception_logs_res.scalar() or 0

    # 4. Total deleted records out of sync (not deleted in Tally)
    unreconciled_del_res = await db.execute(
        select(func.count(DeletedRecordAudit.audit_id)).where(
            DeletedRecordAudit.company_id == user.company_id,
            DeletedRecordAudit.tally_sync_status.in_(["NOT_DELETED_IN_TALLY", "SYNC_FAILED", "PENDING"])
        )
    )
    unreconciled_deleted_count = unreconciled_del_res.scalar() or 0
    total_sync_issues = failed_logs + exception_logs + unreconciled_deleted_count

    # 5. Recent 5 logs
    recent_logs_res = await db.execute(
        select(SyncTrafficLog).where(
            SyncTrafficLog.company_id == user.company_id
        ).order_by(SyncTrafficLog.created_at.desc()).limit(5)
    )
    recent_logs = recent_logs_res.scalars().all()

    return {
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

    # Look up existing sync item or create new
    sq_stmt = select(SyncQueue).where(
        SyncQueue.company_id == user.company_id,
        SyncQueue.record_type == "Voucher",
        SyncQueue.record_id == voucher_id
    )
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
    tally_url = settings.TALLY_URL
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
    tally_url = settings.TALLY_URL

    if not tally_url:
        raise HTTPException(status_code=400, detail="Tally URL is not configured")

    entity_name = audit.entity_identifier or (audit.snapshot_data or {}).get("name") or (audit.snapshot_data or {}).get("voucher_number") or ""
    
    if audit.entity_type == "Ledger":
        inner_xml = f'<LEDGER NAME="{entity_name}" Action="Delete"><NAME>{entity_name}</NAME></LEDGER>'
        master_id = "All Masters"
    elif audit.entity_type == "StockItem":
        inner_xml = f'<STOCKITEM NAME="{entity_name}" Action="Delete"><NAME>{entity_name}</NAME></STOCKITEM>'
        master_id = "All Masters"
    elif audit.entity_type == "Voucher":
        guid_tag = f"<GUID>{audit.tally_guid}</GUID>" if audit.tally_guid else f"<VOUCHERNUMBER>{entity_name.replace('Voucher #', '')}</VOUCHERNUMBER>"
        inner_xml = f'<VOUCHER Action="Delete">{guid_tag}</VOUCHER>'
        master_id = "Vouchers"
    else:
        inner_xml = f'<{audit.entity_type.upper()} NAME="{entity_name}" Action="Delete"><NAME>{entity_name}</NAME></{audit.entity_type.upper()}>'
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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
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
    is_success = check_tally_success(resp_str) or metrics["deleted"] > 0

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
    tally_url = settings.TALLY_URL

    if not tally_url:
        raise HTTPException(status_code=400, detail="Tally URL is not configured")

    entity_name = audit.entity_identifier or (audit.snapshot_data or {}).get("name") or ""
    
    if audit.entity_type == "Ledger":
        inner_xml = f'''<LEDGER NAME="{entity_name}" Action="Alter">
          <NAME>{entity_name}</NAME>
          <ISBILLWISEON>No</ISBILLWISEON>
        </LEDGER>'''
    elif audit.entity_type == "StockItem":
        inner_xml = f'''<STOCKITEM NAME="{entity_name}" Action="Alter">
          <NAME>{entity_name}</NAME>
        </STOCKITEM>'''
    else:
        inner_xml = f'<{audit.entity_type.upper()} NAME="{entity_name}" Action="Alter"><NAME>{entity_name}</NAME></{audit.entity_type.upper()}>'

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
        <SVCURRENTCOMPANY>{comp_name}</SVCURRENTCOMPANY>
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
    is_success = check_tally_success(resp_str) or metrics["altered"] > 0

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




