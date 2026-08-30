from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import delete
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json

from app.core.database import get_db
from app.core.config import settings
from app.core.permissions import require_permission, get_current_user, require_voucher_read_permission
from app.core.cache import get_cached_response, set_cached_response, clear_company_cache
from app.models.portal_core import User, Module, ApprovalRule, ApprovalRequest, AuditLog, SyncQueue, Company, EinvoiceMetadata, DeletedRecordAudit
from app.models.tally_core import (
    MstVoucherType, TrnVoucher, TrnAccounting, TrnBankAllocation, TrnBill, BillAllocation, MstLedger, MstGroup, TrnInventory, MstStockItem, VoucherAccountingAllocation, GstRegistration, TrnCostCentreAllocation
)

from app.schemas.voucher import (
    VoucherCreate, VoucherResponse, VoucherListResponse,
    ApprovalRuleCreate, ApprovalRuleResponse,
    ApprovalRequestResponse
)
from app.services.gst_service import compute_gst_allocations

router = APIRouter(prefix="/vouchers", tags=["Vouchers & Posting"])

async def log_audit(db: AsyncSession, company_id: int, user_id: int, action: str, entity_type: str, entity_id: int, old_val: dict = None, new_val: dict = None):
    audit = AuditLog(
        company_id=company_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_val,
        new_value=new_val
    )
    db.add(audit)

