import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete, text
from sqlalchemy.sql import func
from typing import List, Dict, Any
import json
from decimal import Decimal
import urllib.request
import logging

from app.core.database import get_db
from app.core.permissions import require_permission
from app.core.config import settings
from app.routers.admin import require_admin
from app.models.user import User
from app.models.ledger import MstLedger, MstGroup
from app.models.voucher import TrnVoucher, TrnAccounting
from app.models.sync import SyncQueue
from app.services.tally_xml_importer import import_tally_xml

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/sync", tags=["Tally Synchronization"])

# Global lock to serialize inbound sync background tasks and prevent deadlocks
sync_lock = asyncio.Lock()

async def run_inbound_sync_background(xml_data: str, company_id: int):
    """Asynchronously parses and imports inbound Tally XML, serialized via a global lock."""
    from app.core.database import AsyncSessionLocal
    from app.core.cache import clear_company_cache
    import logging
    logger = logging.getLogger("uvicorn.error")

    async with sync_lock:
        async with AsyncSessionLocal() as db:
            try:
                logger.info(f"Background inbound sync task started for company_id={company_id}")
                result = await import_tally_xml(xml_data, db, company_id)
                if result.get("status") == "error":
                    logger.error(f"Background inbound sync failed for company_id={company_id}: {result.get('message')}")
                else:
                    logger.info(f"Background inbound sync succeeded for company_id={company_id}: {result}")
                    clear_company_cache(company_id)
            except Exception as e:
                logger.error(f"Background inbound sync exception for company_id={company_id}: {str(e)}", exc_info=True)

@router.post("/inbound")
async def inbound_sync(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_permission("ledgers", "create"))
):
    """
    Receives raw Tally XML export from sync bridge daemon, queueing it for async processing.
    """
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
        
    background_tasks.add_task(run_inbound_sync_background, xml_data, user.company_id)
    
    return {
        "status": "success",
        "message": "Inbound sync payload received and queued for background processing.",
        "imported_groups": 0, "imported_ledgers": 0, "imported_vouchers": 0,
        "imported_stock_groups": 0, "imported_uoms": 0, "imported_godowns": 0,
        "imported_stock_categories": 0, "imported_stock_items": 0
    }

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
                # Find group name
                g_stmt = select(MstGroup).where(MstGroup.group_id == ledger.group_id)
                g_res = await db.execute(g_stmt)
                group = g_res.scalars().first()
                group_name = group.name if group else "Sundry Debtors"
                
                # Build Tally XML Envelope
                xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <IMPORTDUPS>@@RequestImportDups</IMPORTDUPS>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <LEDGER NAME="{ledger.name}" ACTION="Create">
          <NAME>{ledger.name}</NAME>
          <PARENT>{group_name}</PARENT>
          <OPENINGBALANCE>{'-' if ledger.opening_balance_type == 'Dr' else ''}{ledger.opening_balance}</OPENINGBALANCE>
          <GSTIN>{ledger.gstin or ''}</GSTIN>
        </LEDGER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""
                
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


