from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from decimal import Decimal
from sqlalchemy import func, delete, update
import logging

logger = logging.getLogger("app.routers.ledgers")

from app.core.database import get_db
from app.core.permissions import require_permission, get_current_user, get_effective_permission
from app.models.portal_core import User
from app.models.portal_core import SyncQueue
from app.models.tally_core import MstGroup, MstLedger, MstLedgerBankDetail, CostCenter, BankTransactionType, MstLedgerMsmeDetail
from app.models.portal_core import GstRegistrationType
from app.models.tally_core import TrnAccounting
from app.schemas.ledger import (
    AccountGroupCreate, AccountGroupResponse, AccountGroupUpdate, AccountGroupTreeNode,
    LedgerCreate, LedgerResponse,
    CostCenterCreate, CostCenterResponse,
    GstRegistrationTypeResponse, BankTransactionTypeResponse
)

router = APIRouter(prefix="/ledgers", tags=["Ledgers & Masters"])

@router.get("/gst-registration-types", response_model=List[GstRegistrationTypeResponse])
async def get_gst_registration_types(
    db: AsyncSession = Depends(get_db)
):
    stmt = select(GstRegistrationType).where(GstRegistrationType.is_active == True).order_by(GstRegistrationType.display_order)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.get("/bank-transaction-types", response_model=List[BankTransactionTypeResponse])
async def get_bank_transaction_types(
    db: AsyncSession = Depends(get_db)
):
    stmt = select(BankTransactionType).where(BankTransactionType.is_active == True).order_by(BankTransactionType.display_order)
    res = await db.execute(stmt)
    return res.scalars().all()

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
        select(MstGroup).options(
            selectinload(MstGroup.gst_details)
        ).where(MstGroup.company_id == user.company_id)
    )
    return query.scalars().all()