# --- Voucher Types ---
@router.get("/types")
async def get_voucher_types(
    user: User = Depends(require_voucher_read_permission),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(select(MstVoucherType).where(MstVoucherType.company_id == user.company_id))
    return res.scalars().all()

# --- Voucher Posting Logic ---

async def handle_inventory_posting(db, user, voucher, vtype, req, is_update=False):
    # Reverse existing stock if update
    if is_update:
        # Stock quantities are updated when voucher status is 'confirmed'
        # We need to reverse them before deleting if the old status was 'confirmed'
        if voucher.status == 'confirmed':
            old_inv_stmt = select(TrnInventory).where(TrnInventory.voucher_id == voucher.voucher_id)
            old_inv_res = await db.execute(old_inv_stmt)
            for old_inv in old_inv_res.scalars().all():
                item_res = await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == old_inv.stock_item_id))
                item = item_res.scalars().first()
                if item:
                    qty = float(old_inv.quantity)
                    if old_inv.is_inward:
                        item.closing_qty = float(item.closing_qty or 0) - qty
                    else:
                        item.closing_qty = float(item.closing_qty or 0) + qty
        
        # Delete old child records
        await db.execute(delete(TrnAccounting).where(TrnAccounting.voucher_id == voucher.voucher_id))
        await db.execute(delete(TrnInventory).where(TrnInventory.voucher_id == voucher.voucher_id))
        await db.execute(delete(TrnBill).where(TrnBill.voucher_id == voucher.voucher_id))

    # Process new inventory entries
    tax_ledger_entries = {}
    
    if req.inventory_entries:
        # GST auto-calc
        auto_gst = []
        if req.is_invoice and vtype.parent_type in ['Sales', 'Purchase', 'Credit Note', 'Debit Note']:
            is_sales_type = vtype.parent_type in ['Sales', 'Debit Note'] or vtype.name in ['Sales', 'Debit Note']
            auto_gst = await compute_gst_allocations(
                company_id=user.company_id,
                party_ledger_id=req.party_ledger_id,
                gst_registration_id=req.gst_registration_id,
                inventory_entries=req.inventory_entries,
                db=db,
                is_sales=is_sales_type
            )
            
        for idx, inv_req in enumerate(req.inventory_entries):
            is_inward = True
            if vtype.parent_type in ['Sales', 'Debit Note']:
                is_inward = False
                
            inv = TrnInventory(
                voucher_id=voucher.voucher_id,
                stock_item_id=inv_req.stock_item_id,
                godown_id=inv_req.godown_id,
                batch_id=inv_req.batch_id,
                quantity=inv_req.quantity,
                billed_qty=inv_req.billed_qty or inv_req.quantity,
                rate=inv_req.rate,
                rate_unit_id=inv_req.rate_unit_id,
                amount=inv_req.amount,
                discount_percent=getattr(inv_req, 'discount_percent', Decimal('0.00')),
                discount_amount=getattr(inv_req, 'discount_amount', Decimal('0.00')),
                is_inward=is_inward,
                is_deemed_positive=inv_req.is_deemed_positive,
                flow_type=inv_req.flow_type
            )
            db.add(inv)
            await db.flush()
            
            # Post manual allocations
            if inv_req.accounting_allocations:
                for alloc in inv_req.accounting_allocations:
                    db.add(VoucherAccountingAllocation(
                        stock_entry_id=inv.stock_entry_id,
                        ledger_id=alloc.ledger_id,
                        is_deemed_positive=alloc.is_deemed_positive,
                        amount=alloc.amount
                    ))
                    key = (alloc.ledger_id, alloc.is_deemed_positive)
                    tax_ledger_entries[key] = tax_ledger_entries.get(key, 0) + float(alloc.amount)
            else:
                # Post auto-gst allocations for this item
                item_auto_gst = [g for g in auto_gst if g['item_index'] == idx]
                for g in item_auto_gst:
                    db.add(VoucherAccountingAllocation(
                        stock_entry_id=inv.stock_entry_id,
                        ledger_id=g['ledger_id'],
                        is_deemed_positive=g['is_deemed_positive'],
                        amount=g['amount']
                    ))
                    key = (g['ledger_id'], g['is_deemed_positive'])
                    tax_ledger_entries[key] = tax_ledger_entries.get(key, 0) + float(g['amount'])

            # Update stock balance if confirmed
            if req.status == 'confirmed':
                item_res = await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == inv_req.stock_item_id))
                item = item_res.scalars().first()
                if item:
                    qty = float(inv.quantity)
                    if inv.is_inward:
                        item.closing_qty = float(item.closing_qty or 0) + qty
                    else:
                        item.closing_qty = float(item.closing_qty or 0) - qty

    # Post accounting entries
    for e in req.entries:
        entry = TrnAccounting(
            voucher_id=voucher.voucher_id,
            ledger_id=e.ledger_id,
            cost_center_id=e.cost_center_id,
            debit_amount=e.debit_amount,
            credit_amount=e.credit_amount,
            entry_narration=e.entry_narration,
            forex_currency_id=e.forex_currency_id,
            forex_amount=e.forex_amount,
            exchange_rate_used=e.exchange_rate_used
        )
        db.add(entry)
        await db.flush()
        
        if e.bank_allocations:
            for ba in e.bank_allocations:
                db.add(TrnBankAllocation(
                    entry_id=entry.entry_id,
                    instrument_date=ba.instrument_date,
                    transaction_type=ba.transaction_type,
                    payment_favouring=ba.payment_favouring,
                    instrument_number=ba.instrument_number,
                    amount=ba.amount,
                    transfer_mode=getattr(ba, 'transfer_mode', None),
                    virtual_payment_address=getattr(ba, 'virtual_payment_address', None),
                    cheque_cross_comment=getattr(ba, 'cheque_cross_comment', None),
                    bank_name=getattr(ba, 'bank_name', None),
                    account_number=getattr(ba, 'account_number', None),
                    ifs_code=getattr(ba, 'ifs_code', None),
                    is_connected_payment=getattr(ba, 'is_connected_payment', False)
                ))

        if getattr(e, 'cost_centre_allocations', None):
            for cca in e.cost_centre_allocations:
                db.add(TrnCostCentreAllocation(
                    entry_id=entry.entry_id,
                    cost_centre_id=cca.cost_centre_id,
                    amount=cca.amount,
                    percentage=getattr(cca, 'percentage', None)
                ))

        if getattr(e, 'bill_allocations', None):
            for ba in e.bill_allocations:
                bill = None
                if ba.bill_id:
                    b_res = await db.execute(select(TrnBill).where(TrnBill.bill_id == ba.bill_id, TrnBill.company_id == user.company_id))
                    bill = b_res.scalars().first()
                elif ba.bill_reference:
                    b_res = await db.execute(select(TrnBill).where(
                        TrnBill.company_id == user.company_id,
                        TrnBill.party_ledger_id == e.ledger_id,
                        TrnBill.bill_reference == ba.bill_reference
                    ))
                    bill = b_res.scalars().first()

                norm_type = "Against Ref" if ba.allocation_type in ["Against Ref", "Agst Ref"] else ba.allocation_type

                if norm_type in ['Advance', 'New Ref']:
                    if not bill:
                        vdate = datetime.strptime(req.voucher_date, "%Y-%m-%d").date()
                        b_ref = ba.bill_reference or req.reference_number or voucher.voucher_number
                        bill = TrnBill(
                            company_id=user.company_id,
                            party_ledger_id=e.ledger_id,
                            voucher_id=voucher.voucher_id,
                            bill_reference=b_ref[:50],
                            bill_date=vdate,
                            due_date=vdate,
                            bill_amount=ba.amount,
                            settled_amount=0.00,
                            status="Open"
                        )
                        db.add(bill)
                        await db.flush()
                elif norm_type == 'Against Ref':
                    if bill:
                        bill.settled_amount = float(bill.settled_amount or 0) + float(ba.amount)
                        if float(bill.settled_amount) >= float(bill.bill_amount):
                            bill.status = "Settled"
                        else:
                            bill.status = "Partially Settled"

                db.add(BillAllocation(
                    voucher_entry_id=entry.entry_id,
                    bill_id=bill.bill_id if bill else None,
                    allocation_type=norm_type,
                    amount=ba.amount
                ))
    
    # If req.is_invoice with inventory entries and no manual req.entries, auto-create balanced party & sales/purchase entries
    if req.is_invoice and req.inventory_entries and not req.entries:
        items_total = sum(float(inv.amount) for inv in req.inventory_entries)
        tax_total = sum(amount for (ledger_id, is_dp), amount in tax_ledger_entries.items())
        gross_total = items_total + tax_total
        voucher.total_amount = Decimal(str(gross_total))
        
        is_sales = vtype.parent_type in ['Sales', 'Debit Note'] or vtype.name in ['Sales', 'Debit Note']
        
        # 1. Party ledger entry
        if req.party_ledger_id:
            db.add(TrnAccounting(
                voucher_id=voucher.voucher_id,
                ledger_id=req.party_ledger_id,
                debit_amount=gross_total if is_sales else 0,
                credit_amount=0 if is_sales else gross_total
            ))
            
        # 2. Sales / Purchase account entry
        acct_group_name = 'Sales' if is_sales else 'Purchase'
        acct_res = await db.execute(
            select(MstLedger).join(MstGroup, MstLedger.group_id == MstGroup.group_id)
            .where(MstLedger.company_id == user.company_id, MstGroup.name.ilike(f'%{acct_group_name}%'))
        )
        main_acct_ledger = acct_res.scalars().first()
        if not main_acct_ledger:
            acct_res = await db.execute(
                select(MstLedger).where(MstLedger.company_id == user.company_id, MstLedger.name.ilike(f'%{acct_group_name}%'))
            )
            main_acct_ledger = acct_res.scalars().first()
            
        if main_acct_ledger:
            db.add(TrnAccounting(
                voucher_id=voucher.voucher_id,
                ledger_id=main_acct_ledger.ledger_id,
                debit_amount=0 if is_sales else items_total,
                credit_amount=items_total if is_sales else 0
            ))
    
    # Roll up tax allocations to TrnAccounting
    for (ledger_id, is_dp), amount in tax_ledger_entries.items():
        db.add(TrnAccounting(
            voucher_id=voucher.voucher_id,
            ledger_id=ledger_id,
            debit_amount=amount if is_dp else 0,
            credit_amount=0 if is_dp else amount
        ))
        
    # Auto-create outstanding bill for Sales/Purchase if confirmed and no manual bill allocations provided
    has_manual_allocations = any(getattr(e, 'bill_allocations', None) for e in req.entries)
    if not has_manual_allocations and req.status == 'confirmed' and vtype.parent_type in ['Sales', 'Purchase'] and req.party_ledger_id:
        ledg_query = await db.execute(select(MstLedger).where(MstLedger.ledger_id == req.party_ledger_id))
        ledger = ledg_query.scalars().first()
        if ledger:
            days = ledger.credit_period_days or 0
            vdate = datetime.strptime(req.voucher_date, "%Y-%m-%d").date()
            due = vdate + timedelta(days=days)
            amount = sum([float(e.debit_amount) for e in req.entries if e.ledger_id == ledger.ledger_id])
            if amount == 0:
                amount = sum([float(e.credit_amount) for e in req.entries if e.ledger_id == ledger.ledger_id])
            if amount == 0 and req.inventory_entries:
                amount = float(voucher.total_amount)
                
            if amount > 0:
                db.add(TrnBill(
                    company_id=user.company_id,
                    party_ledger_id=ledger.ledger_id,
                    voucher_id=voucher.voucher_id,
                    bill_reference=req.reference_number or voucher.voucher_number,
                    bill_date=vdate,
                    due_date=due,
                    bill_amount=amount,
                    settled_amount=0.00,
                    status="Open"
                ))

