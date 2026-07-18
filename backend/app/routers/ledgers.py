from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from decimal import Decimal
from sqlalchemy import func

from app.core.database import get_db
from app.core.permissions import require_permission, get_current_user, get_effective_permission
from app.models.user import User
from app.models.sync import SyncQueue
from app.models.ledger import MstGroup, MstLedger, CostCenter
from app.models.voucher import TrnAccounting
from app.schemas.ledger import (
    AccountGroupCreate, AccountGroupResponse,
    LedgerCreate, LedgerResponse,
    CostCenterCreate, CostCenterResponse
)

router = APIRouter(prefix="/ledgers", tags=["Ledgers & Masters"])

# Helpers
async def check_cyclical_parent(db: AsyncSession, company_id: int, parent_id: int, target_id: int) -> bool:
    curr_parent = parent_id
    visited = set()
    while curr_parent is not None:
        if curr_parent == target_id:
            return True
        if curr_parent in visited:
            break
        visited.add(curr_parent)
        res = await db.execute(
            select(MstGroup.parent_group_id).where(
                MstGroup.group_id == curr_parent,
                MstGroup.company_id == company_id
            )
        )
        curr_parent = res.scalar()
    return False

async def is_ancestor_group(group_id: int, target_name: str, company_id: int, db: AsyncSession) -> bool:
    curr_parent = group_id
    visited = set()
    while curr_parent is not None:
        if curr_parent in visited:
            break
        visited.add(curr_parent)
        group_query = await db.execute(
            select(MstGroup).where(
                MstGroup.group_id == curr_parent,
                MstGroup.company_id == company_id
            )
        )
        group = group_query.scalars().first()
        if not group:
            break
        if group.name.lower() == target_name.lower():
            return True
        curr_parent = group.parent_group_id
    return False

# --- Account Groups ---

