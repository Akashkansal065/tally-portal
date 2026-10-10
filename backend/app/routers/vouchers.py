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
from app.core.datetime_utils import to_ist_iso, get_current_fy_start, is_historical_period
from app.core.permissions import require_permission, get_current_user, require_voucher_read_permission, get_user_allowed_voucher_type_ids
from app.core.cache import get_cached_response, set_cached_response, clear_company_cache
from app.core.pagination import PaginationParams, apply_pagination_headers
from app.models.portal_core import User, Module, ApprovalRule, ApprovalRequest, AuditLog, SyncQueue, Company, EinvoiceMetadata, DeletedRecordAudit
from app.models.tally_core import MstGodown, Batch, TrnAttendance, TrnPayHead, MstPayHead, MstAttendanceType, MstCostCentre
from app.models.tally_core import (
    MstVoucherType, TrnVoucher, TrnAccounting, TrnBankAllocation, TrnBill, BillAllocation, MstLedger, MstGroup, TrnInventory, MstStockItem, VoucherAccountingAllocation, GstRegistration, TrnCostCentreAllocation
)

from app.schemas.voucher import (
    VoucherCreate, VoucherResponse, VoucherListResponse,
    ApprovalRuleCreate, ApprovalRuleResponse,
    ApprovalRequestResponse
)
from app.services.gst_service import compute_gst_allocations
from app.services.voucher_config import auto_bill_reference, configuration_setting
from app.services.voucher_kinds import stock_leaves, is_sales_side, is_physical_stock, is_attendance, is_payroll

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
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    cache_key = f"voucher_types_{user.company_id}"
    if allowed_ids is not None:
        cache_key += f"_user_{user.user_id}"

    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    stmt = select(MstVoucherType).where(MstVoucherType.company_id == user.company_id)
    if allowed_ids is not None:
        stmt = stmt.where(MstVoucherType.voucher_type_id.in_(allowed_ids))
    res = await db.execute(stmt)
    vtypes = res.scalars().all()
    result = [{c.name: getattr(vt, c.name) for c in vt.__table__.columns} for vt in vtypes]
    set_cached_response(user.company_id, cache_key, result, ttl_seconds=7200) # 2 hours
    return result

@router.get("/payroll-masters")
async def get_payroll_masters(
    user: User = Depends(require_voucher_read_permission),
    db: AsyncSession = Depends(get_db)
):
    """What an Attendance or Payroll voucher is built from, as read from Tally: employees (cost centres marked
    for payroll), attendance types, and pay heads (ledgers with a pay type)."""
    employees = (await db.execute(select(MstCostCentre.name).where(
        MstCostCentre.company_id == user.company_id, MstCostCentre.for_payroll == True).order_by(MstCostCentre.name))).scalars().all()  # noqa: E712
    attendance_types = (await db.execute(select(MstAttendanceType.name, MstAttendanceType.type_of_attendance).where(
        MstAttendanceType.company_id == user.company_id).order_by(MstAttendanceType.name))).all()
    pay_heads = (await db.execute(select(MstPayHead.name, MstPayHead.pay_head_type).where(
        MstPayHead.company_id == user.company_id).order_by(MstPayHead.name))).all()
    return {
        "employees": list(employees),
        "attendance_types": [{"name": n, "kind": k} for n, k in attendance_types],
        "pay_heads": [{"name": n, "pay_type": t, "is_deduction": "deduction" in (t or "").lower()} for n, t in pay_heads],
    }


# --- Voucher Posting Logic ---

async def _voucher_item_ids(db, voucher_id) -> set:
    return set((await db.execute(select(TrnInventory.stock_item_id).where(TrnInventory.voucher_id == voucher_id))).scalars().all())