# --- Voucher Endpoints ---

@router.post("", response_model=VoucherResponse, status_code=status.HTTP_201_CREATED)
async def create_voucher(
    req: VoucherCreate,
    response: Response,
    user: User = Depends(require_permission("vouchers", "create")),
    db: AsyncSession = Depends(get_db)
):
    if not req.entries and not req.inventory_entries:
        raise HTTPException(status_code=400, detail="Voucher must have at least one entry.")
        
    total_debits = sum((e.debit_amount for e in req.entries), Decimal('0.00')) if req.entries else Decimal('0.00')
    total_credits = sum((e.credit_amount for e in req.entries), Decimal('0.00')) if req.entries else Decimal('0.00')
    
    if req.entries and total_debits != total_credits:
        raise HTTPException(status_code=400, detail=f"Voucher is unbalanced. Debits: {total_debits}, Credits: {total_credits}")
        
    v_total = total_debits if (req.entries and total_debits > 0) else sum((ie.amount for ie in req.inventory_entries or []), Decimal('0.00'))

    vtype_query = await db.execute(select(MstVoucherType).where(MstVoucherType.voucher_type_id == req.voucher_type_id, MstVoucherType.company_id == user.company_id))
    vtype = vtype_query.scalars().first()
    if not vtype:
        raise HTTPException(status_code=400, detail="Voucher type not found.")
        
    if vtype.numbering_method == "Automatic":
        vnum = f"{vtype.prefix or ''}{vtype.next_number}"
        vtype.next_number += 1
    else:
        vnum = req.reference_number or 'MANUAL'
        
    vdate = datetime.strptime(req.voucher_date, "%Y-%m-%d").date()
        
    # Check Maker-Checker rule threshold
    mod_query = await db.execute(select(Module).where(Module.code == 'vouchers'))
    vouchers_module = mod_query.scalars().first()
    
    matching_rule = None
    if vouchers_module:
        rule_query = await db.execute(
            select(ApprovalRule).where(
                ApprovalRule.company_id == user.company_id,
                ApprovalRule.module_id == vouchers_module.module_id,
                (ApprovalRule.voucher_type_id == None) | (ApprovalRule.voucher_type_id == req.voucher_type_id),
                ApprovalRule.is_active == True
            )
        )
        rules = rule_query.scalars().all()
        for r in rules:
            if r.condition_operator == '>' and total_debits > r.condition_value:
                matching_rule = r
                break
            elif r.condition_operator == '>=' and total_debits >= r.condition_value:
                matching_rule = r
                break
                
    final_status = req.status
    if matching_rule:
        final_status = 'optional'
        
    voucher = TrnVoucher(
        company_id=user.company_id,
        voucher_type_id=req.voucher_type_id,
        voucher_number=vnum,
        voucher_date=vdate,
        reference_number=req.reference_number,
        narration=req.narration,
        total_amount=v_total,
        status=final_status,
        party_ledger_id=req.party_ledger_id,
        is_invoice=req.is_invoice,
        original_voucher_id=req.original_voucher_id,
        gst_registration_id=req.gst_registration_id,
        created_by=user.user_id
    )
    db.add(voucher)
    await db.flush()
    
    await handle_inventory_posting(db, user, voucher, vtype, req)
        
    if matching_rule:
        db.add(ApprovalRequest(rule_id=matching_rule.rule_id, voucher_id=voucher.voucher_id, requested_by=user.user_id, status="Pending"))
        
    await log_audit(db, user.company_id, user.user_id, "CREATE", "Voucher", voucher.voucher_id)
    
    if final_status == 'confirmed':
        sync_item = SyncQueue(company_id=user.company_id, record_type="Voucher", record_id=voucher.voucher_id, action="Create")
        db.add(sync_item)
        
    await db.commit()
    
    if final_status == 'confirmed':
        await db.refresh(sync_item)
        from app.routers.sync import try_push_voucher_realtime
        await try_push_voucher_realtime(voucher.voucher_id, sync_item.sync_id, "Create", db)
    
    final_query = await db.execute(
        select(TrnVoucher)
        .options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bill_allocations).selectinload(BillAllocation.bill),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.accounting_allocations)
        )
        .where(TrnVoucher.voucher_id == voucher.voucher_id)
    )
    
    if matching_rule:
        response.status_code = status.HTTP_202_ACCEPTED
        
    clear_company_cache(user.company_id)
    return final_query.scalars().first()

from sqlalchemy import delete, text