@router.get("/groups", response_model=List[AccountGroupResponse])
async def get_groups(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    query = await db.execute(
        select(MstGroup).where(MstGroup.company_id == user.company_id)
    )
    return query.scalars().all()

@router.post("/groups", response_model=AccountGroupResponse)
async def create_group(
    req: AccountGroupCreate,
    user: User = Depends(require_permission("ledgers", "create")),
    db: AsyncSession = Depends(get_db)
):
    if req.parent_group_id:
        parent_query = await db.execute(
            select(MstGroup).where(
                MstGroup.group_id == req.parent_group_id,
                MstGroup.company_id == user.company_id
            )
        )
        if not parent_query.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent group not found in this company."
            )
            
    group = MstGroup(
        company_id=user.company_id,
        name=req.name,
        parent_group_id=req.parent_group_id,
        nature=req.nature,
        affects_gross_profit=req.affects_gross_profit,
        is_system_defined=False
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group

# --- Ledgers ---

@router.get("", response_model=List[LedgerResponse])
async def get_ledgers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.core.cache import get_cached_response
    cache_key = f"ledgers_user_{user.user_id}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached:
        return cached

    perms_customer = await get_effective_permission(user.user_id, "ledger_customer", db)
    perms_supplier = await get_effective_permission(user.user_id, "ledger_supplier", db)
    perms_general = await get_effective_permission(user.user_id, "ledgers", db)
    
    if not (perms_customer.get("can_read", False) or perms_supplier.get("can_read", False) or perms_general.get("can_read", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view ledgers."
        )
        
    query = await db.execute(
        select(MstLedger).options(selectinload(MstLedger.group)).where(MstLedger.company_id == user.company_id)
    )
    all_ledgers = query.scalars().all()

    # Aggregate total debits and credits from TrnAccounting for all ledgers in a single query
    balance_stmt = select(
        TrnAccounting.ledger_id,
        func.sum(TrnAccounting.debit_amount).label("total_debit"),
        func.sum(TrnAccounting.credit_amount).label("total_credit")
    ).group_by(TrnAccounting.ledger_id)
    sums_res = await db.execute(balance_stmt)
    sums_dict = {row.ledger_id: (row.total_debit or Decimal("0.00"), row.total_credit or Decimal("0.00")) for row in sums_res}
    
    filtered = []
    for ledger in all_ledgers:
        is_debtor = await is_ancestor_group(ledger.group_id, "Sundry Debtors", user.company_id, db)
        is_creditor = await is_ancestor_group(ledger.group_id, "Sundry Creditors", user.company_id, db)
        
        # Calculate closing balance
        total_dr, total_cr = sums_dict.get(ledger.ledger_id, (Decimal("0.00"), Decimal("0.00")))
        op_bal = ledger.opening_balance or Decimal("0.00")
        
        if ledger.opening_balance_type == "Cr":
            net_bal = -op_bal + total_dr - total_cr
        else:
            net_bal = op_bal + total_dr - total_cr
            
        # Attach dynamic properties
        ledger.closing_balance = net_bal
        ledger.group_name = ledger.group.name if ledger.group else None
        ledger.is_customer = is_debtor
        ledger.is_supplier = is_creditor
        
        # Extract mobile and clean address from combined address field
        mobile_val = None
        address_val = ledger.address
        if ledger.address and " | Mobile: " in ledger.address:
            parts = ledger.address.split(" | Mobile: ")
            address_val = parts[0]
            mobile_val = parts[1]
            
        ledger.mobile = mobile_val
        ledger.address = address_val
        ledger.email = None

        if is_debtor:
            if perms_customer.get("can_read", False):
                filtered.append(ledger)
        elif is_creditor:
            if perms_supplier.get("can_read", False):
                filtered.append(ledger)
        else:
            if perms_general.get("can_read", False):
                filtered.append(ledger)
                
    from app.core.cache import set_cached_response
    set_cached_response(user.company_id, cache_key, filtered)
    return filtered

@router.post("", response_model=LedgerResponse)
async def create_ledger(
    req: LedgerCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate group
    group_query = await db.execute(
        select(MstGroup).where(
            MstGroup.group_id == req.group_id,
            MstGroup.company_id == user.company_id
        )
    )
    if not group_query.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account group not found in this company."
        )
        
    # Check permissions dynamically based on parent group
    is_debtor = await is_ancestor_group(req.group_id, "Sundry Debtors", user.company_id, db)
    is_creditor = await is_ancestor_group(req.group_id, "Sundry Creditors", user.company_id, db)
    
    if is_debtor:
        module_code = "ledger_customer"
    elif is_creditor:
        module_code = "ledger_supplier"
    else:
        module_code = "ledgers"
        
    perms = await get_effective_permission(user.user_id, module_code, db)
    if not perms.get("can_create", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to create in module {module_code}."
        )
        
    # Check if duplicate name in company
    dup_query = await db.execute(
        select(MstLedger).where(
            MstLedger.name == req.name,
            MstLedger.company_id == user.company_id
        )
    )
    if dup_query.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A ledger with this name already exists in the company."
        )
        
    ledger = MstLedger(
        company_id=user.company_id,
        **req.model_dump()
    )
    db.add(ledger)
    await db.flush()
    
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Ledger",
        record_id=ledger.ledger_id,
        action="Create"
    )
    db.add(sync_item)
    
    await db.commit()
    await db.refresh(ledger)
    from app.core.cache import clear_company_cache
    clear_company_cache(user.company_id)
    return ledger

@router.put("/{ledger_id}", response_model=LedgerResponse)
async def update_ledger(
    ledger_id: int,
    req: LedgerCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    ledger_query = await db.execute(
        select(MstLedger).where(
            MstLedger.ledger_id == ledger_id,
            MstLedger.company_id == user.company_id
        )
    )
    ledger = ledger_query.scalars().first()
    if not ledger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ledger not found."
        )
        
    # Validate group
    group_query = await db.execute(
        select(MstGroup).where(
            MstGroup.group_id == req.group_id,
            MstGroup.company_id == user.company_id
        )
    )
    if not group_query.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account group not found in this company."
        )
        
    # Check permissions dynamically for existing group and new group
    is_debtor_old = await is_ancestor_group(ledger.group_id, "Sundry Debtors", user.company_id, db)
    is_creditor_old = await is_ancestor_group(ledger.group_id, "Sundry Creditors", user.company_id, db)
    is_debtor_new = await is_ancestor_group(req.group_id, "Sundry Debtors", user.company_id, db)
    is_creditor_new = await is_ancestor_group(req.group_id, "Sundry Creditors", user.company_id, db)
    
    module_old = "ledger_customer" if is_debtor_old else "ledger_supplier" if is_creditor_old else "ledgers"
    module_new = "ledger_customer" if is_debtor_new else "ledger_supplier" if is_creditor_new else "ledgers"
    
    perms_old = await get_effective_permission(user.user_id, module_old, db)
    perms_new = await get_effective_permission(user.user_id, module_new, db)
    
    if not perms_old.get("can_update", False) or not perms_new.get("can_update", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update ledgers in these module categories."
        )
        
    for k, v in req.model_dump().items():
        setattr(ledger, k, v)
        
    await db.commit()
    await db.refresh(ledger)
    from app.core.cache import clear_company_cache
    clear_company_cache(user.company_id)
    return ledger

