from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, update, delete
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.permissions import require_permission, get_current_user
from app.models.portal_core import User, SyncQueue
from app.models.tally_core import MstVoucherType, MstVoucherTypePrefix, MstVoucherTypeSuffix, MstVoucherTypeRestart, MstVoucherTypeClass, MstVoucherTypeClassGroup
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

    return {"message": "Voucher Type deleted successfully"}