async def build_voucher_snapshot(voucher: TrnVoucher, db: AsyncSession) -> dict:
    vid = voucher.voucher_id
    
    # 1. Fetch current accounting entries with child allocations
    entries_stmt = (
        select(TrnAccounting)
        .options(
            selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnAccounting.bill_allocations),
            selectinload(TrnAccounting.cost_centre_allocations)
        )
        .where(TrnAccounting.voucher_id == vid)
    )
    entries_res = await db.execute(entries_stmt)
    old_entries = entries_res.scalars().all()
    
    entries_data = []
    for e in old_entries:
        entries_data.append({
            "entry_id": e.entry_id,
            "ledger_id": e.ledger_id,
            "cost_center_id": e.cost_center_id,
            "debit_amount": float(e.debit_amount or 0),
            "credit_amount": float(e.credit_amount or 0),
            "entry_narration": e.entry_narration,
            "forex_currency_id": e.forex_currency_id,
            "forex_amount": float(e.forex_amount) if e.forex_amount else None,
            "exchange_rate_used": float(e.exchange_rate_used) if e.exchange_rate_used else None,
            "bank_allocations": [{
                "instrument_date": ba.instrument_date.isoformat() if ba.instrument_date else None,
                "transaction_type": ba.transaction_type,
                "payment_favouring": ba.payment_favouring,
                "instrument_number": ba.instrument_number,
                "amount": float(ba.amount or 0),
                "transfer_mode": ba.transfer_mode,
                "virtual_payment_address": ba.virtual_payment_address,
                "cheque_cross_comment": ba.cheque_cross_comment,
                "bank_name": ba.bank_name,
                "account_number": ba.account_number,
                "ifs_code": ba.ifs_code,
                "is_connected_payment": ba.is_connected_payment
            } for ba in (e.bank_allocations or [])],
            "bill_allocations": [{
                "bill_id": ba.bill_id,
                "allocation_type": ba.allocation_type,
                "amount": float(ba.amount or 0)
            } for ba in (e.bill_allocations or [])],
            "cost_centre_allocations": [{
                "cost_centre_id": cca.cost_centre_id,
                "amount": float(cca.amount or 0),
                "percentage": float(cca.percentage) if cca.percentage else None
            } for cca in (e.cost_centre_allocations or [])]
        })
        
    # 2. Fetch current inventory entries with accounting allocations
    inv_stmt = (
        select(TrnInventory)
        .options(selectinload(TrnInventory.accounting_allocations))
        .where(TrnInventory.voucher_id == vid)
    )
    inv_res = await db.execute(inv_stmt)
    old_invs = inv_res.scalars().all()
    
    inv_data = []
    item_balances = {}
    for inv in old_invs:
        if inv.stock_item_id not in item_balances:
            si_res = await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == inv.stock_item_id))
            si = si_res.scalars().first()
            if si:
                item_balances[inv.stock_item_id] = {
                    "closing_qty": float(si.closing_qty or 0),
                    "closing_value": float(si.closing_value or 0),
                    "closing_rate": float(si.closing_rate or 0)
                }
        inv_data.append({
            "stock_entry_id": inv.stock_entry_id,
            "stock_item_id": inv.stock_item_id,
            "godown_id": inv.godown_id,
            "batch_id": inv.batch_id,
            "quantity": float(inv.quantity or 0),
            "billed_qty": float(inv.billed_qty or 0) if inv.billed_qty else None,
            "rate": float(inv.rate or 0),
            "rate_unit_id": inv.rate_unit_id,
            "amount": float(inv.amount or 0),
            "discount_percent": float(inv.discount_percent or 0),
            "discount_amount": float(inv.discount_amount or 0),
            "is_inward": inv.is_inward,
            "is_deemed_positive": inv.is_deemed_positive,
            "flow_type": inv.flow_type,
            "accounting_allocations": [{
                "ledger_id": aa.ledger_id,
                "is_deemed_positive": aa.is_deemed_positive,
                "amount": float(aa.amount or 0)
            } for aa in (inv.accounting_allocations or [])]
        })
        
    return {
        "voucher_id": voucher.voucher_id,
        "company_id": voucher.company_id,
        "voucher_type_id": voucher.voucher_type_id,
        "voucher_number": str(voucher.voucher_number),
        "voucher_date": voucher.voucher_date.isoformat() if voucher.voucher_date else None,
        "reference_number": voucher.reference_number,
        "narration": voucher.narration,
        "total_amount": float(voucher.total_amount or 0),
        "status": voucher.status,
        "party_ledger_id": voucher.party_ledger_id,
        "is_invoice": voucher.is_invoice,
        "original_voucher_id": voucher.original_voucher_id,
        "gst_registration_id": voucher.gst_registration_id,
        "tally_guid": voucher.tally_guid,
        "tally_alter_id": voucher.tally_alter_id,
        "entries": entries_data,
        "inventory_entries": inv_data,
        "item_balances": item_balances
    }

@router.put("/{voucher_id}", response_model=VoucherResponse)
async def update_voucher(
    voucher_id: int,
    req: VoucherCreate,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    v_query = await db.execute(select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id))
    voucher = v_query.scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
        
    vtype_query = await db.execute(select(MstVoucherType).where(MstVoucherType.voucher_type_id == req.voucher_type_id))
    vtype = vtype_query.scalars().first()

    # Capture pre-alter snapshot BEFORE applying any updates
    snapshot = await build_voucher_snapshot(voucher, db)
    
    voucher.voucher_date = datetime.strptime(req.voucher_date, "%Y-%m-%d").date()
    voucher.reference_number = req.reference_number
    total_debits = sum((e.debit_amount for e in req.entries), Decimal('0.00')) if req.entries else Decimal('0.00')
    voucher.total_amount = total_debits if (req.entries and total_debits > 0) else sum((ie.amount for ie in req.inventory_entries or []), Decimal('0.00'))
    voucher.party_ledger_id = req.party_ledger_id
    voucher.is_invoice = req.is_invoice
    voucher.original_voucher_id = req.original_voucher_id
    voucher.gst_registration_id = req.gst_registration_id
    
    await handle_inventory_posting(db, user, voucher, vtype, req, is_update=True)
    
    await log_audit(db, user.company_id, user.user_id, "UPDATE", "Voucher", voucher.voucher_id)
    
    if voucher.status == 'confirmed':
        sync_item = SyncQueue(
            company_id=user.company_id,
            record_type="Voucher",
            record_id=voucher.voucher_id,
            action="Alter",
            snapshot_data=snapshot
        )
        db.add(sync_item)
        await db.commit()
        await db.refresh(sync_item)
        from app.routers.sync import try_push_voucher_realtime
        await try_push_voucher_realtime(voucher.voucher_id, sync_item.sync_id, "Alter", db)
    else:
        await db.commit()
    
    clear_company_cache(user.company_id)
    final_query = await db.execute(
        select(TrnVoucher)
        .options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bill_allocations).selectinload(BillAllocation.bill),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.accounting_allocations)
        )
        .where(TrnVoucher.voucher_id == voucher.voucher_id)
    )
    return final_query.scalars().first()

