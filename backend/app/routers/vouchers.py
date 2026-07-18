from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import json

from app.models.payment import TrnBill

from app.core.database import get_db
from app.core.permissions import require_permission, get_current_user
from app.models.user import User, Module
from app.models.voucher import MstVoucherType, TrnVoucher, TrnAccounting, ApprovalRule, ApprovalRequest, AuditLog
from app.models.ledger import MstLedger
from app.models.sync import SyncQueue
from app.schemas.voucher import (
    VoucherCreate, VoucherResponse, VoucherListResponse,
    ApprovalRuleCreate, ApprovalRuleResponse,
    ApprovalRequestResponse
)

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
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(
        select(MstVoucherType).where(MstVoucherType.company_id == user.company_id)
    )
    return res.scalars().all()

# --- Voucher Posting ---

@router.post("", response_model=VoucherResponse, status_code=status.HTTP_201_CREATED)
async def create_voucher(
    req: VoucherCreate,
    response: Response,
    user: User = Depends(require_permission("vouchers", "create")),
    db: AsyncSession = Depends(get_db)
):
    if not req.entries:
        raise HTTPException(status_code=400, detail="Voucher must have at least one entry.")
        
    total_debits = sum(e.debit_amount for e in req.entries)
    total_credits = sum(e.credit_amount for e in req.entries)
    
    if total_debits != total_credits:
        raise HTTPException(
            status_code=400,
            detail=f"Voucher is unbalanced. Total Debits: {total_debits}, Total Credits: {total_credits}"
        )
    if total_debits <= 0:
        raise HTTPException(status_code=400, detail="Voucher amount must be greater than zero.")
        
    # Get voucher type
    vtype_query = await db.execute(
        select(MstVoucherType).where(
            MstVoucherType.voucher_type_id == req.voucher_type_id,
            MstVoucherType.company_id == user.company_id
        )
    )
    vtype = vtype_query.scalars().first()
    if not vtype:
        raise HTTPException(status_code=400, detail="Voucher type not found.")
        
    # Generate auto-numbering
    if vtype.numbering_method == "Automatic":
        vnum = f"{vtype.prefix or ''}{vtype.next_number}"
        vtype.next_number += 1
    else:
        if not req.reference_number:
            raise HTTPException(status_code=400, detail="Manual voucher number must be provided in reference_number.")
        vnum = req.reference_number
        
    # Parse date
    try:
        vdate = datetime.strptime(req.voucher_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        
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
                
    is_held_for_approval = False
    if matching_rule:
        is_held_for_approval = True
        
    voucher = TrnVoucher(
        company_id=user.company_id,
        voucher_type_id=req.voucher_type_id,
        voucher_number=vnum,
        voucher_date=vdate,
        reference_number=req.reference_number,
        narration=req.narration,
        total_amount=total_debits,
        is_optional=True if is_held_for_approval else req.is_optional,
        created_by=user.user_id
    )
    db.add(voucher)
    await db.flush() # Populate voucher_id
    
    # Save entries
    for e in req.entries:
        # Verify ledger exists and load group
        ledg_query = await db.execute(
            select(MstLedger).options(selectinload(MstLedger.group)).where(MstLedger.ledger_id == e.ledger_id, MstLedger.company_id == user.company_id)
        )
        ledger = ledg_query.scalars().first()
        if not ledger:
            raise HTTPException(status_code=400, detail=f"Ledger ID {e.ledger_id} not found in this company.")
            
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
        
        # Auto-create outstanding bill for party ledger entries in Sales/Purchase
        if vtype.name in ['Sales', 'Purchase'] and ('Debtors' in ledger.group.name or 'Creditors' in ledger.group.name):
            days = ledger.credit_period_days or 0
            due = vdate + timedelta(days=days)
            amount = e.debit_amount if e.debit_amount > 0 else e.credit_amount
            
            bill = TrnBill(
                company_id=user.company_id,
                party_ledger_id=ledger.ledger_id,
                voucher_id=voucher.voucher_id,
                bill_reference=vnum,
                bill_date=vdate,
                due_date=due,
                bill_amount=amount,
                settled_amount=0.00,
                status="Open"
            )
            db.add(bill)
        
    # If maker-checker was triggered, save approval request
    if is_held_for_approval:
        app_req = ApprovalRequest(
            rule_id=matching_rule.rule_id,
            voucher_id=voucher.voucher_id,
            requested_by=user.user_id,
            status="Pending"
        )
        db.add(app_req)
        
    # Log audit trail
    new_value_snapshot = {
        "voucher_number": vnum,
        "total_amount": float(total_debits),
        "is_optional": voucher.is_optional,
        "held_for_approval": is_held_for_approval
    }
    await log_audit(
        db,
        user.company_id,
        user.user_id,
        "CREATE",
        "Voucher",
        voucher.voucher_id,
        new_val=new_value_snapshot
    )
    
    if not voucher.is_optional:
        sync_item = SyncQueue(
            company_id=user.company_id,
            record_type="Voucher",
            record_id=voucher.voucher_id,
            action="Create"
        )
        db.add(sync_item)
        
    await db.commit()
    
    # Fetch completed object with entries loaded
    final_query = await db.execute(
        select(TrnVoucher)
        .options(
            selectinload(TrnVoucher.voucher_type),
            selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
        )
        .where(TrnVoucher.voucher_id == voucher.voucher_id)
    )
    final_voucher = final_query.scalars().first()
    
    if is_held_for_approval:
        response.status_code = status.HTTP_202_ACCEPTED
        
    return final_voucher

def _resolve_party_and_amount(entries):
    """Score entries by ledger group to find the primary party (like tally-web's party_name lookup)."""
    if not entries:
        return "Cash Account", 0.0

    primary_entry = entries[0]
    max_score = -100

    for entry in entries:
        ledger = getattr(entry, "ledger", None)
        if not ledger:
            continue
        group = getattr(ledger, "group", None)
        gname = (getattr(group, "name", "") or "").lower() if group else ""
        lname = (getattr(ledger, "name", "") or "").lower()

        score = 0
        if "debtors" in gname or "creditors" in gname:
            score = 10
        elif "bank" in gname or "cash" in gname:
            score = 5
        elif "sales" in gname or "purchase" in gname or "tax" in gname or "duty" in gname or "round" in lname:
            score = -10
        else:
            score = 1

        if score > max_score:
            max_score = score
            primary_entry = entry

    ledger = getattr(primary_entry, "ledger", None)
    party_name = getattr(ledger, "name", "Cash Account") if ledger else "Cash Account"

    debit = float(primary_entry.debit_amount or 0)
    credit = float(primary_entry.credit_amount or 0)
    amount = debit if debit > 0 else credit

    return party_name, abs(amount)


@router.get("", response_model=List[VoucherListResponse])
async def get_vouchers(
    is_optional: Optional[bool] = None,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TrnVoucher).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
    ).where(TrnVoucher.company_id == user.company_id)
    if is_optional is not None:
        stmt = stmt.where(TrnVoucher.is_optional == is_optional)
    stmt = stmt.order_by(TrnVoucher.voucher_date.desc(), TrnVoucher.voucher_id.desc())
    res = await db.execute(stmt)
    vouchers = res.scalars().all()

    result = []
    for v in vouchers:
        party_name, amount = _resolve_party_and_amount(v.entries)
        if amount == 0:
            continue
        result.append({
            "voucher_id": v.voucher_id,
            "date": str(v.voucher_date),
            "voucher_type": v.voucher_type.name if v.voucher_type else "Unknown",
            "voucher_number": v.voucher_number,
            "reference_number": v.reference_number,
            "narration": v.narration,
            "party_name": party_name,
            "amount": amount,
            "total_amount": float(v.total_amount or 0),
        })
    return result

