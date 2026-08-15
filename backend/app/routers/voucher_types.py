from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, update, delete
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.permissions import require_permission, get_current_user
from app.models.portal_core import User, SyncQueue
from app.models.tally_core import (
    MstVoucherType, MstVoucherTypePrefix, MstVoucherTypeSuffix, 
    MstVoucherTypeRestart, MstVoucherTypeClass, MstVoucherTypeClassGroup,
    MstVoucherConfiguration
)
from app.schemas.voucher import (
    VoucherConfigurationResponse, VoucherConfigurationUpdate
)
from app.routers.sync import try_push_voucher_type_realtime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

from datetime import date

# --- Nested Pydantic Schemas ---
class VoucherTypePrefixBase(BaseModel):
    applicable_from: date
    particulars: str

class VoucherTypeSuffixBase(BaseModel):
    applicable_from: date
    particulars: str

class VoucherTypeRestartBase(BaseModel):
    applicable_from: date
    starting_number: int
    periodicity: str

class VoucherTypeClassGroupBase(BaseModel):
    group_name: str
    is_included: bool

class VoucherTypeClassBase(BaseModel):
    class_name: str
    bank_alloc_for: Optional[str] = None
    default_ledger_name: Optional[str] = None
    groups: List[VoucherTypeClassGroupBase] = []

# --- Pydantic Schemas ---
class VoucherTypeBase(BaseModel):
    name: str
    parent_type: Optional[str] = None
    abbreviation: Optional[str] = None
    numbering_method: str = "Automatic"
    prefix: Optional[str] = ""
    suffix: Optional[str] = ""
    next_number: Optional[int] = 1
    prevent_duplicates: Optional[bool] = False
    is_active: Optional[bool] = True
    use_effective_dates: Optional[bool] = False
    allow_zero_valued_transactions: Optional[bool] = False
    is_optional_by_default: Optional[bool] = False
    allow_narration_in_voucher: Optional[bool] = True
    provide_narrations_for_each_ledger: Optional[bool] = False
    print_voucher_after_saving: Optional[bool] = False
    enable_default_accounting_allocations: Optional[bool] = False
    track_additional_costs_for_purchases: Optional[bool] = False
    default_jurisdiction: Optional[str] = None
    default_title_to_print: Optional[str] = None
    numbering_behavior: Optional[str] = None
    width_of_numerical_part: int = 0
    prefill_with_zero: bool = False
    show_unused_vch_nos: bool = False
    whatsapp_voucher_after_saving: bool = False
    
    prefixes: List[VoucherTypePrefixBase] = []
    suffixes: List[VoucherTypeSuffixBase] = []
    restarts: List[VoucherTypeRestartBase] = []
    classes: List[VoucherTypeClassBase] = []

class VoucherTypeCreate(VoucherTypeBase):
    pass

class VoucherTypeUpdate(VoucherTypeBase):
    pass

class VoucherTypeResponse(VoucherTypeBase):
    voucher_type_id: int
    company_id: int
    is_system_defined: bool
    tally_guid: Optional[str] = None

    class Config:
        from_attributes = True

# --- API Endpoints ---