async def handle_inventory_posting(db, user, voucher, vtype, req, is_update=False, previous_reference=None):
    from app.services.stock_counts import rebalance_counted_items
    # Items whose stock this posting touches; any of them covered by a Physical Stock count is re-derived below
    touched_items = await _voucher_item_ids(db, voucher.voucher_id) if is_update else set()
    touched_items |= {ie.stock_item_id for ie in (req.inventory_entries or [])}
    # The bill this voucher already raised for its party: an edit keeps its name
    previous_bill = None
    # Reverse existing stock if update
    if is_update:
        previous_bill = (await db.execute(select(TrnBill.bill_reference).where(
            TrnBill.voucher_id == voucher.voucher_id, TrnBill.party_ledger_id == voucher.party_ledger_id))).scalars().first()
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
            is_sales_type = stock_leaves(vtype)
            auto_gst = await compute_gst_allocations(
                company_id=user.company_id,
                party_ledger_id=req.party_ledger_id,
                gst_registration_id=req.gst_registration_id,
                inventory_entries=req.inventory_entries,
                db=db,
                is_sales=is_sales_type
            )
            
        for idx, inv_req in enumerate(req.inventory_entries):
            is_inward = not stock_leaves(vtype)
            if inv_req.flow_type:
                # Stock Journal: what is produced arrives, what is consumed leaves
                is_inward = inv_req.flow_type == 'destination'

            # A godown / batch must be this company's (and the batch this item's)
            if inv_req.godown_id is not None:
                ok = (await db.execute(select(MstGodown.godown_id).where(
                    MstGodown.godown_id == inv_req.godown_id, MstGodown.company_id == user.company_id))).scalar()
                if not ok:
                    raise HTTPException(status_code=400, detail="Godown not found.")
            if inv_req.batch_id is not None:
                ok = (await db.execute(select(Batch.batch_id).where(
                    Batch.batch_id == inv_req.batch_id, Batch.company_id == user.company_id,
                    Batch.stock_item_id == inv_req.stock_item_id))).scalar()
                if not ok:
                    raise HTTPException(status_code=400, detail="That batch isn't for this item.")

            counted_qty = None
            if is_physical_stock(vtype):
                # A stock count: the line becomes the movement that brings the books to the counted figure
                counted_item = (await db.execute(select(MstStockItem).where(
                    MstStockItem.stock_item_id == inv_req.stock_item_id, MstStockItem.company_id == user.company_id))).scalars().first()
                if not counted_item:
                    raise HTTPException(status_code=400, detail="Stock item not found.")
                counted_qty = Decimal(str(inv_req.quantity))
                difference = counted_qty - Decimal(str(counted_item.closing_qty or 0))
                is_inward = difference >= 0
                inv_req.quantity = abs(difference)

            inv = TrnInventory(
                voucher_id=voucher.voucher_id,
                stock_item_id=inv_req.stock_item_id,
                godown_id=inv_req.godown_id,
                batch_id=inv_req.batch_id,
                quantity=inv_req.quantity,
                actual_quantity=counted_qty,
                billed_qty=inv_req.billed_qty or inv_req.quantity,
                rate=inv_req.rate,
                rate_unit_id=inv_req.rate_unit_id,
                amount=inv_req.amount,
                discount_percent=getattr(inv_req, 'discount_percent', Decimal('0.00')),
                discount_amount=getattr(inv_req, 'discount_amount', Decimal('0.00')),
                is_inward=is_inward,
                is_deemed_positive=is_inward if (inv_req.flow_type or counted_qty is not None) else inv_req.is_deemed_positive,
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

    await db.flush()
    await rebalance_counted_items(db, user.company_id, touched_items)

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
        
        # The party is debited when stock leaves; the item lines post to a sales or a purchase ledger by
        # which side the voucher is on (see voucher_kinds)
        is_sales = stock_leaves(vtype)
        
        # 1. Party ledger entry
        if req.party_ledger_id:
            db.add(TrnAccounting(
                voucher_id=voucher.voucher_id,
                ledger_id=req.party_ledger_id,
                debit_amount=gross_total if is_sales else 0,
                credit_amount=0 if is_sales else gross_total
            ))
            
        # 2. Sales / Purchase account entry
        acct_group_name = 'Sales' if is_sales_side(vtype) else 'Purchase'
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
                    bill_reference=auto_bill_reference(
                        voucher.voucher_number, req.reference_number,
                        await configuration_setting(db, vtype, "use_vch_no_as_bill_ref"),
                        previous_bill, previous_reference)[:50],
                    bill_date=vdate,
                    due_date=due,
                    bill_amount=amount,
                    settled_amount=0.00,
                    status="Open"
                ))

def _inventory_total(inventory_entries) -> Decimal:
    """Value of the item lines. A Stock Journal counts what it produces (or, with nothing produced, what it
    consumes), not both sides added together."""
    lines = inventory_entries or []
    for flow in ("destination", "source"):  # (a Physical Stock count carries no amounts and totals 0)
        side = [ie.amount for ie in lines if ie.flow_type == flow]
        if side:
            return sum(side, Decimal('0.00'))
    return sum((ie.amount for ie in lines), Decimal('0.00'))


