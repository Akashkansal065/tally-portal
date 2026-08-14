from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from decimal import Decimal
from app.models.tally_core import MstStockItem, MstLedger, GstRegistration, MstGroup
from app.schemas.voucher import InventoryEntryCreate, AccountingAllocationCreate

async def get_tax_ledger(db: AsyncSession, company_id: int, tax_type: str) -> Optional[int]:
    """Finds a tax ledger by name (CGST, SGST, IGST) under Duties & Taxes."""
    stmt = (
        select(MstLedger)
        .join(MstGroup, MstLedger.group_id == MstGroup.group_id)
        .where(
            MstLedger.company_id == company_id,
            MstGroup.name.ilike('%Duties & Taxes%'),
            MstLedger.name.ilike(f'%{tax_type}%')
        )
    )
    res = await db.execute(stmt)
    ledger = res.scalars().first()
    return ledger.ledger_id if ledger else None

async def compute_gst_allocations(
    company_id: int,
    party_ledger_id: int,
    gst_registration_id: Optional[int],
    inventory_entries: List[InventoryEntryCreate],
    db: AsyncSession,
    is_sales: bool = False
):
    """
    Computes automatic GST allocations for inventory entries.
    Returns a flat list of dicts: { 'item_index': i, 'ledger_id': id, 'is_deemed_positive': bool, 'amount': Decimal }
    """
    # 1. Resolve states
    party_state = None
    if party_ledger_id:
        party_res = await db.execute(select(MstLedger).where(MstLedger.ledger_id == party_ledger_id))
        party = party_res.scalars().first()
        if party:
            party_state = party.state

    company_state = None
    if gst_registration_id:
        reg_res = await db.execute(select(GstRegistration).where(GstRegistration.id == gst_registration_id))
        reg = reg_res.scalars().first()
        if reg:
            company_state = reg.registered_state
            
    is_interstate = (party_state != company_state) if (party_state and company_state) else False
    
    # 2. Get Tax Ledgers
    cgst_ledger_id = await get_tax_ledger(db, company_id, 'CGST')
    sgst_ledger_id = await get_tax_ledger(db, company_id, 'SGST')
    igst_ledger_id = await get_tax_ledger(db, company_id, 'IGST')
    
    allocations = []
    
    # In Sales: Tax is Credit (is_deemed_positive = False)
    # In Purchase: Tax is Debit (is_deemed_positive = True)
    is_dp = not is_sales
    
    for idx, entry in enumerate(inventory_entries):
        # Ignore if user already provided manual allocations
        if entry.accounting_allocations:
            continue
            
        item_res = await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == entry.stock_item_id))
        item = item_res.scalars().first()
        if not item or not item.gst_rate_percent:
            continue
            
        rate = Decimal(item.gst_rate_percent)
        amount = entry.amount
        
        if is_interstate and igst_ledger_id:
            tax_amount = (amount * rate) / Decimal('100.0')
            allocations.append({
                'item_index': idx,
                'ledger_id': igst_ledger_id,
                'is_deemed_positive': is_dp,
                'amount': tax_amount
            })
        elif not is_interstate and cgst_ledger_id and sgst_ledger_id:
            half_rate = rate / Decimal('2.0')
            tax_amount = (amount * half_rate) / Decimal('100.0')
            allocations.append({
                'item_index': idx,
                'ledger_id': cgst_ledger_id,
                'is_deemed_positive': is_dp,
                'amount': tax_amount
            })
            allocations.append({
                'item_index': idx,
                'ledger_id': sgst_ledger_id,
                'is_deemed_positive': is_dp,
                'amount': tax_amount
            })

    return allocations
