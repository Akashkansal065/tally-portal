import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from typing import List, Dict, Any
import json
from decimal import Decimal

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.ledger import MstLedger, MstGroup
from app.models.voucher import TrnVoucher, TrnAccounting
from app.models.sync import SyncQueue
from app.services.tally_xml_importer import import_tally_xml

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
                logger.error(f"Background inbound sync exception for company_id={company_id}: {str(e)}")

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