async def post_payroll_lines(db: AsyncSession, user: User, voucher: TrnVoucher, vtype, req) -> None:
    """
    Stores the lines of an Attendance or Payroll voucher, replacing any it had.
    A Payroll voucher sent without ledger lines gets them here: each pay head ledger is debited for its
    earnings (or credited for its deductions) and the payable ledger named as the party takes the net.
    Pay head amounts are kept signed the way Tally keeps them: an earning negative, a deduction positive.
    """
    await db.execute(delete(TrnAttendance).where(TrnAttendance.voucher_id == voucher.voucher_id))
    await db.execute(delete(TrnPayHead).where(TrnPayHead.voucher_id == voucher.voucher_id))

    if req.attendance_entries:
        if not is_attendance(vtype):
            raise HTTPException(status_code=400, detail="Attendance lines belong on an Attendance voucher.")
        for line in req.attendance_entries:
            if not line.employee_name.strip() or not line.attendance_type.strip():
                raise HTTPException(status_code=400, detail="Each attendance line needs an employee and an attendance type.")
            db.add(TrnAttendance(voucher_id=voucher.voucher_id, employee_name=line.employee_name.strip(),
                                 attendancetype_name=line.attendance_type.strip(), time_value=line.value, type_value=line.value))

    if req.payroll_entries:
        if not is_payroll(vtype):
            raise HTTPException(status_code=400, detail="Pay head lines belong on a Payroll voucher.")
        if not req.entries and not req.party_ledger_id:
            raise HTTPException(status_code=400, detail="Choose the ledger the salary is payable to (for example Salary Payable).")
        head_types = dict((await db.execute(select(MstPayHead.name, MstPayHead.pay_head_type).where(MstPayHead.company_id == user.company_id))).all())
        by_ledger: dict = {}
        for line in req.payroll_entries:
            head_name = line.pay_head_name.strip()
            ledger = (await db.execute(select(MstLedger).where(MstLedger.company_id == user.company_id, MstLedger.name == head_name))).scalars().first()
            if not ledger:
                raise HTTPException(status_code=400, detail=f"Pay head '{head_name}' has no ledger of that name.")
            is_deduction = "deduction" in (head_types.get(head_name) or "").lower()
            signed = abs(line.amount) if is_deduction else -abs(line.amount)
            db.add(TrnPayHead(voucher_id=voucher.voucher_id, category=(line.category or "Primary Cost Category").strip(),
                              employee_name=line.employee_name.strip(), payhead_name=head_name, amount=signed))
            by_ledger[ledger.ledger_id] = by_ledger.get(ledger.ledger_id, Decimal("0")) + signed
        if not req.entries:
            net = Decimal("0")
            for ledger_id, signed in by_ledger.items():
                db.add(TrnAccounting(voucher_id=voucher.voucher_id, ledger_id=ledger_id,
                                     debit_amount=-signed if signed < 0 else 0, credit_amount=signed if signed > 0 else 0))
                net += -signed
            db.add(TrnAccounting(voucher_id=voucher.voucher_id, ledger_id=req.party_ledger_id,
                                 debit_amount=-net if net < 0 else 0, credit_amount=net if net > 0 else 0))
            voucher.total_amount = sum((-v for v in by_ledger.values() if v < 0), Decimal("0"))
    await db.flush()


async def payroll_lines_of(db: AsyncSession, voucher_id: int) -> dict:
    """The attendance and pay head lines of a voucher, in the shape they are sent in (amounts positive)."""
    attendance = (await db.execute(select(TrnAttendance).where(TrnAttendance.voucher_id == voucher_id).order_by(TrnAttendance.id))).scalars().all()
    pay = (await db.execute(select(TrnPayHead).where(TrnPayHead.voucher_id == voucher_id).order_by(TrnPayHead.id))).scalars().all()
    return {
        "attendance_entries": [{"employee_name": a.employee_name, "attendance_type": a.attendancetype_name,
                                "value": float(a.time_value or 0)} for a in attendance],
        "payroll_entries": [{"employee_name": p.employee_name, "pay_head_name": p.payhead_name, "category": p.category,
                             "amount": float(abs(p.amount or 0)), "is_deduction": (p.amount or 0) > 0} for p in pay],
    }