@router.post("/{voucher_id}/rollback")
async def rollback_voucher_alter(
    voucher_id: int,
    sync_id: Optional[int] = None,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Rolls back a failed voucher alter operation to its pre-alter snapshot.
    Restores the voucher header, accounting entries, and inventory movements.
    """
    v_stmt = select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id)
    voucher = (await db.execute(v_stmt)).scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
        
    sq_query = select(SyncQueue).where(
        SyncQueue.company_id == user.company_id,
        SyncQueue.record_type == "Voucher",
        SyncQueue.record_id == voucher_id,
        SyncQueue.action == "Alter",
        SyncQueue.snapshot_data != None
    )
    if sync_id:
        sq_query = sq_query.where(SyncQueue.sync_id == sync_id)
    sq_query = sq_query.order_by(SyncQueue.sync_id.desc())
    sync_item = (await db.execute(sq_query)).scalars().first()
    
    if not sync_item or not sync_item.snapshot_data:
        raise HTTPException(status_code=400, detail="No pre-alter snapshot available for this voucher rollback.")
        
    snap = sync_item.snapshot_data
    vid = voucher.voucher_id
    tally_db = settings.TALLY_DATABASE_NAME

    # 1. Reverse CURRENT inventory entries before applying snapshot
    cur_inv_stmt = select(TrnInventory).where(TrnInventory.voucher_id == vid)
    cur_invs = (await db.execute(cur_inv_stmt)).scalars().all()
    for cur_inv in cur_invs:
        si = (await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == cur_inv.stock_item_id))).scalars().first()
        if si:
            q = float(cur_inv.quantity or 0)
            if cur_inv.is_inward:
                si.closing_qty = float(si.closing_qty or 0) - q
            else:
                si.closing_qty = float(si.closing_qty or 0) + q

    # 2. Delete current child records
    await db.execute(text(f"DELETE FROM `{tally_db}`.voucher_accounting_allocations WHERE stock_entry_id IN (SELECT stock_entry_id FROM `{tally_db}`.stock_entries WHERE voucher_id = {vid})"))
    await db.execute(text(f"DELETE FROM `{tally_db}`.stock_entries WHERE voucher_id = {vid}"))
    await db.execute(text(f"DELETE FROM `{tally_db}`.voucher_entry_cost_centres WHERE entry_id IN (SELECT entry_id FROM `{tally_db}`.voucher_entries WHERE voucher_id = {vid})"))
    await db.execute(text(f"DELETE FROM `{tally_db}`.bank_allocations WHERE entry_id IN (SELECT entry_id FROM `{tally_db}`.voucher_entries WHERE voucher_id = {vid})"))
    await db.execute(text(f"DELETE FROM `{tally_db}`.bill_allocations WHERE voucher_entry_id IN (SELECT entry_id FROM `{tally_db}`.voucher_entries WHERE voucher_id = {vid})"))
    await db.execute(text(f"DELETE FROM `{tally_db}`.voucher_entries WHERE voucher_id = {vid}"))
    await db.flush()

    # 3. Restore voucher header
    if snap.get("voucher_date"):
        voucher.voucher_date = datetime.strptime(snap["voucher_date"][:10], "%Y-%m-%d").date()
    voucher.reference_number = snap.get("reference_number")
    voucher.narration = snap.get("narration")
    voucher.total_amount = Decimal(str(snap.get("total_amount", 0)))
    voucher.status = snap.get("status", "confirmed")
    voucher.party_ledger_id = snap.get("party_ledger_id")
    voucher.is_invoice = snap.get("is_invoice", False)

    # 4. Re-insert original accounting entries
    for e_snap in (snap.get("entries") or []):
        entry = TrnAccounting(
            voucher_id=vid,
            ledger_id=e_snap["ledger_id"],
            cost_center_id=e_snap.get("cost_center_id"),
            debit_amount=Decimal(str(e_snap.get("debit_amount", 0))),
            credit_amount=Decimal(str(e_snap.get("credit_amount", 0))),
            entry_narration=e_snap.get("entry_narration"),
            forex_currency_id=e_snap.get("forex_currency_id"),
            forex_amount=Decimal(str(e_snap["forex_amount"])) if e_snap.get("forex_amount") else None,
            exchange_rate_used=Decimal(str(e_snap["exchange_rate_used"])) if e_snap.get("exchange_rate_used") else None
        )
        db.add(entry)
        await db.flush()
        
        for ba in (e_snap.get("bank_allocations") or []):
            db.add(TrnBankAllocation(
                entry_id=entry.entry_id,
                instrument_date=datetime.strptime(ba["instrument_date"][:10], "%Y-%m-%d").date() if ba.get("instrument_date") else None,
                transaction_type=ba.get("transaction_type", "Others"),
                payment_favouring=ba.get("payment_favouring"),
                instrument_number=ba.get("instrument_number"),
                amount=Decimal(str(ba.get("amount", 0))),
                transfer_mode=ba.get("transfer_mode"),
                virtual_payment_address=ba.get("virtual_payment_address"),
                cheque_cross_comment=ba.get("cheque_cross_comment"),
                bank_name=ba.get("bank_name"),
                account_number=ba.get("account_number"),
                ifs_code=ba.get("ifs_code"),
                is_connected_payment=ba.get("is_connected_payment", False)
            ))
            
        for bill_a in (e_snap.get("bill_allocations") or []):
            db.add(BillAllocation(
                voucher_entry_id=entry.entry_id,
                bill_id=bill_a.get("bill_id"),
                allocation_type=bill_a.get("allocation_type", "Against Ref"),
                amount=Decimal(str(bill_a.get("amount", 0)))
            ))
            
        for cca in (e_snap.get("cost_centre_allocations") or []):
            db.add(TrnCostCentreAllocation(
                entry_id=entry.entry_id,
                cost_centre_id=cca["cost_centre_id"],
                amount=Decimal(str(cca.get("amount", 0))),
                percentage=Decimal(str(cca["percentage"])) if cca.get("percentage") else None
            ))

    # 5. Re-insert original inventory entries and restore stock closing balances
    for inv_snap in (snap.get("inventory_entries") or []):
        inv = TrnInventory(
            voucher_id=vid,
            stock_item_id=inv_snap["stock_item_id"],
            godown_id=inv_snap.get("godown_id"),
            batch_id=inv_snap.get("batch_id"),
            quantity=Decimal(str(inv_snap.get("quantity", 0))),
            billed_qty=Decimal(str(inv_snap["billed_qty"])) if inv_snap.get("billed_qty") else None,
            rate=Decimal(str(inv_snap.get("rate", 0))),
            rate_unit_id=inv_snap.get("rate_unit_id"),
            amount=Decimal(str(inv_snap.get("amount", 0))),
            discount_percent=Decimal(str(inv_snap.get("discount_percent", 0))),
            discount_amount=Decimal(str(inv_snap.get("discount_amount", 0))),
            is_inward=inv_snap.get("is_inward", True),
            is_deemed_positive=inv_snap.get("is_deemed_positive", True),
            flow_type=inv_snap.get("flow_type")
        )
        db.add(inv)
        await db.flush()
        
        for aa in (inv_snap.get("accounting_allocations") or []):
            db.add(VoucherAccountingAllocation(
                stock_entry_id=inv.stock_entry_id,
                ledger_id=aa["ledger_id"],
                is_deemed_positive=aa["is_deemed_positive"],
                amount=Decimal(str(aa.get("amount", 0)))
            ))
            
        si = (await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == inv_snap["stock_item_id"]))).scalars().first()
        if si:
            q = float(inv_snap.get("quantity", 0))
            if inv_snap.get("is_inward", True):
                si.closing_qty = float(si.closing_qty or 0) + q
            else:
                si.closing_qty = float(si.closing_qty or 0) - q

    # Mark SyncQueue status as ROLLED_BACK
    sync_item.status = "ROLLED_BACK"
    sync_item.error_message = f"Rolled back to pre-alter snapshot by user #{user.user_id}"
    
    await log_audit(db, user.company_id, user.user_id, "ROLLBACK", "Voucher", voucher_id)
    await db.commit()
    clear_company_cache(user.company_id)

    res = await db.execute(
        select(TrnVoucher)
        .options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bill_allocations).selectinload(BillAllocation.bill),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.accounting_allocations)
        )
        .where(TrnVoucher.voucher_id == vid)
    )
    return res.scalars().first()

@router.post("/{voucher_id}/retry-sync")
async def retry_voucher_sync(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Retries pushing an altered or created voucher to Tally Prime.
    """
    v_stmt = select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id)
    voucher = (await db.execute(v_stmt)).scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
        
    sq_query = (
        select(SyncQueue)
        .where(
            SyncQueue.company_id == user.company_id,
            SyncQueue.record_type == "Voucher",
            SyncQueue.record_id == voucher_id
        )
        .order_by(SyncQueue.sync_id.desc())
    )
    sync_item = (await db.execute(sq_query)).scalars().first()
    if not sync_item:
        sync_item = SyncQueue(company_id=user.company_id, record_type="Voucher", record_id=voucher_id, action="Alter")
        db.add(sync_item)
        await db.commit()
        await db.refresh(sync_item)
        
    from app.routers.sync import try_push_voucher_realtime
    tally_ok, tally_status, tally_err = await try_push_voucher_realtime(voucher_id, sync_item.sync_id, sync_item.action, db)
    return {
        "voucher_id": voucher_id,
        "sync_id": sync_item.sync_id,
        "tally_synced": tally_ok,
        "tally_status": tally_status,
        "tally_message": tally_err
    }