def _post_to_tally_sync(url: str, xml_payload: str) -> str:
    encoded_data = xml_payload.encode('utf-16-le')
    req = urllib.request.Request(
        url,
        data=encoded_data,
        headers={
            'Content-Type': 'text/xml;charset=utf-16',
            'Content-Length': str(len(encoded_data))
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        raw_bytes = response.read()
        try:
            return raw_bytes.decode('utf-16')
        except (UnicodeDecodeError, UnicodeError):
            return raw_bytes.decode('utf-8', errors='ignore')


def check_tally_success(response_xml: str) -> bool:
    return (
        "<CREATED>1</CREATED>" in response_xml or 
        "<UPDATED>1</UPDATED>" in response_xml or 
        "<ERRORS>0</ERRORS>" in response_xml
    )


async def run_once_sync_background(company_id: int):
    """
    Executes a single cycle of bidirectional synchronization with the Tally XML Server in the background.
    """
    from app.core.database import AsyncSessionLocal
    from app.core.cache import clear_company_cache
    
    tally_url = settings.TALLY_URL
    if not tally_url:
        logger.error(f"Background run-once sync aborted for company_id={company_id}: TALLY_URL is not configured.")
        return

    logger.info(f"Background run-once sync started for company_id={company_id}")
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. PHASE 1: Outbound Sync (ERP -> Tally)
            stmt = select(SyncQueue).where(
                SyncQueue.company_id == company_id,
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
                        g_stmt = select(MstGroup).where(MstGroup.group_id == ledger.group_id)
                        g_res = await db.execute(g_stmt)
                        group = g_res.scalars().first()
                        group_name = group.name if group else "Sundry Debtors"
                        
                        xml_envelope = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <IMPORTDUPS>@@RequestImportDups</IMPORTDUPS>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <LEDGER NAME="{ledger.name}" ACTION="Create">
          <NAME>{ledger.name}</NAME>
          <PARENT>{group_name}</PARENT>
          <OPENINGBALANCE>{'-' if ledger.opening_balance_type == 'Dr' else ''}{ledger.opening_balance}</OPENINGBALANCE>
          <GSTIN>{ledger.gstin or ''}</GSTIN>
        </LEDGER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""
                        
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
                    try:
                        resp_xml = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_envelope)
                        if check_tally_success(resp_xml):
                            item.is_processed = True
                            outbound_success += 1
                    except Exception as e:
                        logger.error(f"Failed to sync outbound item {item.sync_id} to Tally in background: {str(e)}", exc_info=True)
                        
            if outbound_success > 0:
                await db.commit()

            # 2. PHASE 2: Inbound Sync (Tally -> ERP) with ALTERID
            ledger_stmt = select(func.max(MstLedger.tally_alter_id)).where(MstLedger.company_id == company_id)
            ledger_res = await db.execute(ledger_stmt)
            max_ledger_alter = ledger_res.scalar() or 0
            
            voucher_stmt = select(func.max(TrnVoucher.tally_alter_id)).where(TrnVoucher.company_id == company_id)
            voucher_res = await db.execute(voucher_stmt)
            max_voucher_alter = voucher_res.scalar() or 0

            queries = {
                "Groups": """<ENVELOPE>
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
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="IncrementalLedgers">
            <TYPE>Ledger</TYPE>
            <FETCH>GUID,ALTERID,NAME,PARENT,OPENINGBALANCE,GSTIN,LEDGSTREGDETAILS.LIST,LEDMAILINGDETAILS.LIST</FETCH>
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
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="IncrementalVouchers">
            <TYPE>Voucher</TYPE>
            <FETCH>GUID,ALTERID,DATE,VOUCHERTYPENAME,VOUCHERNUMBER,NARRATION,ALLLEDGERENTRIES.LIST,LEDGERENTRIES.LIST,INVENTORYENTRIES.LIST</FETCH>
            <FILTERS>AlteredFilter</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="AlteredFilter">
            $ALTERID &gt; {max_voucher_alter}
          </SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                "StockGroups": """<ENVELOPE>
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
                "Units": """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllUnits</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllUnits">
            <TYPE>Unit</TYPE>
            <FETCH>NAME,SYMBOL,DECIMALPLACES</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>""",
                "Godowns": """<ENVELOPE>
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
                "StockCategories": """<ENVELOPE>
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
                "StockItems": """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>AllStockItems</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="AllStockItems">
            <TYPE>StockItem</TYPE>
            <FETCH>NAME,PARENT,CATEGORY,BASEUNITS,OPENINGBALANCE,OPENINGVALUE,INFGSTHSNCODE,INFGSTIGSTRATE</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""
            }

            import_results = {}
            total_imported = {
                "groups": 0, "ledgers": 0, "vouchers": 0,
                "stock_groups": 0, "uoms": 0, "godowns": 0,
                "stock_categories": 0, "stock_items": 0
            }
            
            async with sync_lock:
                for name, xml_payload in queries.items():
                    try:
                        resp_xml = await asyncio.to_thread(_post_to_tally_sync, tally_url, xml_payload)
                        if not resp_xml or "<ENVELOPE>" not in resp_xml:
                            import_results[name] = {"status": "skipped", "message": "Tally returned empty/invalid response."}
                            continue
                        
                        res = await import_tally_xml(resp_xml, db, company_id)
                        import_results[name] = res
                        
                        if res.get("status") == "success":
                            total_imported["groups"] += res.get("imported_groups", 0)
                            total_imported["ledgers"] += res.get("imported_ledgers", 0)
                            total_imported["vouchers"] += res.get("imported_vouchers", 0)
                            total_imported["stock_groups"] += res.get("imported_stock_groups", 0)
                            total_imported["uoms"] += res.get("imported_uoms", 0)
                            total_imported["godowns"] += res.get("imported_godowns", 0)
                            total_imported["stock_categories"] += res.get("imported_stock_categories", 0)
                            total_imported["stock_items"] += res.get("imported_stock_items", 0)
                    except Exception as e:
                        import_results[name] = {"status": "error", "message": str(e)}
                        logger.error(f"Background Inbound sync failed for collection {name}: {str(e)}", exc_info=True)

            clear_company_cache(company_id)
            logger.info(f"Background run-once sync completed for company_id={company_id}: {total_imported}")
        except Exception as e:
            logger.error(f"Background run-once sync failed with exception for company_id={company_id}: {str(e)}", exc_info=True)


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

    background_tasks.add_task(run_once_sync_background, user.company_id)

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