# --- Tally push ---

def tally_voucher_ident(voucher: TrnVoucher, vtype_name: str) -> dict:
    """What addresses this voucher in Tally, kept on a queued delete for when the app's copy is gone."""
    from app.routers.sync import voucher_remote_id
    return {
        "company_id": voucher.company_id,
        "remote_id": voucher_remote_id(voucher),
        "master_id": voucher.tally_master_id,
        "guid": voucher.tally_guid,
        "vtype": vtype_name,
        "date": (voucher.tally_date or voucher.voucher_date).strftime("%Y%m%d") if voucher.voucher_date else "",
        "name": f"{vtype_name} #{voucher.voucher_number}",
    }


async def _push_voucher_change(db: AsyncSession, user: User, voucher_id: int, action: str, snapshot: dict = None):
    """
    Sends the change, still uncommitted, to Tally and keeps it only if Tally does not refuse it.
    A refusal rolls the whole request back (the voucher, its lines, stock, bills, the number it took) and
    raises with Tally's reason; when Tally cannot be reached the change is kept and stays queued, and a new
    voucher keeps a provisional number until Tally has numbered it.
    Returns the (synced, status, message) to put on the response.
    """
    from app.routers.sync import send_voucher, record_voucher_push
    from app.services.group_deletion import queue_sync_event

    sync_item = await queue_sync_event(db, user.company_id, "Voucher", voucher_id, action, snapshot)
    sync_id = sync_item.sync_id
    result = await send_voucher(db, voucher_id, action)
    if result["status"] == "REJECTED":
        await db.rollback()
        await record_voucher_push(db, voucher_id, None, action, result)
        raise HTTPException(status_code=400, detail=f"Tally did not accept this voucher: {result['reason']}")
    await db.commit()
    clear_company_cache(user.company_id)
    await record_voucher_push(db, voucher_id, sync_id, action, result)
    ok = result["status"] == "SUCCESS"
    message = result["reason"]
    if ok and result.get("renumbered_from"):
        message = f"Tally numbered this voucher {result['name'].split('#')[-1]} (it was provisionally {result['renumbered_from']})."
    elif result["status"] == "NO_RESPONSE" and action == "Create":
        message = "Tally could not be reached. The voucher is saved with a provisional number and will take Tally's number once it is sent."
    return (ok, result["status"], message)


def attach_tally_result(voucher: TrnVoucher, result):
    if voucher is not None and result:
        voucher.tally_synced, voucher.tally_status, voucher.tally_message = result


# --- Voucher Endpoints ---