@router.delete("/{voucher_id}")
async def delete_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    v_query = await db.execute(select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id))
    voucher = v_query.scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
        
    # Reverse stock if confirmed
    if voucher.status == 'confirmed':
        old_inv_stmt = select(TrnInventory).where(TrnInventory.voucher_id == voucher.voucher_id)
        old_inv_res = await db.execute(old_inv_stmt)
        for old_inv in old_inv_res.scalars().all():
            item_res = await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == old_inv.stock_item_id))
            item = item_res.scalars().first()
            if item:
                qty = float(old_inv.quantity)
                if old_inv.is_inward:
                    item.closing_qty = float(item.closing_qty or 0) - qty
                else:
                    item.closing_qty = float(item.closing_qty or 0) + qty
                    
    # Record in DeletedRecordAudit for audit trail & to block zombie resurrection during inbound sync
    snapshot = {
        "voucher_id": voucher.voucher_id,
        "company_id": voucher.company_id,
        "voucher_type_id": voucher.voucher_type_id,
        "voucher_number": str(voucher.voucher_number),
        "voucher_date": voucher.voucher_date.isoformat() if voucher.voucher_date else None,
        "reference_number": voucher.reference_number,
        "narration": voucher.narration,
        "total_amount": float(voucher.total_amount or 0),
        "status": voucher.status,
        "tally_guid": voucher.tally_guid,
        "tally_alter_id": voucher.tally_alter_id
    }
    
    del_audit = DeletedRecordAudit(
        company_id=user.company_id,
        entity_type="Voucher",
        record_id=voucher_id,
        tally_guid=voucher.tally_guid or f"MYTALLY-VCH-{voucher_id}",
        entity_identifier=f"Voucher #{voucher.voucher_number}",
        deleted_by_user_id=user.user_id,
        tally_sync_status="PENDING",
        snapshot_data=snapshot
    )
    db.add(del_audit)
    
    sync_item = SyncQueue(company_id=user.company_id, record_type="Voucher", record_id=voucher_id, action="Delete")
    db.add(sync_item)
    await db.flush()

    from app.routers.sync import try_push_voucher_realtime
    tally_ok, tally_status, tally_err = await try_push_voucher_realtime(voucher_id, sync_item.sync_id, "Delete", db)

    await db.delete(voucher)
    await log_audit(db, user.company_id, user.user_id, "DELETE", "Voucher", voucher_id)
    await db.commit()
    clear_company_cache(user.company_id)
    return {
        "detail": "Voucher deleted successfully in MyTally.",
        "tally_synced": tally_ok,
        "tally_status": tally_status,
        "tally_message": tally_err
    }