@router.get("", response_model=List[VoucherTypeResponse])
async def list_voucher_types(
    parent_type: Optional[str] = None,
    search: Optional[str] = None,
    user: User = Depends(require_permission("settings", "read")),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.orm import selectinload
    stmt = select(MstVoucherType).options(
        selectinload(MstVoucherType.prefixes),
        selectinload(MstVoucherType.suffixes),
        selectinload(MstVoucherType.restarts),
        selectinload(MstVoucherType.classes).selectinload(MstVoucherTypeClass.groups)
    ).where(MstVoucherType.company_id == user.company_id)
    
    if parent_type:
        stmt = stmt.where(MstVoucherType.parent_type == parent_type)
        
    if search:
        stmt = stmt.where(MstVoucherType.name.ilike(f"%{search}%"))
        
    stmt = stmt.order_by(MstVoucherType.name)
    res = await db.execute(stmt)
    return res.unique().scalars().all()

@router.post("", response_model=VoucherTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_voucher_type(
    req: VoucherTypeCreate,
    user: User = Depends(require_permission("settings", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Check if name already exists
    existing = (await db.execute(
        select(MstVoucherType).where(MstVoucherType.company_id == user.company_id, MstVoucherType.name == req.name)
    )).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Voucher Type '{req.name}' already exists.")

    data = req.model_dump(exclude={'prefixes', 'suffixes', 'restarts', 'classes'})
    new_vt = MstVoucherType(
        company_id=user.company_id,
        is_system_defined=False,
        **data
    )
    db.add(new_vt)
    await db.flush() # To get ID

    for p in req.prefixes:
        db.add(MstVoucherTypePrefix(voucher_type_id=new_vt.voucher_type_id, **p.model_dump()))
    for s in req.suffixes:
        db.add(MstVoucherTypeSuffix(voucher_type_id=new_vt.voucher_type_id, **s.model_dump()))
    for r in req.restarts:
        db.add(MstVoucherTypeRestart(voucher_type_id=new_vt.voucher_type_id, **r.model_dump()))
    for c in req.classes:
        c_data = c.model_dump(exclude={'groups'})
        new_class = MstVoucherTypeClass(voucher_type_id=new_vt.voucher_type_id, **c_data)
        db.add(new_class)
        await db.flush()
        for g in c.groups:
            db.add(MstVoucherTypeClassGroup(class_id=new_class.class_id, **g.model_dump()))

    # Add to sync queue
    sq = SyncQueue(
        company_id=user.company_id,
        record_type="VoucherType",
        record_id=new_vt.voucher_type_id,
        action="Create",
        is_processed=False
    )
    db.add(sq)
    await db.commit()
    await db.refresh(new_vt)

    # Real-time push
    await try_push_voucher_type_realtime(new_vt.voucher_type_id, sq.sync_id, "Create", db)

    # Re-fetch with eager loads for Pydantic response
    from sqlalchemy.orm import selectinload
    stmt = select(MstVoucherType).options(
        selectinload(MstVoucherType.prefixes),
        selectinload(MstVoucherType.suffixes),
        selectinload(MstVoucherType.restarts),
        selectinload(MstVoucherType.classes).selectinload(MstVoucherTypeClass.groups)
    ).where(MstVoucherType.voucher_type_id == new_vt.voucher_type_id)
    
    return (await db.execute(stmt)).scalars().first()

@router.put("/{vt_id}", response_model=VoucherTypeResponse)
async def update_voucher_type(
    vt_id: int,
    req: VoucherTypeUpdate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    vt = (await db.execute(
        select(MstVoucherType).where(MstVoucherType.voucher_type_id == vt_id, MstVoucherType.company_id == user.company_id)
    )).scalars().first()
    
    if not vt:
        raise HTTPException(status_code=404, detail="Voucher Type not found.")

    old_name = vt.name
    
    # Check for name collision
    if req.name != vt.name:
        if vt.is_system_defined:
            raise HTTPException(status_code=400, detail="Cannot rename a system-defined voucher type.")
            
        existing = (await db.execute(
            select(MstVoucherType).where(MstVoucherType.company_id == user.company_id, MstVoucherType.name == req.name)
        )).scalars().first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Voucher Type '{req.name}' already exists.")

    update_data = req.model_dump(exclude_unset=True, exclude={'prefixes', 'suffixes', 'restarts', 'classes'})
    for key, value in update_data.items():
        if vt.is_system_defined and key in ("name", "parent_type", "abbreviation"):
            continue
        setattr(vt, key, value)
        
    # Recreate nested collections
    await db.execute(delete(MstVoucherTypePrefix).where(MstVoucherTypePrefix.voucher_type_id == vt_id))
    await db.execute(delete(MstVoucherTypeSuffix).where(MstVoucherTypeSuffix.voucher_type_id == vt_id))
    await db.execute(delete(MstVoucherTypeRestart).where(MstVoucherTypeRestart.voucher_type_id == vt_id))
    await db.execute(delete(MstVoucherTypeClass).where(MstVoucherTypeClass.voucher_type_id == vt_id))
    
    for p in req.prefixes:
        db.add(MstVoucherTypePrefix(voucher_type_id=vt_id, **p.model_dump()))
    for s in req.suffixes:
        db.add(MstVoucherTypeSuffix(voucher_type_id=vt_id, **s.model_dump()))
    for r in req.restarts:
        db.add(MstVoucherTypeRestart(voucher_type_id=vt_id, **r.model_dump()))
    for c in req.classes:
        c_data = c.model_dump(exclude={'groups'})
        new_class = MstVoucherTypeClass(voucher_type_id=vt_id, **c_data)
        db.add(new_class)
        await db.flush()
        for g in c.groups:
            db.add(MstVoucherTypeClassGroup(class_id=new_class.class_id, **g.model_dump()))

    sq = SyncQueue(
        company_id=user.company_id,
        record_type="VoucherType",
        record_id=vt.voucher_type_id,
        action="Alter",
        is_processed=False
    )
    db.add(sq)
    await db.commit()
    await db.refresh(vt)

    await try_push_voucher_type_realtime(vt.voucher_type_id, sq.sync_id, "Alter", db, old_name=old_name)

    # Re-fetch with eager loads for Pydantic response
    from sqlalchemy.orm import selectinload
    stmt = select(MstVoucherType).options(
        selectinload(MstVoucherType.prefixes),
        selectinload(MstVoucherType.suffixes),
        selectinload(MstVoucherType.restarts),
        selectinload(MstVoucherType.classes).selectinload(MstVoucherTypeClass.groups)
    ).where(MstVoucherType.voucher_type_id == vt.voucher_type_id)
    
    return (await db.execute(stmt)).scalars().first()

@router.delete("/{vt_id}", status_code=status.HTTP_200_OK)
async def delete_voucher_type(
    vt_id: int,
    user: User = Depends(require_permission("settings", "delete")),
    db: AsyncSession = Depends(get_db)
):
    vt = (await db.execute(
        select(MstVoucherType).where(MstVoucherType.voucher_type_id == vt_id, MstVoucherType.company_id == user.company_id)
    )).scalars().first()
    
    if not vt:
        raise HTTPException(status_code=404, detail="Voucher Type not found.")
        
    if vt.is_system_defined:
        raise HTTPException(status_code=400, detail="Cannot delete a system-defined voucher type.")

    vt_name = vt.name
    
    sq = SyncQueue(
        company_id=user.company_id,
        record_type="VoucherType",
        record_id=vt.voucher_type_id,
        action="Delete",
        is_processed=False
    )
    db.add(sq)
    
    await db.delete(vt)
    await db.commit()

    await try_push_voucher_type_realtime(vt_id, sq.sync_id, "Delete", db, deleted_name=vt_name)

    return {
        "message": "Voucher Type deleted successfully",
        "warning": "Tally currently does not support deleting Voucher Types via API. Please manually delete this voucher type in Tally (Gateway of Tally > Alter > Voucher Type > Alt+D) to keep the systems fully synced."
    }

# --- Voucher Configuration Endpoints (F12) ---

@router.get("/{vt_id}/configuration", response_model=VoucherConfigurationResponse)
async def get_voucher_type_configuration(
    vt_id: int,
    user: User = Depends(require_permission("vouchers", "read")),
    db: AsyncSession = Depends(get_db)
):
    vt_stmt = select(MstVoucherType).where(
        MstVoucherType.voucher_type_id == vt_id,
        MstVoucherType.company_id == user.company_id
    )
    vt_res = await db.execute(vt_stmt)
    vt = vt_res.scalars().first()
    if not vt:
        raise HTTPException(status_code=404, detail="Voucher Type not found.")

    cfg_stmt = select(MstVoucherConfiguration).where(
        MstVoucherConfiguration.voucher_type_id == vt_id,
        MstVoucherConfiguration.company_id == user.company_id
    )
    cfg_res = await db.execute(cfg_stmt)
    cfg = cfg_res.scalars().first()

    if cfg:
        return cfg

    # Generate smart defaults based on voucher type
    parent_type = (vt.parent_type or vt.name or "").lower()
    is_purchase = "purchase" in parent_type or "receipt note" in parent_type
    is_sales = "sales" in parent_type or "delivery note" in parent_type
    is_payment_receipt = "payment" in parent_type or "receipt" in parent_type or "contra" in parent_type

    return VoucherConfigurationResponse(
        config_id=None,
        company_id=user.company_id,
        voucher_type_id=vt_id,
        use_cr_dr=True,
        provide_supplier_ref=is_purchase,
        warn_negative_cash=True,
        preallocate_bills=False,
        show_bill_wise_details=True,
        show_bill_wise_multiple_lines=True,
        show_list_of_bills=True,
        show_final_bill_balances=True,
        skip_date_field=False,
        show_inventory_details=(is_sales or is_purchase),
        show_ledger_current_balance=True,
        warn_voucher_number_length=True,
        enable_stripe_view=False,
        use_default_bank_allocations=is_payment_receipt,
        auto_cheque_numbering=True,
        select_cheque_range=True,
        set_ledger_bank_allocations=False,
        print_cheque_after_saving=False,
        show_cheque_details_before_printing=True,
        provide_cash_denominations=("contra" in parent_type),
        provide_buyer_details=is_sales,
        provide_dispatch_order_export=is_sales,
        provide_order_details=is_sales,
        select_common_sales_ledger=is_sales,
        use_vch_no_as_bill_ref=is_sales,
        warn_negative_stock=(is_sales or is_purchase),
        provide_trade_discount=False,
        rate_inclusive_of_tax=False,
        show_party_turnover=False,
        use_default_pg_allocations=False,
        set_ledger_pg_allocations=False,
        provide_party_gst_details=False,
        modify_gst_hsn_details=False,
        send_eway_bill_details=is_sales,
    )

@router.put("/{vt_id}/configuration", response_model=VoucherConfigurationResponse)
async def update_voucher_type_configuration(
    vt_id: int,
    req: VoucherConfigurationUpdate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    vt_stmt = select(MstVoucherType).where(
        MstVoucherType.voucher_type_id == vt_id,
        MstVoucherType.company_id == user.company_id
    )
    vt_res = await db.execute(vt_stmt)
    vt = vt_res.scalars().first()
    if not vt:
        raise HTTPException(status_code=404, detail="Voucher Type not found.")

    cfg_stmt = select(MstVoucherConfiguration).where(
        MstVoucherConfiguration.voucher_type_id == vt_id,
        MstVoucherConfiguration.company_id == user.company_id
    )
    cfg_res = await db.execute(cfg_stmt)
    cfg = cfg_res.scalars().first()

    data = req.model_dump()
    if cfg:
        for k, v in data.items():
            setattr(cfg, k, v)
    else:
        cfg = MstVoucherConfiguration(
            company_id=user.company_id,
            voucher_type_id=vt_id,
            **data
        )
        db.add(cfg)

    # 1. Enqueue SyncQueue item for VoucherType Master synchronization
    sq = SyncQueue(
        company_id=user.company_id,
        record_type="VoucherType",
        record_id=vt_id,
        action="Alter",
        is_processed=False
    )
    db.add(sq)
    await db.commit()
    await db.refresh(cfg)
    await db.refresh(sq)

    logger.info(
        f"\n=======================================================\n"
        f"⚙️ [VOUCHER CONFIGURATION UPDATED]\n"
        f"• Voucher Type: '{vt.name}' (ID: {vt_id}, Parent: {vt.parent_type})\n"
        f"• Accounting: use_cr_dr={cfg.use_cr_dr}, warn_cash={cfg.warn_negative_cash}\n"
        f"• Invoicing: supplier_ref={cfg.provide_supplier_ref}, buyer_details={cfg.provide_buyer_details}\n"
        f"• Inventory & Tax: stock_warn={cfg.warn_negative_stock}, inclusive_tax={cfg.rate_inclusive_of_tax}\n"
        f"• Banking: default_bank={cfg.use_default_bank_allocations}, cash_denominations={cfg.provide_cash_denominations}\n"
        f"• Statutory: eway_bill={cfg.send_eway_bill_details}, party_gst={cfg.provide_party_gst_details}\n"
        f"🔄 Triggering Real-Time Tally Master Sync (sync_id={sq.sync_id})...\n"
        f"=======================================================\n"
    )

    # 2. Attempt Real-time Master Push to Tally
    try:
        await try_push_voucher_type_realtime(vt_id, sq.sync_id, "Alter", db)
    except Exception as e:
        logger.warning(f"Real-time Tally push for VoucherType {vt_id} encountered exception: {e}")

    return cfg