@router.post("", response_model=VoucherResponse, status_code=status.HTTP_201_CREATED)
async def create_voucher(
    req: VoucherCreate,
    response: Response,
    user: User = Depends(require_permission("vouchers", "create")),
    db: AsyncSession = Depends(get_db)
):
    if not req.entries and not req.inventory_entries and not req.attendance_entries and not req.payroll_entries:
        raise HTTPException(status_code=400, detail="Voucher must have at least one entry.")
        
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    if allowed_ids is not None and req.voucher_type_id not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create vouchers of this type."
        )
        
    total_debits = sum((e.debit_amount for e in req.entries), Decimal('0.00')) if req.entries else Decimal('0.00')
    total_credits = sum((e.credit_amount for e in req.entries), Decimal('0.00')) if req.entries else Decimal('0.00')
    
    if req.entries and total_debits != total_credits:
        raise HTTPException(status_code=400, detail=f"Voucher is unbalanced. Debits: {total_debits}, Credits: {total_credits}")
        
    v_total = total_debits if (req.entries and total_debits > 0) else _inventory_total(req.inventory_entries)

    # Row lock serializes number allocation per voucher type until commit; populate_existing
    # refreshes next_number even if this voucher type is already in the session's identity map.
    vtype_query = await db.execute(
        select(MstVoucherType)
        .where(MstVoucherType.voucher_type_id == req.voucher_type_id, MstVoucherType.company_id == user.company_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    vtype = vtype_query.scalars().first()
    if not vtype:
        raise HTTPException(status_code=400, detail="Voucher type not found.")
        
    if vtype.numbering_method == "Automatic":
        vnum = f"{vtype.prefix or ''}{vtype.next_number}"
        vtype.next_number += 1
    else:
        vnum = req.reference_number or 'MANUAL'
        
    vdate = datetime.strptime(req.voucher_date, "%Y-%m-%d").date()
        
    # Maker-checker: a voucher matching an approval rule is held back from Tally until approved
    from app.services import approvals as approvals_svc
    matching_rule = await approvals_svc.rule_for(db, user, req.voucher_type_id, v_total)
                
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
        # The number is the app's guess until Tally has numbered the voucher
        number_is_provisional=True,
        created_by=user.user_id
    )
    db.add(voucher)
    await db.flush()
    
    await handle_inventory_posting(db, user, voucher, vtype, req)
    await post_payroll_lines(db, user, voucher, vtype, req)
        
    if matching_rule:
        await approvals_svc.request_approval(db, user, voucher, matching_rule, vtype.name if vtype else "Voucher")
        
    await log_audit(db, user.company_id, user.user_id, "CREATE", "Voucher", voucher.voucher_id)
    
    tally_result = None
    voucher_id = voucher.voucher_id
    if final_status == 'confirmed':
        tally_result = await _push_voucher_change(db, user, voucher_id, "Create")
    else:
        await db.commit()
    
    final_query = await db.execute(
        select(TrnVoucher)
        .options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bank_allocations),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.bill_allocations).selectinload(BillAllocation.bill),
            # The response includes each entry's cost-centre allocations
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.cost_centre_allocations),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.accounting_allocations)
        )
        .where(TrnVoucher.voucher_id == voucher_id)
        .execution_options(populate_existing=True)
    )
    
    if matching_rule:
        response.status_code = status.HTTP_202_ACCEPTED
        
    clear_company_cache(user.company_id)
    created = final_query.scalars().first()
    attach_tally_result(created, tally_result)
    return created

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
        
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    if allowed_ids is not None:
        if voucher.voucher_type_id not in allowed_ids or req.voucher_type_id not in allowed_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify vouchers of this type."
            )
        
    vtype_query = await db.execute(select(MstVoucherType).where(MstVoucherType.voucher_type_id == req.voucher_type_id))
    vtype = vtype_query.scalars().first()

    # Capture pre-alter snapshot BEFORE applying any updates
    snapshot = await build_voucher_snapshot(voucher, db)
    
    previous_reference = voucher.reference_number
    voucher.voucher_date = datetime.strptime(req.voucher_date, "%Y-%m-%d").date()
    voucher.reference_number = req.reference_number
    voucher.narration = req.narration
    total_debits = sum((e.debit_amount for e in req.entries), Decimal('0.00')) if req.entries else Decimal('0.00')
    voucher.total_amount = total_debits if (req.entries and total_debits > 0) else _inventory_total(req.inventory_entries)
    voucher.party_ledger_id = req.party_ledger_id
    voucher.is_invoice = req.is_invoice
    voucher.original_voucher_id = req.original_voucher_id
    voucher.gst_registration_id = req.gst_registration_id
    
    await handle_inventory_posting(db, user, voucher, vtype, req, is_update=True, previous_reference=previous_reference)
    await post_payroll_lines(db, user, voucher, vtype, req)
    
    await log_audit(db, user.company_id, user.user_id, "UPDATE", "Voucher", voucher.voucher_id)
    
    tally_result = None
    if voucher.status == 'confirmed':
        await db.flush()
        tally_result = await _push_voucher_change(db, user, voucher_id, "Alter", snapshot)
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
            # The response includes each entry's cost-centre allocations
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.cost_centre_allocations),
            selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.accounting_allocations)
        )
        .where(TrnVoucher.voucher_id == voucher_id)
        .execution_options(populate_existing=True)
    )
    updated = final_query.scalars().first()
    attach_tally_result(updated, tally_result)
    return updated

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
        
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    if allowed_ids is not None and voucher.voucher_type_id not in allowed_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify vouchers of this type.")
        
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
            # The response includes each entry's cost-centre allocations
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.cost_centre_allocations),
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
        
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    if allowed_ids is not None and voucher.voucher_type_id not in allowed_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify vouchers of this type.")
        
    # The row still waiting for this voucher, else a fresh one for the voucher as it is now. A processed row
    # or a delete is never replayed: row ids get reused, and the last row for this id may be the delete of a
    # voucher that had the id before.
    from app.services.group_deletion import queue_sync_event
    sync_item = (await db.execute(
        select(SyncQueue).where(
            SyncQueue.company_id == user.company_id, SyncQueue.record_type == "Voucher", SyncQueue.record_id == voucher_id,
            SyncQueue.is_processed == False, SyncQueue.action != "Delete")
        .order_by(SyncQueue.sync_id.desc())
    )).scalars().first()
    if not sync_item:
        sync_item = await queue_sync_event(db, user.company_id, "Voucher", voucher_id,
                                           "Cancel" if (voucher.is_cancelled or voucher.status == "cancelled") else "Alter")
        await db.commit()
    action = sync_item.action

    from app.routers.sync import try_push_voucher_realtime
    tally_ok, tally_status, tally_err = await try_push_voucher_realtime(voucher_id, sync_item.sync_id, action, db)
    clear_company_cache(user.company_id)
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
        
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    if allowed_ids is not None and voucher.voucher_type_id not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete vouchers of this type."
        )
        
    from app.routers.sync import send_voucher, record_voucher_push
    from app.services.group_deletion import queue_sync_event

    vtype = (await db.execute(select(MstVoucherType).where(MstVoucherType.voucher_type_id == voucher.voucher_type_id))).scalars().first()
    ident = tally_voucher_ident(voucher, vtype.name if vtype else "Journal")

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
        "tally_alter_id": voucher.tally_alter_id,
        "tally_voucher": ident
    }
    
    del_audit = DeletedRecordAudit(
        company_id=user.company_id,
        entity_type="Voucher",
        record_id=voucher_id,
        tally_guid=voucher.tally_guid or ident["remote_id"],
        entity_identifier=f"Voucher #{voucher.voucher_number}",
        deleted_by_user_id=user.user_id,
        tally_sync_status="PENDING",
        snapshot_data=snapshot
    )
    db.add(del_audit)

    # Only vouchers that were sent, or are waiting to be sent, have anything to remove in Tally
    tally_result = (True, "NOT_SENT", None)
    sync_id = None
    result = None
    if voucher.status in ('confirmed', 'cancelled') or voucher.tally_master_id or voucher.tally_guid or voucher.tally_remote_id:
        # The identifiers go on the queue row: a delete retried later no longer has the voucher to read them from
        sync_item = await queue_sync_event(db, user.company_id, "Voucher", voucher_id, "Delete", {"tally_voucher": ident})
        sync_id = sync_item.sync_id
        result = await send_voucher(db, voucher_id, "Delete", ident)
        if result["status"] == "REJECTED":
            # Tally still has the voucher, so the app keeps it too
            await db.rollback()
            await record_voucher_push(db, voucher_id, None, "Delete", result)
            raise HTTPException(status_code=409, detail=f"Tally did not delete this voucher: {result['reason']}")
        ok = result["status"] in ("SUCCESS", "ALREADY_ABSENT")
        message = result["reason"]
        if result["status"] == "NO_RESPONSE":
            message = "Tally could not be reached. The voucher is deleted here and will be deleted in Tally when it is back."
        tally_result = (ok, result["status"], message)
    else:
        del_audit.tally_sync_status = "SYNCED_TO_TALLY"

    from app.services.stock_counts import rebalance_counted_items
    deleted_items = await _voucher_item_ids(db, voucher_id)
    # Attendance and payroll lines hang off the voucher by id only
    await db.execute(delete(TrnAttendance).where(TrnAttendance.voucher_id == voucher_id))
    await db.execute(delete(TrnPayHead).where(TrnPayHead.voucher_id == voucher_id))
    await db.delete(voucher)
    await db.flush()
    await rebalance_counted_items(db, user.company_id, deleted_items)
    await log_audit(db, user.company_id, user.user_id, "DELETE", "Voucher", voucher_id)
    await db.commit()
    clear_company_cache(user.company_id)
    if result is not None:
        await record_voucher_push(db, voucher_id, sync_id, "Delete", result)
    return {
        "detail": "Voucher deleted successfully in MyTally.",
        "tally_synced": tally_result[0],
        "tally_status": tally_result[1],
        "tally_message": tally_result[2]
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
        
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    if allowed_ids is not None and voucher.voucher_type_id not in allowed_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify vouchers of this type.")
        
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
    
    await log_audit(db, user.company_id, user.user_id, "CANCEL", "Voucher", voucher_id)
    await db.flush()
    from app.services.stock_counts import rebalance_counted_items
    await rebalance_counted_items(db, user.company_id, await _voucher_item_ids(db, voucher_id))
    # A cancel Tally refuses is undone here (raises); one Tally cannot be reached for stays queued
    tally_ok, tally_status, tally_err = await _push_voucher_change(db, user, voucher_id, "Cancel")
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
        
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    if allowed_ids is not None and voucher.voucher_type_id not in allowed_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify vouchers of this type.")
        
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
    await log_audit(db, user.company_id, user.user_id, "STATUS_UPDATE", "Voucher", voucher_id)
    await db.flush()
    from app.services.stock_counts import rebalance_counted_items
    await rebalance_counted_items(db, user.company_id, await _voucher_item_ids(db, voucher_id))
    tally_ok, tally_status, tally_err = await _push_voucher_change(db, user, voucher_id, action_type)
    clear_company_cache(user.company_id)
    return {"detail": f"Status updated to {status_val}", "tally_synced": tally_ok, "tally_status": tally_status, "tally_message": tally_err}

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
    response: Response,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    date: Optional[str] = None,
    ledger_id: Optional[int] = None,
    party_name: Optional[str] = None,
    voucher_type: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    user: User = Depends(require_voucher_read_permission),
    db: AsyncSession = Depends(get_db)
):
    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    cache_key = f"vouchers_list_{status}_{from_date}_{to_date}_{date}_{ledger_id}_{party_name}_{voucher_type}"
    if allowed_ids is not None:
        cache_key += f"_user_{user.user_id}"
    if pagination.is_paginated:
        cache_key += f"_p{pagination.page}_ps{pagination.page_size}"

    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        if isinstance(cached, dict) and "items" in cached and "total" in cached:
            apply_pagination_headers(response, cached["total"], pagination)
            return cached["items"]
        elif isinstance(cached, list):
            apply_pagination_headers(response, len(cached), pagination)
            return cached
        return cached

    stmt = select(TrnVoucher).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
    ).where(TrnVoucher.company_id == user.company_id)

    if allowed_ids is not None:
        stmt = stmt.where(TrnVoucher.voucher_type_id.in_(allowed_ids))

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
            "number_is_provisional": bool(v.number_is_provisional),
            "reference_number": v.reference_number,
            "narration": v.narration,
            "party_name": resolved_party,
            "amount": amount,
            "total_amount": float(v.total_amount or 0),
        })

    total = len(result)
    apply_pagination_headers(response, total, pagination)
    paginated_result = pagination.slice_list(result)

    is_historical = is_historical_period(to_date_str=to_date, date_str=date)
    ttl = 86400 if is_historical else 600  # 24h for closed/historical FY, 10 min for active period
    set_cached_response(
        user.company_id,
        cache_key,
        {"items": paginated_result, "total": total} if pagination.is_paginated else paginated_result,
        ttl_seconds=ttl
    )
    return paginated_result