@router.post("/{voucher_id}/cancel")
async def cancel_voucher(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancels a voucher in MyTally and pushes <ISCANCELLED>Yes</ISCANCELLED> to TallyPrime.
    Reverses all inventory stock movements and zeros out financial impact while retaining sequence integrity.
    """
    v_query = await db.execute(select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id))
    voucher = v_query.scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
        
    old_status = voucher.status
    if old_status == 'cancelled':
        return {"detail": "Voucher is already cancelled", "tally_synced": True, "tally_status": "SUCCESS", "tally_message": None}
        
    # Reverse stock if confirmed
    if old_status == 'confirmed':
        inv_stmt = select(TrnInventory).where(TrnInventory.voucher_id == voucher.voucher_id)
        inv_res = await db.execute(inv_stmt)
        for inv in inv_res.scalars().all():
            item_res = await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == inv.stock_item_id))
            item = item_res.scalars().first()
            if item:
                qty = float(inv.quantity)
                if inv.is_inward:
                    item.closing_qty = float(item.closing_qty or 0) - qty
                else:
                    item.closing_qty = float(item.closing_qty or 0) + qty
                    
    voucher.status = 'cancelled'
    voucher.is_cancelled = True
    
    sync_item = SyncQueue(company_id=user.company_id, record_type="Voucher", record_id=voucher_id, action="Cancel")
    db.add(sync_item)
    await log_audit(db, user.company_id, user.user_id, "CANCEL", "Voucher", voucher_id)
    await db.commit()
    await db.refresh(sync_item)
    
    from app.routers.sync import try_push_voucher_realtime
    tally_ok, tally_status, tally_err = await try_push_voucher_realtime(voucher_id, sync_item.sync_id, "Cancel", db)
    clear_company_cache(user.company_id)
    return {
        "detail": "Voucher cancelled successfully in MyTally.",
        "tally_synced": tally_ok,
        "tally_status": tally_status,
        "tally_message": tally_err
    }

@router.patch("/{voucher_id}/status")
async def update_voucher_status(
    voucher_id: int,
    status_val: str,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    if status_val not in ['draft', 'optional', 'confirmed', 'cancelled']:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    v_query = await db.execute(select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id))
    voucher = v_query.scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")
        
    old_status = voucher.status
    if old_status == status_val:
        return {"detail": "Status unchanged"}
        
    # If transitioning to/from confirmed, adjust stock
    if old_status == 'confirmed' or status_val == 'confirmed':
        inv_stmt = select(TrnInventory).where(TrnInventory.voucher_id == voucher.voucher_id)
        inv_res = await db.execute(inv_stmt)
        for inv in inv_res.scalars().all():
            item_res = await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == inv.stock_item_id))
            item = item_res.scalars().first()
            if item:
                qty = float(inv.quantity)
                # To confirmed = apply stock
                if status_val == 'confirmed':
                    if inv.is_inward: item.closing_qty = float(item.closing_qty or 0) + qty
                    else: item.closing_qty = float(item.closing_qty or 0) - qty
                # From confirmed = reverse stock
                else:
                    if inv.is_inward: item.closing_qty = float(item.closing_qty or 0) - qty
                    else: item.closing_qty = float(item.closing_qty or 0) + qty
                    
    voucher.status = status_val
    voucher.is_cancelled = (status_val == 'cancelled')
    
    action_type = "Cancel" if status_val == 'cancelled' else "Alter"
    sync_item = SyncQueue(company_id=user.company_id, record_type="Voucher", record_id=voucher_id, action=action_type)
    db.add(sync_item)
    await log_audit(db, user.company_id, user.user_id, "STATUS_UPDATE", "Voucher", voucher_id)
    await db.commit()
    await db.refresh(sync_item)
    
    from app.routers.sync import try_push_voucher_realtime
    await try_push_voucher_realtime(voucher_id, sync_item.sync_id, action_type, db)
    clear_company_cache(user.company_id)
    return {"detail": f"Status updated to {status_val}"}

def _resolve_party_and_amount(entries):
    if not entries: return "Cash Account", 0.0, None
    primary_entry = entries[0]
    max_score = -100
    sales_purchase_sum = 0.0
    has_sales_purchase = False

    for entry in entries:
        ledger = getattr(entry, "ledger", None)
        if not ledger: continue
        group = getattr(ledger, "group", None)
        gname = (getattr(group, "name", "") or "").lower() if group else ""
        lname = (getattr(ledger, "name", "") or "").lower()

        if "sales accounts" in gname or "purchase accounts" in gname or "sales" in gname or "purchase" in gname:
            if "tax" not in lname and "duty" not in lname and "round" not in lname and "discount" not in lname:
                damt = float(entry.debit_amount or 0)
                camt = float(entry.credit_amount or 0)
                sales_purchase_sum += damt if damt > 0 else camt
                has_sales_purchase = True

        score = 0
        if "debtors" in gname or "creditors" in gname: score = 10
        elif "bank" in gname or "cash" in gname: score = 5
        elif "sales" in gname or "purchase" in gname or "tax" in gname or "duty" in gname or "round" in lname: score = -10
        else: score = 1

        if score > max_score:
            max_score = score
            primary_entry = entry

    ledger = getattr(primary_entry, "ledger", None)
    party_name = getattr(ledger, "name", "Cash Account") if ledger else "Cash Account"
    party_ledger_id = getattr(primary_entry, "ledger_id", None)
    debit = float(primary_entry.debit_amount or 0)
    credit = float(primary_entry.credit_amount or 0)
    party_net_amount = debit if debit > 0 else credit

    gross_amount = sales_purchase_sum if (has_sales_purchase and sales_purchase_sum > 0) else party_net_amount
    return party_name, abs(gross_amount), party_ledger_id

@router.get("", response_model=List[VoucherListResponse])
async def get_vouchers(
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    date: Optional[str] = None,
    ledger_id: Optional[int] = None,
    party_name: Optional[str] = None,
    voucher_type: Optional[str] = None,
    user: User = Depends(require_voucher_read_permission),
    db: AsyncSession = Depends(get_db)
):
    cache_key = f"vouchers_list_{status}_{from_date}_{to_date}_{date}_{ledger_id}_{party_name}_{voucher_type}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None: return cached

    stmt = select(TrnVoucher).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
    ).where(TrnVoucher.company_id == user.company_id)

    if status: stmt = stmt.where(TrnVoucher.status == status)
    if date: stmt = stmt.where(TrnVoucher.voucher_date == datetime.strptime(date, "%Y-%m-%d").date())
    if from_date: stmt = stmt.where(TrnVoucher.voucher_date >= datetime.strptime(from_date, "%Y-%m-%d").date())
    if to_date: stmt = stmt.where(TrnVoucher.voucher_date <= datetime.strptime(to_date, "%Y-%m-%d").date())
    if voucher_type: stmt = stmt.join(MstVoucherType).where(MstVoucherType.name == voucher_type)
    if ledger_id: stmt = stmt.join(TrnAccounting).where(TrnAccounting.ledger_id == ledger_id)

    stmt = stmt.order_by(TrnVoucher.voucher_date.desc(), TrnVoucher.voucher_id.desc())
    res = await db.execute(stmt)
    vouchers = res.scalars().all()

    result = []
    for v in vouchers:
        resolved_party, amount, _ = _resolve_party_and_amount(v.entries)
        if party_name and party_name.lower() not in resolved_party.lower(): continue

        result.append({
            "voucher_id": v.voucher_id,
            "date": str(v.voucher_date),
            "voucher_type": v.voucher_type.name if v.voucher_type else "Unknown",
            "voucher_number": v.voucher_number,
            "reference_number": v.reference_number,
            "narration": v.narration,
            "party_name": resolved_party,
            "amount": amount,
            "total_amount": float(v.total_amount or 0),
        })

    set_cached_response(user.company_id, cache_key, result)
    return result

@router.get("/{voucher_id}")
async def get_voucher_detail(
    voucher_id: int,
    user: User = Depends(require_voucher_read_permission),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TrnVoucher).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.cost_centre_allocations).selectinload(TrnCostCentreAllocation.cost_centre),
        selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.stock_item).selectinload(MstStockItem.unit)
    ).where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == user.company_id)
    
    res = await db.execute(stmt)
    voucher = res.scalars().first()
    if not voucher: raise HTTPException(status_code=404, detail="Voucher not found")

    party_name, amount, party_ledger_id = _resolve_party_and_amount(voucher.entries)
    if voucher.party_ledger_id:
        party_ledger_id = voucher.party_ledger_id

    entries = []
    for entry in voucher.entries:
        ledger_name = entry.ledger.name if entry.ledger else "Unknown"
        debit = float(entry.debit_amount or 0)
        credit = float(entry.credit_amount or 0)
        
        bank_allocs = []
        if entry.bank_allocations:
            for ba in entry.bank_allocations:
                bank_allocs.append({
                    "allocation_id": ba.allocation_id,
                    "instrument_date": str(ba.instrument_date) if ba.instrument_date else None,
                    "transaction_type": ba.transaction_type,
                    "payment_favouring": ba.payment_favouring,
                    "instrument_number": ba.instrument_number,
                    "amount": float(ba.amount or 0),
                    "transfer_mode": ba.transfer_mode,
                    "virtual_payment_address": ba.virtual_payment_address,
                    "cheque_cross_comment": ba.cheque_cross_comment,
                    "bank_name": ba.bank_name,
                    "account_number": ba.account_number,
                    "ifs_code": ba.ifs_code,
                    "is_connected_payment": ba.is_connected_payment,
                })

        entries.append({
            "entry_id": entry.entry_id,
            "ledger_id": entry.ledger_id,
            "ledger_name": ledger_name,
            "amount": debit if debit > 0 else credit,
            "debit_amount": debit,
            "credit_amount": credit,
            "entry_type": "Debit" if debit > 0 else "Credit",
            "cost_center_id": entry.cost_center_id,
            "bank_allocations": bank_allocs,
            "cost_centre_allocations": [
                {
                    "id": cca.id,
                    "cost_centre_id": cca.cost_centre_id,
                    "cost_centre_name": cca.cost_centre.name if getattr(cca, 'cost_centre', None) and cca.cost_centre else f"Cost Centre #{cca.cost_centre_id}",
                    "amount": float(cca.amount or 0),
                    "percentage": float(cca.percentage) if cca.percentage is not None else None
                } for cca in getattr(entry, 'cost_centre_allocations', []) or []
            ]
        })

    # Calculate fallback voucher-level tax rate from accounting tax ledgers if item rate is not set
    total_tax_amt = sum(
        float(e.credit_amount or e.debit_amount or 0)
        for e in voucher.entries
        if e.ledger and any(t in e.ledger.name.upper() for t in ["CGST", "SGST", "IGST", "GST", "TAX", "DUTY", "DUTIES"])
    )
    total_inv_amt = sum(float(inv.amount or 0) for inv in voucher.inventory_entries)
    fallback_gst_rate = round((total_tax_amt / total_inv_amt) * 100, 2) if total_inv_amt > 0 and total_tax_amt > 0 else 0.0

    inventory = []
    inventory_entries = []
    for inv in voucher.inventory_entries:
        item_name = inv.stock_item.name if inv.stock_item else "Unknown Item"
        uom_sym = inv.stock_item.unit.symbol if inv.stock_item and inv.stock_item.unit else "PCS"
        qty = float(inv.quantity or 0)
        rate = float(inv.rate or 0)
        disc_pct = float(inv.discount_percent or 0)
        amt = float(inv.amount or 0)

        # GST Rate from stock item or fallback from invoice tax ledger split
        item_gst_rate = float(inv.stock_item.gst_rate_percent) if inv.stock_item and inv.stock_item.gst_rate_percent is not None and float(inv.stock_item.gst_rate_percent) > 0 else fallback_gst_rate
        item_hsn = inv.stock_item.hsn_code if inv.stock_item else ""

        # Rate Inclusive of Tax (e.g. 68.64 with 18% GST -> 81.00)
        rate_incl_tax = round(rate * (1.0 + (item_gst_rate / 100.0)), 2) if item_gst_rate > 0 else rate

        inv_dict = {
            "stock_entry_id": inv.stock_entry_id,
            "stock_item_id": inv.stock_item_id,
            "item": item_name,
            "stock_item_name": item_name,
            "quantity": qty,
            "rate": rate,
            "gst_rate": item_gst_rate,
            "gstRate": item_gst_rate,
            "gst_hsn_code": item_hsn,
            "gstHsnCode": item_hsn,
            "hsn_code": item_hsn,
            "rate_incl_tax": rate_incl_tax,
            "rateInclTax": rate_incl_tax,
            "discount_percent": disc_pct,
            "discount_amount": float(inv.discount_amount or 0),
            "uom": uom_sym,
            "amount": amt,
            "godown_id": inv.godown_id,
            "batch_id": inv.batch_id,
        }
        inventory.append(inv_dict)
        inventory_entries.append(inv_dict)

    # Check sync queue status for this voucher
    sq_stmt = (
        select(SyncQueue)
        .where(
            SyncQueue.company_id == user.company_id,
            SyncQueue.record_type == "Voucher",
            SyncQueue.record_id == voucher_id
        )
        .order_by(SyncQueue.sync_id.desc())
    )
    latest_sync = (await db.execute(sq_stmt)).scalars().first()
    
    sync_status = latest_sync.status if latest_sync else "SUCCESS"
    sync_error = latest_sync.error_message if latest_sync else None
    can_rollback = bool(latest_sync and latest_sync.snapshot_data and latest_sync.status in ["FAILED", "EXCEPTION"])
    sync_id = latest_sync.sync_id if latest_sync else None

    output = {
        "voucher_id": voucher.voucher_id,
        "date": str(voucher.voucher_date),
        "voucher_date": str(voucher.voucher_date),
        "voucher_type": voucher.voucher_type.name if voucher.voucher_type else "Unknown",
        "voucher_type_id": voucher.voucher_type_id,
        "voucher_number": voucher.voucher_number,
        "reference_number": voucher.reference_number,
        "narration": voucher.narration,
        "status": voucher.status,
        "party_name": party_name,
        "party_ledger_id": party_ledger_id,
        "original_voucher_id": voucher.original_voucher_id,
        "is_invoice": voucher.is_invoice,
        "amount": amount,
        "total_amount": float(voucher.total_amount or 0),
        "entries": entries,
        "accounts": entries,
        "inventory": inventory,
        "inventory_entries": inventory_entries,
        "is_inventory_voucher": len(inventory) > 0,
        "sync_status": sync_status,
        "tally_error_message": sync_error,
        "can_rollback": can_rollback,
        "sync_id": sync_id
    }
    return output