@router.delete("/{ledger_id}")
async def delete_ledger(
    ledger_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    ledger_query = await db.execute(
        select(MstLedger).where(
            MstLedger.ledger_id == ledger_id,
            MstLedger.company_id == user.company_id
        )
    )
    ledger = ledger_query.scalars().first()
    if not ledger:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ledger not found."
        )
        
    # Check permissions dynamically
    is_debtor = await is_ancestor_group(ledger.group_id, "Sundry Debtors", user.company_id, db)
    is_creditor = await is_ancestor_group(ledger.group_id, "Sundry Creditors", user.company_id, db)
    
    module_code = "ledger_customer" if is_debtor else "ledger_supplier" if is_creditor else "ledgers"
    perms = await get_effective_permission(user.user_id, module_code, db)
    if not perms.get("can_delete", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to delete in module {module_code}."
        )
        
    await db.delete(ledger)
    await db.commit()
    from app.core.cache import clear_company_cache
    clear_company_cache(user.company_id)
    return {"detail": "Ledger deleted successfully."}

@router.get("/{ledger_id}/statement")
async def get_ledger_statement(
    ledger_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.models.ledger import MstLedger
    ledger_stmt = select(MstLedger).options(selectinload(MstLedger.group)).where(
        MstLedger.ledger_id == ledger_id,
        MstLedger.company_id == user.company_id
    )
    ledger_res = await db.execute(ledger_stmt)
    ledger = ledger_res.scalars().first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")
        
    addr = ledger.address or ""
    mobile_val = ""
    if addr and " | Mobile: " in addr:
        parts = addr.split(" | Mobile: ")
        addr = parts[0]
        mobile_val = parts[1]
        
    ledger_info = {
        "ledger_id": ledger.ledger_id,
        "name": ledger.name,
        "parent": ledger.group.name if ledger.group else "Unknown",
        "gstn": ledger.gstin,
        "address": addr,
        "state": ledger.state,
        "mobile": mobile_val,
    }

    from app.models.voucher import TrnAccounting, TrnVoucher, MstVoucherType
    
    stmt = select(
        TrnAccounting.voucher_id,
        TrnAccounting.debit_amount,
        TrnAccounting.credit_amount,
        TrnVoucher.voucher_date,
        TrnVoucher.voucher_number,
        TrnVoucher.reference_number,
        TrnVoucher.narration,
        MstVoucherType.name.label("voucher_type_name")
    ).join(
        TrnVoucher, TrnAccounting.voucher_id == TrnVoucher.voucher_id
    ).join(
        MstVoucherType, TrnVoucher.voucher_type_id == MstVoucherType.voucher_type_id
    ).where(
        TrnAccounting.ledger_id == ledger_id,
        TrnVoucher.company_id == user.company_id
    ).order_by(
        TrnVoucher.voucher_date.desc()
    )
    
    tx_res = await db.execute(stmt)
    transactions = []
    for row in tx_res.all():
        deb = float(row.debit_amount or 0)
        cred = float(row.credit_amount or 0)
        amt = -deb if deb > 0 else cred
        
        transactions.append({
            "id": row.voucher_id,
            "date": str(row.voucher_date),
            "voucherType": row.voucher_type_name,
            "voucherNumber": row.voucher_number,
            "referenceNumber": row.reference_number,
            "narration": row.narration,
            "partyName": "",
            "amount": str(amt),
        })
        
    return {
        "success": True,
        "ledgerInfo": ledger_info,
        "transactions": transactions,
    }