@router.get("/{voucher_id}")
async def get_voucher_detail(
    voucher_id: int,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(TrnVoucher).options(
        selectinload(TrnVoucher.voucher_type),
        selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group)
    ).where(
        TrnVoucher.voucher_id == voucher_id,
        TrnVoucher.company_id == user.company_id
    )
    res = await db.execute(stmt)
    voucher = res.scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found")

    party_name, amount = _resolve_party_and_amount(voucher.entries)

    # Build entries list with ledger names
    entries = []
    for entry in voucher.entries:
        ledger = getattr(entry, "ledger", None)
        ledger_name = getattr(ledger, "name", "Unknown") if ledger else "Unknown"
        debit = float(entry.debit_amount or 0)
        credit = float(entry.credit_amount or 0)
        entries.append({
            "ledger_name": ledger_name,
            "amount": debit if debit > 0 else credit,
            "entry_type": "Debit" if debit > 0 else "Credit",
        })

    # Fetch inventory entries
    from app.models.inventory import TrnInventory, MstStockItem
    inv_stmt = select(TrnInventory).options(
        selectinload(TrnInventory.stock_item).selectinload(MstStockItem.unit)
    ).where(TrnInventory.voucher_id == voucher_id)
    inv_res = await db.execute(inv_stmt)
    inv_entries = inv_res.scalars().all()

    inventory = []
    for inv in inv_entries:
        item_name = inv.stock_item.name if inv.stock_item else "Unknown Item"
        uom_sym = inv.stock_item.unit.symbol if inv.stock_item and inv.stock_item.unit else "PCS"
        gst_pct = float(inv.stock_item.gst_rate_percent or 0) if inv.stock_item else 0.0
        hsn_code = inv.stock_item.hsn_code if inv.stock_item else ""
        
        qty = float(inv.quantity or 0)
        rate = float(inv.rate or 0)
        amt = float(inv.amount or 0)
        
        expected_amt = abs(qty * rate)
        actual_amt = abs(amt)
        discount_percent = 0.0
        if expected_amt > actual_amt and expected_amt > 0:
            diff = expected_amt - actual_amt
            if diff > 1.0:
                discount_percent = round((diff / expected_amt) * 100, 2)

        inventory.append({
            "item": item_name,
            "quantity": qty,
            "rate": rate,
            "uom": uom_sym,
            "gstRate": gst_pct,
            "gstHsnCode": hsn_code,
            "discountAmount": str(discount_percent) if discount_percent > 0 else "0",
            "amount": amt,
        })

    # Fetch party ledger details
    party_ledger = None
    if party_name:
        party_stmt = select(MstLedger).where(
            MstLedger.name == party_name,
            MstLedger.company_id == user.company_id
        )
        party_res = await db.execute(party_stmt)
        party_led = party_res.scalars().first()
        if party_led:
            addr = party_led.address or ""
            mobile_val = ""
            if addr and " | Mobile: " in addr:
                parts = addr.split(" | Mobile: ")
                addr = parts[0]
                mobile_val = parts[1]
            party_ledger = {
                "mailingName": party_led.name,
                "mailingAddress": addr,
                "gstn": party_led.gstin,
                "mailingState": party_led.state,
                "mobile": mobile_val,
            }

    # Map entries for UI accounts list: rename keys to match tally-web details client expectations and deduplicate
    accounts_mapped = []
    seen = set()
    for entry in entries:
        ledger = entry["ledger_name"]
        amt = entry["amount"] if entry["entry_type"] == "Credit" else -entry["amount"]
        key = (ledger, amt)
        if key in seen:
            continue
        seen.add(key)
        accounts_mapped.append({
            "ledger": ledger,
            "amount": amt
        })

    return {
        "voucher_id": voucher.voucher_id,
        "date": str(voucher.voucher_date),
        "voucher_type": voucher.voucher_type.name if voucher.voucher_type else "Unknown",
        "voucher_number": voucher.voucher_number,
        "reference_number": voucher.reference_number,
        "narration": voucher.narration,
        "party_name": party_name,
        "amount": amount,
        "total_amount": float(voucher.total_amount or 0),
        "entries": entries,
        "accounts": accounts_mapped,
        "inventory": inventory,
        "is_inventory_voucher": len(inventory) > 0,
        "party_ledger": party_ledger,
    }

