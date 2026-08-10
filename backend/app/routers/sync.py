import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import update, delete, text
from sqlalchemy.sql import func
from typing import List, Dict, Any, Optional
import json
from decimal import Decimal
import urllib.request
import logging

from app.core.database import get_db
from app.core.permissions import require_permission
from app.core.config import settings
from app.routers.admin import require_admin
from app.models.portal_core import Company
from app.models.tally_core import MstLedger, MstGroup
from app.models.tally_core import TrnVoucher, TrnAccounting
from app.models.portal_core import SyncQueue
from app.services.tally_xml_importer import import_tally_xml

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/sync", tags=["Tally Synchronization"])

# Global lock to serialize inbound sync background tasks and prevent deadlocks
sync_lock = asyncio.Lock()

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
        result = await import_tally_xml(xml_data, db, user.user_id, override_company_name=company_name)
        company_id = result.get("company_id")
        if company_id:
            from app.core.cache import clear_company_cache
            clear_company_cache(company_id)
        return result

@router.get("/outbound-queue")
async def get_outbound_queue(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns unsynced local creations/modifications formatted as Tally-compatible XML payloads.
    """
    stmt = select(SyncQueue).where(
        SyncQueue.company_id == user.company_id,
        SyncQueue.is_processed == False
    ).order_by(SyncQueue.created_at.asc())
    
    res = await db.execute(stmt)
    queue_items = res.scalars().all()
    
    outbound_payloads = []
    
    for item in queue_items:
        xml_envelope = ""
        # 1. Map Ledger Creation
        if item.record_type == "Ledger":
            l_stmt = select(MstLedger).where(MstLedger.ledger_id == item.record_id).options(
                # selectinload group if needed
            )
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
            v_stmt = select(TrnVoucher).where(TrnVoucher.voucher_id == item.record_id)
            v_res = await db.execute(v_stmt)
            voucher = v_res.scalars().first()
            if voucher:
                # Get entries
                ent_stmt = select(TrnAccounting).where(TrnAccounting.voucher_id == voucher.voucher_id)
                ent_res = await db.execute(ent_stmt)
                entries = ent_res.scalars().all()
                
                entries_xml = ""
                for ent in entries:
                    l_stmt = select(MstLedger).where(MstLedger.ledger_id == ent.ledger_id)
                    l_res = await db.execute(l_stmt)
                    ledger = l_res.scalars().first()
                    led_name = ledger.name if ledger else "Suspense A/c"
                    
                    # Convert Debit/Credit back to Tally amount: Negative -> Debit, Positive -> Credit
                    amt = -ent.debit_amount if ent.debit_amount > 0 else ent.credit_amount
                    
                    entries_xml += f"""
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>{led_name}</LEDGERNAME>
            <ISDEEMEDPOSITIVE>{'Yes' if ent.debit_amount > 0 else 'No'}</ISDEEMEDPOSITIVE>
            <AMOUNT>{amt}</AMOUNT>
          </ALLLEDGERENTRIES.LIST>"""
                
                vdate_str = voucher.voucher_date.strftime("%Y%m%d")
                xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Vouchers</ID>
  </HEADER>
  <BODY>
    <DESC></DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHER DATE="{vdate_str}" VOUCHERTYPENAME="Journal" ACTION="Create">
          <DATE>{vdate_str}</DATE>
          <VOUCHERNUMBER>{voucher.voucher_number}</VOUCHERNUMBER>
          <VOUCHERTYPENAME>Journal</VOUCHERTYPENAME>
          {entries_xml}
          <NARRATION>{voucher.narration or ''}</NARRATION>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
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
    stmt = update(SyncQueue).where(
        SyncQueue.sync_id.in_(sync_ids),
        SyncQueue.company_id == user.company_id
    ).values(is_processed=True)
    
    await db.execute(stmt)
    await db.commit()
    return {"status": "success", "message": f"Successfully acknowledged {len(sync_ids)} sync tasks."}

@router.get("/last-alter-id")
async def get_last_alter_id(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the maximum tally_alter_id from ledgers and vouchers to use for incremental inbound sync.
    """
    from sqlalchemy.sql import func
    # Get max alter_id from ledgers
    ledger_stmt = select(func.max(MstLedger.tally_alter_id)).where(MstLedger.company_id == user.company_id)
    ledger_res = await db.execute(ledger_stmt)
    max_ledger_alter = ledger_res.scalar() or 0
    
    # Get max alter_id from vouchers
    voucher_stmt = select(func.max(TrnVoucher.tally_alter_id)).where(TrnVoucher.company_id == user.company_id)
    voucher_res = await db.execute(voucher_stmt)
    max_voucher_alter = voucher_res.scalar() or 0
    
    return {
        "last_ledger_alter_id": int(max_ledger_alter),
        "last_voucher_alter_id": int(max_voucher_alter),
        "last_alter_id": int(max(max_ledger_alter, max_voucher_alter))
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

    gst_reg_details_xml = f"""<LEDGSTREGDETAILS.LIST>
      <APPLICABLEFROM>20250401</APPLICABLEFROM>
      <GSTREGISTRATIONTYPE>{gst_reg_type}</GSTREGISTRATIONTYPE>
      <GSTIN>{gstin_val}</GSTIN>
    </LEDGSTREGDETAILS.LIST>""" if (gst_reg_type or gstin_val) else ""

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
            <INCOMETAXNUMBER>{pan_val}</INCOMETAXNUMBER>
            <GSTIN>{gstin_val}</GSTIN>
            <PARTYGSTIN>{gstin_val}</PARTYGSTIN>
            <GSTREGISTRATIONTYPE>{gst_reg_type}</GSTREGISTRATIONTYPE>
            {gst_reg_details_xml}
            <ISBILLWISEON>{is_billwise}</ISBILLWISEON>
            <CREDITLIMIT>{credit_limit_val or ''}</CREDITLIMIT>
            <BILLCREDITPERIOD>{f"{credit_days_val} Days" if credit_days_val else ''}</BILLCREDITPERIOD>
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
                "applicablefrom": "20250401",
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
                "applicablefrom": "20250401",
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
</REQUESTDATA>
</IMPORTDATA>
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

async def try_push_group_realtime(group_id: int, sync_id: int, action: str, db: AsyncSession):
    try:
        tally_url = settings.TALLY_URL
        if not tally_url:
            return False

        g_stmt = select(MstGroup).options(
            selectinload(MstGroup.parent),
            selectinload(MstGroup.gst_details)
        ).where(MstGroup.group_id == group_id)
        g_res = await db.execute(g_stmt)
        group = g_res.scalars().first()
        if not group:
            return False

        parent_name = group.parent.name if group.parent else ""
        
        c_stmt = select(Company).where(Company.company_id == group.company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        json_payload = build_group_json_payload(group, parent_name, comp_name, action)

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY JSON PUSH (group_id={group_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{json.dumps(json_payload, indent=2)}\n=======================================================\n")

        resp_str = await asyncio.to_thread(_post_json_to_tally_sync, tally_url, json_payload, 5)

        if check_tally_json_success(resp_str):
            sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(is_processed=True)
            await db.execute(sq_stmt)
            await db.commit()
            return True
            
    except Exception as e:
        logger.warning(f"Real-time Tally JSON push exception for group_id={group_id}: {str(e)}", exc_info=True)
    return False

async def try_push_ledger_realtime(ledger_id: int, sync_item_id: int, action: str, db: AsyncSession):
    """
    Attempts real-time push to Tally Prime on the fly using JSON API (Tally_Ledger_apis.md schema).
    If Tally is reachable and succeeds, marks SyncQueue item as processed (is_processed=True).
    If Tally is unreachable/times out, leaves SyncQueue item as is_processed=False to sync later.
    """
    try:
        tally_url = settings.TALLY_URL
        if not tally_url:
            logger.warning("Real-time Tally push skipped: TALLY_URL is not configured.")
            return False

        l_stmt = select(MstLedger).options(selectinload(MstLedger.group), selectinload(MstLedger.bank_details)).where(MstLedger.ledger_id == ledger_id)
        l_res = await db.execute(l_stmt)
        ledger = l_res.scalars().first()
        if not ledger:
            logger.warning(f"Real-time Tally push skipped: ledger_id={ledger_id} not found.")
            return False

        group_name = ledger.group.name if ledger.group else "Sundry Debtors"
        
        c_stmt = select(Company).where(Company.company_id == ledger.company_id)
        c_res = await db.execute(c_stmt)
        comp_obj = c_res.scalars().first()
        comp_name = comp_obj.name if comp_obj else ""

        json_payload = build_ledger_json_payload(ledger, group_name, comp_name, action)

        logger.info(f"\n=======================================================\nOUTBOUND REALTIME TALLY JSON PUSH (ledger_id={ledger_id}, action={action})\nURL: {tally_url}\nPAYLOAD:\n{json.dumps(json_payload, indent=2)}\n=======================================================\n")

        resp_str = await asyncio.to_thread(_post_json_to_tally_sync, tally_url, json_payload, 5)
        
        logger.info(f"\n=======================================================\nTALLY JSON PUSH RESPONSE (ledger_id={ledger_id})\nRESPONSE:\n{resp_str}\n=======================================================\n")

        if check_tally_json_success(resp_str):
            sq_stmt = update(SyncQueue).where(SyncQueue.sync_id == sync_item_id).values(is_processed=True)
            await db.execute(sq_stmt)
            await db.commit()
            logger.info(f"Real-time Tally JSON push successful for ledger_id={ledger_id}, action={action}")
            return True
        else:
            logger.error(f"Real-time Tally JSON push failed for ledger_id={ledger_id}: {resp_str}")
    except Exception as e:
        logger.warning(f"Real-time Tally JSON push exception for ledger_id={ledger_id}: {str(e)}", exc_info=True)
    return False


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
                    v_stmt = select(TrnVoucher).where(TrnVoucher.voucher_id == item.record_id)
                    v_res = await db.execute(v_stmt)
                    voucher = v_res.scalars().first()
                    if voucher:
                        # Get entries
                        ent_stmt = select(TrnAccounting).where(TrnAccounting.voucher_id == voucher.voucher_id)
                        ent_res = await db.execute(ent_stmt)
                        entries = ent_res.scalars().all()
                        
                        entries_xml = ""
                        for ent in entries:
                            l_stmt = select(MstLedger).where(MstLedger.ledger_id == ent.ledger_id)
                            l_res = await db.execute(l_stmt)
                            ledger = l_res.scalars().first()
                            led_name = ledger.name if ledger else "Suspense A/c"
                            
                            # Convert Debit/Credit back to Tally amount: Negative -> Debit, Positive -> Credit
                            amt = -ent.debit_amount if ent.debit_amount > 0 else ent.credit_amount
                            
                            entries_xml += f"""
                  <ALLLEDGERENTRIES.LIST>
                    <LEDGERNAME>{led_name}</LEDGERNAME>
                    <ISDEEMEDPOSITIVE>{'Yes' if ent.debit_amount > 0 else 'No'}</ISDEEMEDPOSITIVE>
                    <AMOUNT>{amt}</AMOUNT>
                  </ALLLEDGERENTRIES.LIST>"""
                        
                        vdate_str = voucher.voucher_date.strftime("%Y%m%d")
                        xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>Vouchers</ID>
  </HEADER>
  <BODY>
    <DESC></DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <VOUCHER DATE="{vdate_str}" VOUCHERTYPENAME="Journal" ACTION="Create">
          <DATE>{vdate_str}</DATE>
          <VOUCHERNUMBER>{voucher.voucher_number}</VOUCHERNUMBER>
          <VOUCHERTYPENAME>Journal</VOUCHERTYPENAME>
          {entries_xml}
          <NARRATION>{voucher.narration or ''}</NARRATION>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""

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
<BASICCOMPANYPHONE>{company.telephone or ''}</BASICCOMPANYPHONE>
<BASICCOMPANYMOBILE>{company.mobile or ''}</BASICCOMPANYMOBILE>
<BASICCOMPANYEMAIL>{company.email or ''}</BASICCOMPANYEMAIL>
<WEBSITE>{company.website or ''}</WEBSITE>
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
            <FETCH>NAME,PARENT,NUMBERINGMETHOD,PREVENTDUPLICATES,ALTERID,GUID</FETCH>
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
                            resp_xml = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_payload)
                            if not resp_xml:
                                logger.warning(f"[SYNC WARNING] Empty response from Tally for collection '{name}'. Skipping.")
                                continue
                            if "<ENVELOPE>" not in resp_xml:
                                logger.warning(f"[SYNC WARNING] Invalid response (no <ENVELOPE> tag) from Tally for collection '{name}'. Response snippet: {resp_xml[:200]}...")
                                continue
                            
                            logger.info(f"[SYNC INFO] Received {len(resp_xml)} bytes from Tally for collection '{name}'.")
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
                                
                                logger.info(
                                    f"[SYNC SUCCESS] Collection '{name}' imported successfully. "
                                    f"Counts - Groups: {c_groups}, Ledgers: {c_ledgers}, Vouchers: {c_vouchers}, "
                                    f"StockItems: {c_stock_items}, Currencies: {c_currencies}, VoucherTypes: {c_voucher_types}"
                                )
                                
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
                                logger.error(f"[SYNC ERROR] Failed to import collection '{name}'. Error: {err_msg}")
                        except Exception as e:
                            logger.error(f"[SYNC FATAL] Exception while processing collection '{name}': {str(e)}", exc_info=True)

            logger.info(f"[SYNC COMPLETED] Background run-once sync finished for user_id={user_id}: {total_imported}")
        except Exception as e:
            logger.error(f"[SYNC FATAL] Background run-once sync failed with exception for user_id={user_id}: {str(e)}", exc_info=True)


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