@router.get("/groups/tree", response_model=List[AccountGroupTreeNode])
async def get_groups_tree(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    query = await db.execute(
        select(MstGroup).options(
            selectinload(MstGroup.gst_details)
        ).where(MstGroup.company_id == user.company_id)
    )
    groups = query.scalars().all()
    
    # Build tree
    group_dict = {
        g.group_id: AccountGroupTreeNode(**AccountGroupResponse.model_validate(g).model_dump(), children=[])
        for g in groups
    }
    tree = []
    
    for g in groups:
        node = group_dict[g.group_id]
        if g.parent_group_id and g.parent_group_id in group_dict:
            group_dict[g.parent_group_id].children.append(node)
        else:
            tree.append(node)
            
    return tree

@router.get("/groups/{group_id}", response_model=AccountGroupResponse)
async def get_group(
    group_id: int,
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    query = await db.execute(
        select(MstGroup).options(
            selectinload(MstGroup.gst_details)
        ).where(
            MstGroup.group_id == group_id,
            MstGroup.company_id == user.company_id
        )
    )
    group = query.scalars().first()
    if not group:
        logger.warning(f"Failed to fetch group {group_id} for user {user.user_id}: Group not found.")
        raise HTTPException(status_code=404, detail="Group not found.")
    return group

@router.post("/groups", response_model=AccountGroupResponse)
async def create_group(
    req: AccountGroupCreate,
    user: User = Depends(require_permission("ledgers", "create")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} (Company {user.company_id}) attempting to create group: {req.name}")
    
    # Duplicate check
    dup_query = await db.execute(
        select(MstGroup).where(
            MstGroup.name == req.name,
            MstGroup.company_id == user.company_id
        )
    )
    if dup_query.scalars().first():
        logger.warning(f"User {user.user_id} failed to create group: Name '{req.name}' already exists.")
        raise HTTPException(status_code=400, detail="A group with this name already exists in the company.")

    if req.parent_group_id:
        parent_query = await db.execute(
            select(MstGroup).where(
                MstGroup.group_id == req.parent_group_id,
                MstGroup.company_id == user.company_id
            )
        )
        parent_grp = parent_query.scalars().first()
        if not parent_grp:
            logger.warning(f"User {user.user_id} failed to create group: Parent ID {req.parent_group_id} not found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent group not found in this company."
            )
        if not parent_grp.is_addable:
            logger.warning(f"User {user.user_id} failed to create group: Parent ID {req.parent_group_id} is not addable.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add sub-groups under this parent group."
            )
            
    group = MstGroup(
        company_id=user.company_id,
        name=req.name,
        parent_group_id=req.parent_group_id,
        nature=req.nature,
        affects_gross_profit=req.affects_gross_profit,
        alias_name=req.alias_name,
        is_addable=req.is_addable,
        is_revenue=req.is_revenue,
        is_subledger=req.is_subledger,
        is_billwise_on=req.is_billwise_on,
        used_for_calculation=req.used_for_calculation,
        method_to_allocate=req.method_to_allocate,
        is_system_defined=False
    )
    db.add(group)
    await db.flush()
    
    if req.gst_details:
        from app.models.tally_core import MstGroupGstDetails
        for gst in req.gst_details:
            gst_row = MstGroupGstDetails(
                group_id=group.group_id,
                applicable_from=gst.applicable_from,
                hsn_sac_details=gst.hsn_sac_details,
                hsn_sac=gst.hsn_sac,
                gst_rate_details=gst.gst_rate_details,
                taxability_type=gst.taxability_type,
                gst_rate=gst.gst_rate
            )
            db.add(gst_row)
        await db.flush()
    
    # Sync Queue
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Group",
        record_id=group.group_id,
        action="Create",
    )
    db.add(sync_item)
    await db.commit()
    await db.refresh(group)
    
    from app.routers.sync import try_push_group_realtime
    await try_push_group_realtime(group.group_id, sync_item.sync_id, "Create", db)
    
    logger.info(f"Group created successfully: {group.name} (ID: {group.group_id})")
    return group

@router.put("/groups/{group_id}", response_model=AccountGroupResponse)
async def update_group(
    group_id: int,
    req: AccountGroupUpdate,
    user: User = Depends(require_permission("ledgers", "update")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} (Company {user.company_id}) attempting to update group ID {group_id}")
    
    query = await db.execute(
        select(MstGroup).where(
            MstGroup.group_id == group_id,
            MstGroup.company_id == user.company_id
        )
    )
    group = query.scalars().first()
    if not group:
        logger.warning(f"User {user.user_id} failed to update group ID {group_id}: Not found.")
        raise HTTPException(status_code=404, detail="Group not found.")
        
    if group.is_system_defined and req.nature != group.nature:
        logger.warning(f"User {user.user_id} failed to update group ID {group_id}: Cannot change nature of system group.")
        raise HTTPException(status_code=400, detail="Cannot change nature of system-defined groups.")
        
    # Duplicate name check
    if req.name != group.name:
        dup_query = await db.execute(
            select(MstGroup).where(
                MstGroup.name == req.name,
                MstGroup.company_id == user.company_id
            )
        )
        if dup_query.scalars().first():
            logger.warning(f"User {user.user_id} failed to update group ID {group_id}: Name '{req.name}' already exists.")
            raise HTTPException(status_code=400, detail="A group with this name already exists.")

    if req.parent_group_id:
        if req.parent_group_id == group.group_id:
            logger.warning(f"User {user.user_id} failed to update group ID {group_id}: Self parent assignment.")
            raise HTTPException(status_code=400, detail="A group cannot be its own parent.")
            
        parent_query = await db.execute(
            select(MstGroup).where(
                MstGroup.group_id == req.parent_group_id,
                MstGroup.company_id == user.company_id
            )
        )
        parent_grp = parent_query.scalars().first()
        if not parent_grp:
            logger.warning(f"User {user.user_id} failed to update group ID {group_id}: Parent ID {req.parent_group_id} not found.")
            raise HTTPException(status_code=400, detail="Parent group not found.")
            
        # Circular reference check
        curr_parent = parent_grp.parent_group_id
        while curr_parent is not None:
            if curr_parent == group.group_id:
                logger.warning(f"User {user.user_id} failed to update group ID {group_id}: Circular reference detected.")
                raise HTTPException(status_code=400, detail="Circular parent reference detected.")
            parent_query2 = await db.execute(select(MstGroup).where(MstGroup.group_id == curr_parent))
            p2 = parent_query2.scalars().first()
            curr_parent = p2.parent_group_id if p2 else None
            
    group.name = req.name
    group.parent_group_id = req.parent_group_id
    group.nature = req.nature
    group.affects_gross_profit = req.affects_gross_profit
    group.alias_name = req.alias_name
    group.is_addable = req.is_addable
    group.is_revenue = req.is_revenue
    group.is_subledger = req.is_subledger
    group.is_billwise_on = req.is_billwise_on
    group.used_for_calculation = req.used_for_calculation
    group.method_to_allocate = req.method_to_allocate
    
    if req.gst_details is not None:
        from app.models.tally_core import MstGroupGstDetails
        await db.execute(delete(MstGroupGstDetails).where(MstGroupGstDetails.group_id == group_id))
        for gst in req.gst_details:
            gst_row = MstGroupGstDetails(
                group_id=group_id,
                applicable_from=gst.applicable_from,
                hsn_sac_details=gst.hsn_sac_details,
                hsn_sac=gst.hsn_sac,
                gst_rate_details=gst.gst_rate_details,
                taxability_type=gst.taxability_type,
                gst_rate=gst.gst_rate
            )
            db.add(gst_row)
            
    await db.flush()
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Group",
        record_id=group.group_id,
        action="Alter",
    )
    db.add(sync_item)
    await db.commit()
    await db.refresh(group)
    
    from app.routers.sync import try_push_group_realtime
    await try_push_group_realtime(group.group_id, sync_item.sync_id, "Alter", db)
    
    logger.info(f"Group updated successfully: {group.name} (ID: {group.group_id})")
    return group

@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: int,
    user: User = Depends(require_permission("ledgers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} (Company {user.company_id}) attempting to delete group ID {group_id}")
    
    query = await db.execute(
        select(MstGroup).where(
            MstGroup.group_id == group_id,
            MstGroup.company_id == user.company_id
        )
    )
    group = query.scalars().first()
    if not group:
        logger.warning(f"User {user.user_id} failed to delete group ID {group_id}: Not found.")
        raise HTTPException(status_code=404, detail="Group not found.")
        
    if group.is_system_defined:
        logger.warning(f"User {user.user_id} failed to delete group ID {group_id}: System-defined group.")
        raise HTTPException(status_code=400, detail="Cannot delete system-defined groups.")
        
    # Check for child groups
    child_group_query = await db.execute(select(MstGroup).where(MstGroup.parent_group_id == group_id))
    if child_group_query.scalars().first():
        logger.warning(f"User {user.user_id} failed to delete group ID {group_id}: Has child groups.")
        raise HTTPException(status_code=400, detail="Cannot delete group because it has child sub-groups.")
        
    # Check for child ledgers
    child_ledger_query = await db.execute(select(MstLedger).where(MstLedger.group_id == group_id))
    if child_ledger_query.scalars().first():
        logger.warning(f"User {user.user_id} failed to delete group ID {group_id}: Has attached ledgers.")
        raise HTTPException(status_code=400, detail="Cannot delete group because it is assigned to one or more ledgers.")
        
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Group",
        record_id=group.group_id,
        action="Delete",
    )
    db.add(sync_item)
    await db.flush()
    
    from app.routers.sync import try_push_group_realtime
    await try_push_group_realtime(group.group_id, sync_item.sync_id, "Delete", db)
    
    await db.delete(group)
    await db.commit()
    
    logger.info(f"Group deleted successfully: {group.name} (ID: {group_id})")
    
    return {"detail": "Group deleted successfully."}

# --- Ledgers ---

@router.get("", response_model=List[LedgerResponse])
async def get_ledgers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.core.cache import get_cached_response
    cache_key = f"ledgers_user_{user.user_id}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    perms_customer = await get_effective_permission(user.user_id, "ledger_customer", db)
    perms_supplier = await get_effective_permission(user.user_id, "ledger_supplier", db)
    perms_general = await get_effective_permission(user.user_id, "ledgers", db)
    perms_visits = await get_effective_permission(user.user_id, "visits", db)
    
    if not (perms_customer.get("can_read", False) or perms_supplier.get("can_read", False) or perms_general.get("can_read", False) or perms_visits.get("can_read", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view ledgers."
        )
        
    query = await db.execute(
        select(MstLedger).options(selectinload(MstLedger.group), selectinload(MstLedger.bank_details)).where(MstLedger.company_id == user.company_id)
    )
    all_ledgers = query.scalars().all()

    # Pre-fetch all groups for fast in-memory hierarchy resolution (0 DB queries in loop)
    groups_res = await db.execute(
        select(MstGroup).where(MstGroup.company_id == user.company_id)
    )
    groups_dict = {g.group_id: g for g in groups_res.scalars().all()}

    def check_is_ancestor(group_id: int, target_name: str) -> bool:
        curr_id = group_id
        target_lower = target_name.lower()
        visited = set()
        while curr_id in groups_dict:
            if curr_id in visited:
                break
            visited.add(curr_id)
            grp = groups_dict[curr_id]
            if grp.name and grp.name.lower() == target_lower:
                return True
            curr_id = grp.parent_group_id
        return False

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
        is_debtor = check_is_ancestor(ledger.group_id, "Sundry Debtors")
        is_creditor = check_is_ancestor(ledger.group_id, "Sundry Creditors")
        
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
            
        ledger.mobile = mobile_val or getattr(ledger, 'mobile', None)
        ledger.address = address_val

        if is_debtor:
            if perms_customer.get("can_read", False) or perms_visits.get("can_read", False) or perms_general.get("can_read", False):
                filtered.append(ledger)
        elif is_creditor:
            if perms_supplier.get("can_read", False) or perms_general.get("can_read", False):
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
        
    # Process payload
    data_dict = req.model_dump()
    bank_details_data = data_dict.pop("bank_details", None)
    mobile_val = data_dict.pop("mobile", None)

    # Auto-extract PAN from GSTIN if missing
    if data_dict.get("gstin") and len(data_dict["gstin"].strip()) >= 12 and not data_dict.get("pan_number"):
        data_dict["pan_number"] = data_dict["gstin"].strip()[2:12].upper()

    ent_type = data_dict.pop("enterprise_type", None)
    udyam_no = data_dict.pop("udyam_reg_no", None)

    valid_cols = {c.name for c in MstLedger.__table__.columns}
    filtered_data = {k: v for k, v in data_dict.items() if k in valid_cols}

    ledger = MstLedger(company_id=user.company_id, **filtered_data)
    db.add(ledger)
    await db.flush()

    if ent_type or udyam_no:
        from datetime import date
        db.add(MstLedgerMsmeDetail(
            ledger_id=ledger.ledger_id,
            enterprise_type=ent_type or "Micro",
            udyam_reg_no=udyam_no,
            applicable_from=date.today()
        ))

    if bank_details_data:
        for bd in bank_details_data:
            if bd.get("account_number") or bd.get("upi_id") or bd.get("bank_name"):
                b_record = MstLedgerBankDetail(
                    company_id=user.company_id,
                    ledger_id=ledger.ledger_id,
                    **bd
                )
                db.add(b_record)

    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Ledger",
        record_id=ledger.ledger_id,
        action="Create",
    )
    db.add(sync_item)

    await db.commit()
    await db.refresh(ledger)

    # Trigger real-time on-the-run push to Tally Prime
    from app.routers.sync import try_push_ledger_realtime
    await try_push_ledger_realtime(ledger.ledger_id, sync_item.sync_id, "Create", db)

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
        select(MstLedger).options(selectinload(MstLedger.bank_details)).where(
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
        
    data_dict = req.model_dump()
    bank_details_data = data_dict.pop("bank_details", None)
    mobile_val = data_dict.pop("mobile", None)

    # Auto-extract PAN from GSTIN if missing
    if data_dict.get("gstin") and len(data_dict["gstin"].strip()) >= 12 and not data_dict.get("pan_number"):
        data_dict["pan_number"] = data_dict["gstin"].strip()[2:12].upper()

    if mobile_val and data_dict.get("address"):
        if " | Mobile: " not in data_dict["address"]:
            data_dict["address"] = f"{data_dict['address']} | Mobile: {mobile_val}"
    elif mobile_val and not data_dict.get("address"):
        data_dict["address"] = f"| Mobile: {mobile_val}"

    valid_cols = {c.name for c in MstLedger.__table__.columns}
    for k, v in data_dict.items():
        if k in valid_cols:
            setattr(ledger, k, v)

    ent_type = data_dict.get("enterprise_type")
    udyam_no = data_dict.get("udyam_reg_no")
    if ent_type or udyam_no:
        from datetime import date
        m_stmt = select(MstLedgerMsmeDetail).where(MstLedgerMsmeDetail.ledger_id == ledger.ledger_id)
        m_obj = (await db.execute(m_stmt)).scalars().first()
        if not m_obj:
            m_obj = MstLedgerMsmeDetail(ledger_id=ledger.ledger_id, enterprise_type=ent_type or "Micro", udyam_reg_no=udyam_no, applicable_from=date.today())
            db.add(m_obj)
        else:
            if ent_type: m_obj.enterprise_type = ent_type
            if udyam_no: m_obj.udyam_reg_no = udyam_no

    if bank_details_data is not None:
        from sqlalchemy import delete
        await db.execute(delete(MstLedgerBankDetail).where(MstLedgerBankDetail.ledger_id == ledger.ledger_id))
        for bd in bank_details_data:
            if bd.get("account_number") or bd.get("upi_id") or bd.get("bank_name"):
                b_record = MstLedgerBankDetail(
                    company_id=user.company_id,
                    ledger_id=ledger.ledger_id,
                    **bd
                )
                db.add(b_record)

    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Ledger",
        record_id=ledger.ledger_id,
        action="Alter",
    )
    db.add(sync_item)
        
    await db.commit()
    await db.refresh(ledger)

    # Trigger real-time on-the-run push to Tally Prime
    from app.routers.sync import try_push_ledger_realtime
    await try_push_ledger_realtime(ledger.ledger_id, sync_item.sync_id, "Alter", db)

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

    snapshot = {
        "ledger_id": ledger.ledger_id,
        "company_id": ledger.company_id,
        "name": ledger.name,
        "group_id": ledger.group_id,
        "opening_balance": float(ledger.opening_balance or 0),
        "guid": getattr(ledger, 'guid', None)
    }
    del_audit = DeletedRecordAudit(
        company_id=user.company_id,
        entity_type="Ledger",
        record_id=ledger_id,
        tally_guid=getattr(ledger, 'guid', None) or f"MYTALLY-LEDGER-{ledger_id}",
        entity_identifier=ledger.name,
        deleted_by_user_id=user.user_id,
        tally_sync_status="PENDING",
        snapshot_data=snapshot
    )
    db.add(del_audit)

    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Ledger",
        record_id=ledger.ledger_id,
        action="Delete",
    )
    db.add(sync_item)
    await db.flush()

    # Trigger real-time on-the-run push to Tally Prime
    from app.routers.sync import try_push_ledger_realtime
    tally_ok, tally_status, tally_err = await try_push_ledger_realtime(ledger.ledger_id, sync_item.sync_id, "Delete", db)
        
    await db.delete(ledger)
    await db.commit()
    from app.core.cache import clear_company_cache
    clear_company_cache(user.company_id)
    return {
        "detail": "Ledger deleted successfully in MyTally.",
        "tally_synced": tally_ok,
        "tally_status": tally_status,
        "tally_message": tally_err
    }

@router.get("/{ledger_id}")
async def get_ledger_by_id(
    ledger_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.core.cache import get_cached_response, set_cached_response
    cache_key = f"ledger_detail_{ledger_id}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    ledger_query = await db.execute(
        select(MstLedger).options(selectinload(MstLedger.group)).where(
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

    output = {
        "ledger_id": ledger.ledger_id,
        "company_id": ledger.company_id,
        "group_id": ledger.group_id,
        "group_name": ledger.group.name if ledger.group else None,
        "name": ledger.name,
        "alias": ledger.alias,
        "opening_balance": float(ledger.opening_balance or 0.0),
        "opening_balance_type": ledger.opening_balance_type,
        "gstin": ledger.gstin,
        "address": ledger.address,
        "state": ledger.state,
        "pincode": ledger.pincode,
        "pan_itn": ledger.pan_itn,
        "credit_period_days": ledger.credit_period_days,
        "credit_limit": float(ledger.credit_limit or 0.0) if ledger.credit_limit else None,
    }

    set_cached_response(user.company_id, cache_key, output)
    return output


@router.get("/{ledger_id}/statement")
async def get_ledger_statement(
    ledger_id: int,
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.core.cache import get_cached_response, set_cached_response
    cache_key = f"ledger_statement_{ledger_id}_{from_date}_{to_date}"
    cached = get_cached_response(user.company_id, cache_key)
    if cached is not None:
        return cached

    from app.models.tally_core import MstLedger
    ledger_stmt = select(MstLedger).options(selectinload(MstLedger.group)).where(
        MstLedger.ledger_id == ledger_id,
        MstLedger.company_id == user.company_id
    )
    ledger_res = await db.execute(ledger_stmt)
    ledger = ledger_res.scalars().first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")
        
    addr = ledger.address or ""
    mobile_val = ledger.mobile or ""
    if not mobile_val and addr and " | Mobile: " in addr:
        parts = addr.split(" | Mobile: ")
        addr = parts[0]
        mobile_val = parts[1]

    from datetime import datetime
    from sqlalchemy import text
    parsed_from_date = None
    if from_date:
        try:
            parsed_from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
        except Exception:
            parsed_from_date = None

    # Calculate Individual Party Opening Balance as of from_date
    base_net = (float(ledger.opening_balance) if ledger.opening_balance_type == 'Cr' else -float(ledger.opening_balance)) if ledger.opening_balance else 0.0
    if parsed_from_date:
        prior_stmt = text("""
            SELECT SUM(COALESCE(a.credit_amount, 0) - COALESCE(a.debit_amount, 0)) as prior_net
            FROM tally_sync.voucher_entries a
            JOIN tally_sync.vouchers v ON a.voucher_id = v.voucher_id
            WHERE a.ledger_id = :l_id AND v.voucher_date < :f_dt
        """)
        prior_res = await db.execute(prior_stmt, {"l_id": ledger_id, "f_dt": parsed_from_date})
        prior_val = float(prior_res.scalar() or 0.0)
        net_op = base_net + prior_val
        ind_op_bal = abs(net_op)
        ind_op_type = "Cr" if net_op >= 0 else "Dr"
    else:
        ind_op_bal = float(ledger.opening_balance or 0.0)
        ind_op_type = ledger.opening_balance_type or "Dr"
        
    # Calculate Company-Wide Total Opening Balance as of from_date
    if parsed_from_date:
        tot_op_stmt = text("""
            SELECT 
                SUM(CASE WHEN net_bal < 0 THEN ABS(net_bal) ELSE 0 END) 
                + COALESCE((SELECT SUM(COALESCE(opening_qty, 0) * COALESCE(opening_rate, 0)) FROM tally_sync.stock_items WHERE company_id = :comp_id AND is_active = True), 0) as total_dr,
                SUM(CASE WHEN net_bal > 0 THEN net_bal ELSE 0 END) as total_cr
            FROM (
                SELECT 
                    l.ledger_id,
                    (CASE 
                        WHEN g.name IN ('Sales Accounts', 'Purchase Accounts', 'Direct Expenses', 'Indirect Expenses', 'Direct Incomes', 'Indirect Incomes') THEN 0
                        ELSE (CASE WHEN l.opening_balance_type = 'Cr' THEN COALESCE(l.opening_balance, 0) ELSE -COALESCE(l.opening_balance, 0) END) + COALESCE(SUM(CASE WHEN v.voucher_date < :f_dt THEN (COALESCE(a.credit_amount, 0) - COALESCE(a.debit_amount, 0)) ELSE 0 END), 0)
                     END) as net_bal
                FROM tally_sync.ledgers l
                LEFT JOIN tally_sync.account_groups g ON l.group_id = g.group_id
                LEFT JOIN tally_sync.voucher_entries a ON l.ledger_id = a.ledger_id
                LEFT JOIN tally_sync.vouchers v ON a.voucher_id = v.voucher_id
                WHERE l.company_id = :comp_id AND l.is_active = True
                GROUP BY l.ledger_id, l.opening_balance, l.opening_balance_type, g.name
            ) sub
        """)
        tot_op_res = await db.execute(tot_op_stmt, {"comp_id": user.company_id, "f_dt": parsed_from_date})
    else:
        tot_op_stmt = text("""
            SELECT 
                (SELECT SUM(CASE WHEN opening_balance_type = 'Dr' THEN COALESCE(opening_balance, 0) ELSE 0 END) FROM tally_sync.ledgers WHERE company_id = :comp_id AND is_active = True)
                + COALESCE((SELECT SUM(COALESCE(opening_qty, 0) * COALESCE(opening_rate, 0)) FROM tally_sync.stock_items WHERE company_id = :comp_id AND is_active = True), 0) as total_dr,
                (SELECT SUM(CASE WHEN opening_balance_type = 'Cr' THEN COALESCE(opening_balance, 0) ELSE 0 END) FROM tally_sync.ledgers WHERE company_id = :comp_id AND is_active = True) as total_cr
        """)
        tot_op_res = await db.execute(tot_op_stmt, {"comp_id": user.company_id})

    tot_op_row = tot_op_res.first()
    tot_dr = float(tot_op_row.total_dr or 0.0) if tot_op_row else 0.0
    tot_cr = float(tot_op_row.total_cr or 0.0) if tot_op_row else 0.0
    diff_val = tot_cr - tot_dr
    diff_type = "Cr" if diff_val >= 0 else "Dr"

    ledger_info = {
        "ledger_id": ledger.ledger_id,
        "name": ledger.name,
        "alias_name": ledger.alias_name,
        "parent": ledger.group.name if ledger.group else "Unknown",
        "gstn": ledger.gstin,
        "gst_registration_type": ledger.gst_registration_type,
        "pan_number": ledger.pan_number,
        "address": addr,
        "state": ledger.state,
        "pincode": ledger.pincode,
        "country": ledger.country,
        "phone": ledger.phone,
        "mobile": mobile_val,
        "email": ledger.email,
        "contact_person": ledger.contact_person,
        "opening_balance": ind_op_bal,
        "opening_balance_type": ind_op_type,
        "credit_limit": float(ledger.credit_limit or 0.0) if ledger.credit_limit else None,
        "credit_period_days": ledger.credit_period_days,
        "total_opening_dr": tot_dr,
        "total_opening_cr": tot_cr,
        "total_opening_diff": abs(diff_val),
        "total_opening_diff_type": diff_type,
    }

    from app.models.tally_core import TrnAccounting, TrnVoucher, MstVoucherType
    
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
        
    output = {
        "success": True,
        "ledgerInfo": ledger_info,
        "transactions": transactions,
    }

    set_cached_response(user.company_id, cache_key, output)
    return output