# --- Rules ---

@router.post("/rules", response_model=ApprovalRuleResponse)
async def create_approval_rule(
    req: ApprovalRuleCreate,
    user: User = Depends(require_permission("roles", "create")),
    db: AsyncSession = Depends(get_db)
):
    rule = ApprovalRule(
        company_id=user.company_id,
        **req.model_dump()
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

# --- Maker Checker Actions ---

@router.get("/pending-approvals", response_model=List[ApprovalRequestResponse])
async def get_pending_approvals(
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ApprovalRequest)
        .join(ApprovalRule, ApprovalRequest.rule_id == ApprovalRule.rule_id)
        .where(
            ApprovalRequest.status == "Pending",
            ApprovalRule.company_id == user.company_id
        )
    )
    
    admin_query = await db.execute(
        select(User).where(User.user_id == user.user_id).options(selectinload(User.role))
    )
    curr_user = admin_query.scalars().first()
    if curr_user.role.name != "Admin":
        stmt = stmt.where(ApprovalRule.approver_role_id == user.role_id)
        
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/approve/{request_id}")
async def approve_voucher(
    request_id: int,
    comments: Optional[str] = None,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.voucher))
        .join(ApprovalRule, ApprovalRequest.rule_id == ApprovalRule.rule_id)
        .where(
            ApprovalRequest.request_id == request_id,
            ApprovalRule.company_id == user.company_id
        )
    )
    res = await db.execute(stmt)
    req = res.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found.")
        
    admin_query = await db.execute(
        select(User).where(User.user_id == user.user_id).options(selectinload(User.role))
    )
    curr_user = admin_query.scalars().first()
    
    rule_res = await db.execute(select(ApprovalRule).where(ApprovalRule.rule_id == req.rule_id))
    rule = rule_res.scalars().first()
    
    if curr_user.role.name != "Admin" and rule.approver_role_id != user.role_id:
        raise HTTPException(status_code=403, detail="You do not have permission to approve this request.")
        
    req.status = "Approved"
    req.acted_by = user.user_id
    req.acted_at = datetime.now(timezone.utc)
    req.comments = comments
    
    req.voucher.is_optional = False
    
    await log_audit(
        db,
        user.company_id,
        user.user_id,
        "UPDATE",
        "Voucher",
        req.voucher_id,
        old_val={"is_optional": True},
        new_val={"is_optional": False, "approved_by": user.user_id}
    )
    
    await db.commit()
    return {"detail": "Voucher approved and posted successfully."}