@router.get("/{voucher_id}")
async def get_voucher_detail(
    voucher_id: int,
    user: User = Depends(require_voucher_read_permission),
    db: AsyncSession = Depends(get_db)
):
    cache_key = f"voucher_detail_v3_{voucher_id}"  # v3: number_is_provisional and tally_master_id
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
        if allowed_ids is not None and cached.get("voucher_type_id") not in allowed_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view vouchers of this type."
            )
        return cached

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

    allowed_ids = await get_user_allowed_voucher_type_ids(user.user_id, db)
    if allowed_ids is not None and voucher.voucher_type_id not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view vouchers of this type."
        )

    party_name, amount, party_ledger_id = _resolve_party_and_amount(voucher.entries)
    if voucher.party_ledger_id:
        party_ledger_id = voucher.party_ledger_id
    # The party's ledger (for its GSTIN, B2B or not, and the invoice's buyer block), from the entries
    party_ledger = next((e.ledger for e in voucher.entries if e.ledger and e.ledger_id == party_ledger_id), None)
    party_gstin = party_ledger.gstin if party_ledger and party_ledger.gstin else None
    party_details = {
        "name": party_ledger.name, "address": party_ledger.address, "state": party_ledger.state,
        "pincode": party_ledger.pincode, "gstin": party_ledger.gstin, "mobile": party_ledger.mobile or party_ledger.phone,
        "email": party_ledger.email,
    } if party_ledger else None

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
            # Stock Journal: 'source' (consumed) or 'destination' (produced)
            "flow_type": inv.flow_type,
            "is_inward": inv.is_inward,
            # Physical Stock: the quantity counted (quantity is then the adjustment it made)
            "counted_quantity": float(inv.actual_quantity) if inv.actual_quantity is not None else None,
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

    # Check who cancelled the voucher if cancelled
    cancelled_by = None
    cancelled_at = None
    is_cancelled = bool(voucher.is_cancelled or voucher.status == 'cancelled')
    if is_cancelled:
        audit_res = await db.execute(
            select(AuditLog)
            .options(selectinload(AuditLog.user))
            .where(
                AuditLog.company_id == user.company_id,
                AuditLog.entity_type == "Voucher",
                AuditLog.entity_id == voucher_id,
                AuditLog.action.in_(["CANCEL", "STATUS_UPDATE"])
            )
            .order_by(AuditLog.created_at.desc())
        )
        audit_entry = audit_res.scalars().first()
        if audit_entry:
            cancelled_by = audit_entry.user.username if audit_entry.user else f"User #{audit_entry.user_id}"
            cancelled_at = to_ist_iso(audit_entry.created_at)

    # Check bank reconciliation linkage for this voucher
    from app.models.portal_core import BankStatementTransaction, BankStatement
    stmt_tx_res = await db.execute(
        select(BankStatementTransaction)
        .options(selectinload(BankStatementTransaction.statement))
        .where(BankStatementTransaction.matched_voucher_id == voucher_id)
    )
    stmt_tx = stmt_tx_res.scalars().first()
    bank_recon_info = None
    if stmt_tx:
        bank_recon_info = {
            "transaction_id": stmt_tx.transaction_id,
            "statement_id": stmt_tx.statement_id,
            "statement_filename": stmt_tx.statement.filename if stmt_tx.statement else None,
            "bank_account_no": stmt_tx.statement.account_number if stmt_tx.statement else None,
            "bank_date": stmt_tx.transaction_date.isoformat(),
            "value_date": stmt_tx.value_date.isoformat() if stmt_tx.value_date else None,
            "bank_description": stmt_tx.description,
            "cheque_no": stmt_tx.cheque_no or stmt_tx.reference_no,
            "reference_no": stmt_tx.reference_no,
            "amount": float(stmt_tx.amount),
            "transaction_type": stmt_tx.transaction_type,
            "matched_at": to_ist_iso(stmt_tx.matched_at) if stmt_tx.matched_at else None,
            "match_type": stmt_tx.match_type,
        }

    output = {
        "voucher_id": voucher.voucher_id,
        "date": str(voucher.voucher_date),
        "voucher_date": str(voucher.voucher_date),
        "voucher_type": voucher.voucher_type.name if voucher.voucher_type else "Unknown",
        "voucher_type_id": voucher.voucher_type_id,
        "voucher_number": voucher.voucher_number,
        "number_is_provisional": bool(voucher.number_is_provisional),
        "tally_master_id": voucher.tally_master_id,
        "reference_number": voucher.reference_number,
        "narration": voucher.narration,
        "status": voucher.status,
        "is_cancelled": is_cancelled,
        "cancelled_by": cancelled_by,
        "cancelled_at": cancelled_at,
        "party_name": party_name,
        "party_ledger_id": party_ledger_id,
        "party_gstin": party_gstin,
        "party_details": party_details,
        "original_voucher_id": voucher.original_voucher_id,
        "is_invoice": voucher.is_invoice,
        "amount": amount,
        "total_amount": float(voucher.total_amount or 0),
        "entries": entries,
        "accounts": entries,
        "inventory": inventory,
        "inventory_entries": inventory_entries,
        **(await payroll_lines_of(db, voucher.voucher_id)),
        "is_inventory_voucher": len(inventory) > 0,
        "sync_status": sync_status,
        "tally_error_message": sync_error,
        "can_rollback": can_rollback,
        "sync_id": sync_id,
        "bank_reconciliation": bank_recon_info,
    }

    is_historical = is_historical_period(check_date=voucher.voucher_date)
    ttl = 86400 if is_historical else 600  # 24h for closed/historical FY, 10 min for active period
    set_cached_response(user.company_id, cache_key, output, ttl_seconds=ttl)

    return output