@router.post("/reject/{request_id}")
async def reject_voucher(
    request_id: int,
    comments: Optional[str] = None,
    user: User = Depends(require_permission("vouchers", "update")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ApprovalRequest)
        .options(selectinload(ApprovalRequest.voucher))
        .join(ApprovalRule, ApprovalRequest.rule_id == ApprovalRule.rule_id)
        .where(
            ApprovalRequest.request_id == request_id,
            ApprovalRule.company_id == user.company_id
        )
    )
    res = await db.execute(stmt)
    req = res.scalars().first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found.")
        
    admin_query = await db.execute(
        select(User).where(User.user_id == user.user_id).options(selectinload(User.role))
    )
    curr_user = admin_query.scalars().first()
    
    rule_res = await db.execute(select(ApprovalRule).where(ApprovalRule.rule_id == req.rule_id))
    rule = rule_res.scalars().first()
    
    if curr_user.role.name != "Admin" and rule.approver_role_id != user.role_id:
        raise HTTPException(status_code=403, detail="You do not have permission to reject this request.")
        
    req.status = "Rejected"
    req.acted_by = user.user_id
    req.acted_at = datetime.now(timezone.utc)
    req.comments = comments
    
    req.voucher.is_cancelled = True
    
    await log_audit(
        db,
        user.company_id,
        user.user_id,
        "CANCEL",
        "Voucher",
        req.voucher_id,
        old_val={"is_cancelled": False},
        new_val={"is_cancelled": True, "rejected_by": user.user_id}
    )
    
    await db.commit()
    return {"detail": "Voucher rejected and cancelled."}
