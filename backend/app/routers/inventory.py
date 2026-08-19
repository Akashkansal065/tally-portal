from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date

from app.core.database import get_db
from app.core.config import settings
from app.core.permissions import require_permission, get_current_user
from app.models.portal_core import User, DeletedRecordAudit, SyncQueue
from app.models.tally_core import MstUom, MstStockGroup, StockGroupAlias, MstStockCategory, MstGodown, MstStockItem, Batch, MstPriceLevel
from app.models.portal_core import BillOfMaterials, BomItem, SerialNumber
from app.schemas.inventory import (
    UnitOfMeasureCreate, UnitOfMeasureResponse,
    StockGroupCreate, StockGroupResponse,
    StockCategoryCreate, StockCategoryResponse,
    GodownCreate, GodownResponse,
    StockItemCreate, StockItemResponse,
    BillOfMaterialsCreate, BillOfMaterialsResponse,
    BatchCreate, BatchResponse,
    SerialNumberCreate, SerialNumberResponse,
    PriceLevelCreate, PriceLevelResponse,
    PriceLevelRatesBulkCreate
)

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

# --- Unit of Measure (UOM) ---

@router.post("/uoms", response_model=UnitOfMeasureResponse)
async def create_uom(
    req: UnitOfMeasureCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    if not req.is_simple_unit:
        if not req.base_unit_id or not req.additional_unit_id or not req.conversion_factor:
            raise HTTPException(status_code=400, detail="Compound units require base unit, additional unit, and conversion factor.")
        
        # Verify base and additional units are simple
        base_uom = (await db.execute(select(MstUom).where(MstUom.unit_id == req.base_unit_id, MstUom.company_id == user.company_id))).scalars().first()
        add_uom = (await db.execute(select(MstUom).where(MstUom.unit_id == req.additional_unit_id, MstUom.company_id == user.company_id))).scalars().first()
        
        if not base_uom or not add_uom:
            raise HTTPException(status_code=400, detail="Invalid base or additional unit.")
        if not base_uom.is_simple_unit or not add_uom.is_simple_unit:
            raise HTTPException(status_code=400, detail="Base and additional units must be simple units.")
            
        cf_val = req.conversion_factor or 1
        cf_str = str(int(cf_val)) if cf_val % 1 == 0 else str(cf_val)
        req.symbol = req.symbol or f"{base_uom.symbol} of {cf_str} {add_uom.symbol}"
        req.name = req.name or req.symbol
    else:
        if not req.symbol:
            raise HTTPException(status_code=400, detail="Simple units require a symbol.")
        req.name = req.name or req.symbol

    uom = MstUom(
        company_id=user.company_id,
        name=req.name,
        symbol=req.symbol,
        original_name=req.original_name,
        is_simple_unit=req.is_simple_unit,
        decimal_places=req.decimal_places,
        base_unit_id=req.base_unit_id if not req.is_simple_unit else None,
        additional_unit_id=req.additional_unit_id if not req.is_simple_unit else None,
        conversion_factor=req.conversion_factor if not req.is_simple_unit else None
    )
    db.add(uom)
    await db.flush()

    # Sync Queue & Realtime Push to Tally
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Unit",
        record_id=uom.unit_id,
        action="Create",
    )
    db.add(sync_item)
    await db.commit()
    await db.refresh(uom)

    from app.routers.sync import try_push_uom_realtime
    await try_push_uom_realtime(uom.unit_id, sync_item.sync_id, "Create", db)

    return uom

@router.put("/uoms/{unit_id}", response_model=UnitOfMeasureResponse)
async def update_uom(
    unit_id: int,
    req: UnitOfMeasureCreate,
    user: User = Depends(require_permission("inventory", "update")),
    db: AsyncSession = Depends(get_db)
):
    uom = (await db.execute(select(MstUom).where(MstUom.unit_id == unit_id, MstUom.company_id == user.company_id))).scalars().first()
    if not uom:
        raise HTTPException(status_code=404, detail="Unit of measure not found.")
        
    if not req.is_simple_unit:
        if not req.base_unit_id or not req.additional_unit_id or not req.conversion_factor:
            raise HTTPException(status_code=400, detail="Compound units require base unit, additional unit, and conversion factor.")
        
        base_uom = (await db.execute(select(MstUom).where(MstUom.unit_id == req.base_unit_id, MstUom.company_id == user.company_id))).scalars().first()
        add_uom = (await db.execute(select(MstUom).where(MstUom.unit_id == req.additional_unit_id, MstUom.company_id == user.company_id))).scalars().first()
        
        if not base_uom or not add_uom:
            raise HTTPException(status_code=400, detail="Invalid base or additional unit.")
            
        cf_val = req.conversion_factor or 1
        cf_str = str(int(cf_val)) if cf_val % 1 == 0 else str(cf_val)
        req.symbol = req.symbol or f"{base_uom.symbol} of {cf_str} {add_uom.symbol}"
        req.name = req.name or req.symbol
    else:
        req.name = req.name or req.symbol

    uom.name = req.name
    uom.symbol = req.symbol
    uom.original_name = req.original_name
    uom.is_simple_unit = req.is_simple_unit
    uom.decimal_places = req.decimal_places
    uom.base_unit_id = req.base_unit_id if not req.is_simple_unit else None
    uom.additional_unit_id = req.additional_unit_id if not req.is_simple_unit else None
    uom.conversion_factor = req.conversion_factor if not req.is_simple_unit else None
    
    await db.commit()
    await db.refresh(uom)

    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Unit",
        record_id=uom.unit_id,
        action="Alter",
    )
    db.add(sync_item)
    await db.commit()

    from app.routers.sync import try_push_uom_realtime
    await try_push_uom_realtime(uom.unit_id, sync_item.sync_id, "Alter", db)

    return uom

@router.delete("/uoms/{unit_id}")
async def delete_uom(
    unit_id: int,
    user: User = Depends(require_permission("inventory", "delete")),
    db: AsyncSession = Depends(get_db)
):
    uom = (await db.execute(select(MstUom).where(MstUom.unit_id == unit_id, MstUom.company_id == user.company_id))).scalars().first()
    if not uom:
        raise HTTPException(status_code=404, detail="Unit of measure not found.")

    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Unit",
        record_id=unit_id,
        action="Delete",
    )
    db.add(sync_item)
    await db.flush()

    from app.routers.sync import try_push_uom_realtime
    await try_push_uom_realtime(unit_id, sync_item.sync_id, "Delete", db)

    await db.delete(uom)
    await db.commit()
    return {"message": "Unit of measure deleted successfully."}

@router.get("/uoms", response_model=List[UnitOfMeasureResponse])
async def get_uoms(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import func
    stmt = select(MstUom).where(
        MstUom.company_id == user.company_id,
        func.trim(func.lower(MstUom.symbol)) != 'not applicable'
    ).order_by(MstUom.symbol.asc())
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Stock Groups ---

@router.post("/groups", response_model=StockGroupResponse)
async def create_stock_group(
    req: StockGroupCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    if req.parent_id:
        p_query = await db.execute(
            select(MstStockGroup).where(
                MstStockGroup.stock_group_id == req.parent_id,
                MstStockGroup.company_id == user.company_id
            )
        )
        if not p_query.scalars().first():
            raise HTTPException(status_code=400, detail="Parent group not found.")
            
    group = MstStockGroup(
        company_id=user.company_id,
        name=req.name,
        parent_id=req.parent_id,
        is_active=req.is_active
    )
    db.add(group)
    await db.flush()
    
    for alias in req.aliases:
        db.add(StockGroupAlias(stock_group_id=group.stock_group_id, alias=alias))
        
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockGroup",
        record_id=group.stock_group_id,
        action="Create",
    )
    db.add(sync_item)
    await db.commit()

    from app.routers.sync import try_push_stock_group_realtime
    await try_push_stock_group_realtime(group.stock_group_id, sync_item.sync_id, "Create", db)
    
    final = await db.execute(select(MstStockGroup).options(selectinload(MstStockGroup.aliases)).where(MstStockGroup.stock_group_id == group.stock_group_id))
    return final.scalars().first()

@router.put("/groups/{group_id}", response_model=StockGroupResponse)
async def update_stock_group(
    group_id: int,
    req: StockGroupCreate,
    user: User = Depends(require_permission("inventory", "update")),
    db: AsyncSession = Depends(get_db)
):
    group = (await db.execute(select(MstStockGroup).options(selectinload(MstStockGroup.aliases)).where(MstStockGroup.stock_group_id == group_id, MstStockGroup.company_id == user.company_id))).scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Stock group not found.")
        
    if req.parent_id:
        if req.parent_id == group_id:
            raise HTTPException(status_code=400, detail="Group cannot be its own parent.")
        p_query = await db.execute(select(MstStockGroup).where(MstStockGroup.stock_group_id == req.parent_id, MstStockGroup.company_id == user.company_id))
        if not p_query.scalars().first():
            raise HTTPException(status_code=400, detail="Parent group not found.")
            
    group.name = req.name
    group.parent_id = req.parent_id
    group.is_active = req.is_active
    
    # Update aliases
    await db.execute(StockGroupAlias.__table__.delete().where(StockGroupAlias.stock_group_id == group_id))
    for alias in req.aliases:
        db.add(StockGroupAlias(stock_group_id=group.stock_group_id, alias=alias))
        
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockGroup",
        record_id=group_id,
        action="Alter",
    )
    db.add(sync_item)
    await db.commit()

    from app.routers.sync import try_push_stock_group_realtime
    await try_push_stock_group_realtime(group_id, sync_item.sync_id, "Alter", db)
    
    final = await db.execute(select(MstStockGroup).options(selectinload(MstStockGroup.aliases)).where(MstStockGroup.stock_group_id == group.stock_group_id))
    return final.scalars().first()

@router.delete("/groups/{group_id}")
async def delete_stock_group(
    group_id: int,
    user: User = Depends(require_permission("inventory", "delete")),
    db: AsyncSession = Depends(get_db)
):
    group = (await db.execute(select(MstStockGroup).where(MstStockGroup.stock_group_id == group_id, MstStockGroup.company_id == user.company_id))).scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Stock group not found.")

    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockGroup",
        record_id=group_id,
        action="Delete",
    )
    db.add(sync_item)
    await db.flush()

    from app.routers.sync import try_push_stock_group_realtime
    await try_push_stock_group_realtime(group_id, sync_item.sync_id, "Delete", db)

    await db.delete(group)
    await db.commit()
    return {"message": "Stock group deleted successfully."}

@router.get("/groups", response_model=List[StockGroupResponse])
async def get_stock_groups(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MstStockGroup).options(selectinload(MstStockGroup.aliases)).where(MstStockGroup.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Stock Categories ---

@router.post("/categories", response_model=StockCategoryResponse)
async def create_stock_category(
    req: StockCategoryCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    if req.parent_id:
        p_query = await db.execute(
            select(MstStockCategory).where(
                MstStockCategory.stock_category_id == req.parent_id,
                MstStockCategory.company_id == user.company_id
            )
        )
        if not p_query.scalars().first():
            raise HTTPException(status_code=400, detail="Parent category not found.")
            
    cat = MstStockCategory(
        company_id=user.company_id,
        name=req.name,
        parent_id=req.parent_id,
        is_active=req.is_active
    )
    db.add(cat)
    await db.flush()

    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockCategory",
        record_id=cat.stock_category_id,
        action="Create",
    )
    db.add(sync_item)
    await db.commit()
    await db.refresh(cat)

    from app.routers.sync import try_push_stock_category_realtime
    await try_push_stock_category_realtime(cat.stock_category_id, sync_item.sync_id, "Create", db)

    return cat

@router.put("/categories/{category_id}", response_model=StockCategoryResponse)
async def update_stock_category(
    category_id: int,
    req: StockCategoryCreate,
    user: User = Depends(require_permission("inventory", "update")),
    db: AsyncSession = Depends(get_db)
):
    cat = (await db.execute(select(MstStockCategory).where(MstStockCategory.stock_category_id == category_id, MstStockCategory.company_id == user.company_id))).scalars().first()
    if not cat:
        raise HTTPException(status_code=404, detail="Stock category not found.")
        
    if req.parent_id:
        if req.parent_id == category_id:
            raise HTTPException(status_code=400, detail="Category cannot be its own parent.")
        p_query = await db.execute(select(MstStockCategory).where(MstStockCategory.stock_category_id == req.parent_id, MstStockCategory.company_id == user.company_id))
        if not p_query.scalars().first():
            raise HTTPException(status_code=400, detail="Parent category not found.")
            
    cat.name = req.name
    cat.parent_id = req.parent_id
    cat.is_active = req.is_active
    
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockCategory",
        record_id=category_id,
        action="Alter",
    )
    db.add(sync_item)
    await db.commit()
    await db.refresh(cat)

    from app.routers.sync import try_push_stock_category_realtime
    await try_push_stock_category_realtime(category_id, sync_item.sync_id, "Alter", db)

    return cat

@router.delete("/categories/{category_id}")
async def delete_stock_category(
    category_id: int,
    user: User = Depends(require_permission("inventory", "delete")),
    db: AsyncSession = Depends(get_db)
):
    cat = (await db.execute(select(MstStockCategory).where(MstStockCategory.stock_category_id == category_id, MstStockCategory.company_id == user.company_id))).scalars().first()
    if not cat:
        raise HTTPException(status_code=404, detail="Stock category not found.")

    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockCategory",
        record_id=category_id,
        action="Delete",
    )
    db.add(sync_item)
    await db.flush()

    from app.routers.sync import try_push_stock_category_realtime
    await try_push_stock_category_realtime(category_id, sync_item.sync_id, "Delete", db)

    await db.delete(cat)
    await db.commit()
    return {"message": "Stock category deleted successfully."}

@router.get("/categories", response_model=List[StockCategoryResponse])
async def get_stock_categories(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MstStockCategory).where(MstStockCategory.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Godowns ---

@router.post("/godowns", response_model=GodownResponse)
async def create_godown(
    req: GodownCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    if req.parent_id:
        p_query = await db.execute(
            select(MstGodown).where(
                MstGodown.godown_id == req.parent_id,
                MstGodown.company_id == user.company_id
            )
        )
        if not p_query.scalars().first():
            raise HTTPException(status_code=400, detail="Parent godown not found.")
            
    g = MstGodown(
        company_id=user.company_id,
        name=req.name,
        address=req.address,
        parent_id=req.parent_id,
        is_active=req.is_active,
        contact_person=req.contact_person,
        phone=req.phone
    )
    db.add(g)
    await db.flush()

    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Godown",
        record_id=g.godown_id,
        action="Create",
    )
    db.add(sync_item)
    await db.commit()
    await db.refresh(g)

    from app.routers.sync import try_push_godown_realtime
    await try_push_godown_realtime(g.godown_id, sync_item.sync_id, "Create", db)

    return g

@router.put("/godowns/{godown_id}", response_model=GodownResponse)
async def update_godown(
    godown_id: int,
    req: GodownCreate,
    user: User = Depends(require_permission("inventory", "update")),
    db: AsyncSession = Depends(get_db)
):
    g = (await db.execute(select(MstGodown).where(MstGodown.godown_id == godown_id, MstGodown.company_id == user.company_id))).scalars().first()
    if not g:
        raise HTTPException(status_code=404, detail="Godown not found.")
        
    if req.parent_id:
        if req.parent_id == godown_id:
            raise HTTPException(status_code=400, detail="Godown cannot be its own parent.")
        p_query = await db.execute(select(MstGodown).where(MstGodown.godown_id == req.parent_id, MstGodown.company_id == user.company_id))
        if not p_query.scalars().first():
            raise HTTPException(status_code=400, detail="Parent godown not found.")
            
    g.name = req.name
    g.address = req.address
    g.parent_id = req.parent_id
    g.is_active = req.is_active
    g.contact_person = req.contact_person
    g.phone = req.phone
    
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Godown",
        record_id=godown_id,
        action="Alter",
    )
    db.add(sync_item)
    await db.commit()
    await db.refresh(g)

    from app.routers.sync import try_push_godown_realtime
    await try_push_godown_realtime(godown_id, sync_item.sync_id, "Alter", db)

    return g

@router.delete("/godowns/{godown_id}")
async def delete_godown(
    godown_id: int,
    user: User = Depends(require_permission("inventory", "delete")),
    db: AsyncSession = Depends(get_db)
):
    g = (await db.execute(select(MstGodown).where(MstGodown.godown_id == godown_id, MstGodown.company_id == user.company_id))).scalars().first()
    if not g:
        raise HTTPException(status_code=404, detail="Godown not found.")

    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="Godown",
        record_id=godown_id,
        action="Delete",
    )
    db.add(sync_item)
    await db.flush()

    from app.routers.sync import try_push_godown_realtime
    await try_push_godown_realtime(godown_id, sync_item.sync_id, "Delete", db)

    await db.delete(g)
    await db.commit()
    return {"message": "Godown deleted successfully."}

@router.get("/godowns", response_model=List[GodownResponse])
async def get_godowns(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MstGodown).where(MstGodown.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Price Levels ---

@router.post("/price-levels", response_model=PriceLevelResponse)
async def create_price_level(
    req: PriceLevelCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    pl = MstPriceLevel(company_id=user.company_id, name=req.name, is_active=req.is_active)
    db.add(pl)
    await db.commit()
    await db.refresh(pl)
    return pl

@router.put("/price-levels/{level_id}", response_model=PriceLevelResponse)
async def update_price_level(
    level_id: int,
    req: PriceLevelCreate,
    user: User = Depends(require_permission("inventory", "update")),
    db: AsyncSession = Depends(get_db)
):
    pl = (await db.execute(select(MstPriceLevel).where(MstPriceLevel.price_level_id == level_id, MstPriceLevel.company_id == user.company_id))).scalars().first()
    if not pl:
        raise HTTPException(status_code=404, detail="Price level not found.")
    pl.name = req.name
    pl.is_active = req.is_active
    await db.commit()
    await db.refresh(pl)
    return pl

@router.delete("/price-levels/{level_id}")
async def delete_price_level(
    level_id: int,
    user: User = Depends(require_permission("inventory", "delete")),
    db: AsyncSession = Depends(get_db)
):
    pl = (await db.execute(select(MstPriceLevel).where(MstPriceLevel.price_level_id == level_id, MstPriceLevel.company_id == user.company_id))).scalars().first()
    if not pl:
        raise HTTPException(status_code=404, detail="Price level not found.")
    await db.delete(pl)
    await db.commit()
    return {"message": "Price level deleted successfully."}

@router.get("/price-levels", response_model=List[PriceLevelResponse])
async def get_price_levels(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MstPriceLevel).where(MstPriceLevel.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/price-levels/{level_id}/rates")
async def save_price_level_rates(
    level_id: int,
    req: PriceLevelRatesBulkCreate,
    user: User = Depends(require_permission("inventory", "update")),
    db: AsyncSession = Depends(get_db)
):
    pl = (await db.execute(select(MstPriceLevel).where(MstPriceLevel.price_level_id == level_id, MstPriceLevel.company_id == user.company_id))).scalars().first()
    if not pl:
        raise HTTPException(status_code=404, detail="Price level not found.")

    if not req.rates:
        return {"message": "No rates to save."}

    item_ids = list(set([r.stock_item_id for r in req.rates]))
    
    # Delete existing rates for these items, this level, and this date
    await db.execute(
        StockItemPriceLevelRate.__table__.delete().where(
            StockItemPriceLevelRate.stock_item_id.in_(item_ids),
            StockItemPriceLevelRate.price_level_id == level_id,
            StockItemPriceLevelRate.effective_from == req.effective_from
        )
    )
    
    # Insert new rates
    for r in req.rates:
        db.add(StockItemPriceLevelRate(
            stock_item_id=r.stock_item_id,
            price_level_id=level_id,
            effective_from=req.effective_from,
            qty_from=r.qty_from,
            qty_to=r.qty_to,
            rate=r.rate,
            discount_percent=r.discount_percent
        ))
        
    await db.commit()
    return {"message": "Rates saved successfully."}

# --- Stock Items ---

from app.models.tally_core import StockItemAlias, StockItemPriceList, StockItemOpeningBalance, StockItemBOM, StockItemBOMComponent, StockItemPriceLevelRate

@router.post("/items", response_model=StockItemResponse)
async def create_stock_item(
    req: StockItemCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Verify or resolve UOM
    unit_id = req.unit_id
    if unit_id:
        uom_query = await db.execute(
            select(MstUom).where(
                MstUom.unit_id == unit_id,
                MstUom.company_id == user.company_id
            )
        )
        if not uom_query.scalars().first():
            raise HTTPException(status_code=400, detail="Unit of Measure not found.")
    else:
        # Resolve default UOM for company or create standard 'nos'
        uom_query = await db.execute(
            select(MstUom).where(MstUom.company_id == user.company_id)
        )
        first_uom = uom_query.scalars().first()
        if first_uom:
            unit_id = first_uom.unit_id
        else:
            new_uom = MstUom(company_id=user.company_id, name="nos", symbol="nos")
            db.add(new_uom)
            await db.flush()
            unit_id = new_uom.unit_id
        
    if req.alt_unit_id:
        alt_uom_query = await db.execute(select(MstUom).where(MstUom.unit_id == req.alt_unit_id, MstUom.company_id == user.company_id))
        if not alt_uom_query.scalars().first():
            raise HTTPException(status_code=400, detail="Alternate Unit of Measure not found.")
        
    # Verify group if provided
    if req.stock_group_id:
        g_query = await db.execute(
            select(MstStockGroup).where(
                MstStockGroup.stock_group_id == req.stock_group_id,
                MstStockGroup.company_id == user.company_id
            )
        )
        if not g_query.scalars().first():
            raise HTTPException(status_code=400, detail="Stock group not found.")
            
    # Verify category if provided
    if req.stock_category_id:
        c_query = await db.execute(
            select(MstStockCategory).where(
                MstStockCategory.stock_category_id == req.stock_category_id,
                MstStockCategory.company_id == user.company_id
            )
        )
        if not c_query.scalars().first():
            raise HTTPException(status_code=400, detail="Stock category not found.")
            
    item = MstStockItem(
        company_id=user.company_id,
        name=req.name,
        stock_group_id=req.stock_group_id,
        stock_category_id=req.stock_category_id,
        unit_id=unit_id,
        alt_unit_id=req.alt_unit_id,
        alt_unit_conversion=req.alt_unit_conversion,
        description=req.description,
        standard_cost_price=req.standard_cost_price,
        standard_selling_price=req.standard_selling_price,
        image_url=req.image_url,
        hsn_code=req.hsn_code,
        gst_rate_percent=req.gst_rate_percent,
        opening_qty=req.opening_qty,
        opening_rate=req.opening_rate,
        closing_qty=req.opening_qty or 0,
        closing_rate=req.opening_rate or 0,
        closing_value=(req.opening_qty or 0) * (req.opening_rate or 0),
        reorder_level=req.reorder_level,
        minimum_order_qty=req.minimum_order_qty,
        tracking_type=req.tracking_type,
        shelf_life_days=req.shelf_life_days,
        is_active=req.is_active
    )
    db.add(item)
    await db.flush()
    
    for alias in req.aliases:
        db.add(StockItemAlias(stock_item_id=item.stock_item_id, alias=alias.alias, alias_type=alias.alias_type))
    
    for pl in req.price_lists:
        db.add(StockItemPriceList(stock_item_id=item.stock_item_id, price_type=pl.price_type, effective_from=pl.effective_from, rate=pl.rate))
        
    for ob in req.opening_balances:
        db.add(StockItemOpeningBalance(stock_item_id=item.stock_item_id, godown_id=ob.godown_id, batch_name=ob.batch_name, quantity=ob.quantity, rate=ob.rate, amount=ob.amount))
    
    for bom_req in req.boms:
        bom = StockItemBOM(stock_item_id=item.stock_item_id, bom_name=bom_req.bom_name, unit_of_manufacture=bom_req.unit_of_manufacture, is_active=bom_req.is_active)
        db.add(bom)
        await db.flush()
        for comp in bom_req.components:
            db.add(StockItemBOMComponent(bom_id=bom.bom_id, component_item_id=comp.component_item_id, godown_id=comp.godown_id, quantity=comp.quantity, component_type=comp.component_type))
            
    for plr in req.price_level_rates:
        db.add(StockItemPriceLevelRate(stock_item_id=item.stock_item_id, price_level_id=plr.price_level_id, effective_from=plr.effective_from, qty_from=plr.qty_from, qty_to=plr.qty_to, rate=plr.rate, discount_percent=plr.discount_percent))

    # Sync Queue & Realtime Push to Tally
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockItem",
        record_id=item.stock_item_id,
        action="Create",
    )
    db.add(sync_item)
    await db.commit()
    
    from app.routers.sync import try_push_stock_item_realtime
    await try_push_stock_item_realtime(item.stock_item_id, sync_item.sync_id, "Create", db)
    
    final = await db.execute(
        select(MstStockItem)
        .options(
            selectinload(MstStockItem.unit),
            selectinload(MstStockItem.group),
            selectinload(MstStockItem.aliases),
            selectinload(MstStockItem.price_lists),
            selectinload(MstStockItem.opening_balances),
            selectinload(MstStockItem.boms).selectinload(StockItemBOM.components).selectinload(StockItemBOMComponent.component_item),
            selectinload(MstStockItem.price_level_rates)
        )
        .where(MstStockItem.stock_item_id == item.stock_item_id)
    )
    res_item = final.scalars().first()
    
    # We need to build the response dict to match StockItemResponse
    res_dict = {
        "stock_item_id": res_item.stock_item_id,
        "item_id": res_item.stock_item_id,
        "company_id": res_item.company_id,
        "name": res_item.name,
        "stock_group_id": res_item.stock_group_id,
        "stock_category_id": res_item.stock_category_id,
        "unit_id": res_item.unit_id,
        "alt_unit_id": res_item.alt_unit_id,
        "alt_unit_conversion": res_item.alt_unit_conversion,
        "description": res_item.description,
        "standard_cost_price": res_item.standard_cost_price,
        "standard_selling_price": res_item.standard_selling_price,
        "image_url": res_item.image_url,
        "hsn_code": res_item.hsn_code,
        "gst_rate_percent": res_item.gst_rate_percent,
        "opening_qty": res_item.opening_qty,
        "opening_rate": res_item.opening_rate,
        "reorder_level": res_item.reorder_level,
        "minimum_order_qty": res_item.minimum_order_qty,
        "tracking_type": res_item.tracking_type,
        "shelf_life_days": res_item.shelf_life_days,
        "is_active": res_item.is_active,
        "group_name": res_item.group.name if res_item.group else None,
        "uom": res_item.unit.symbol if res_item.unit else None,
        "closing_balance": res_item.closing_qty,
        "closing_rate": res_item.closing_rate,
        "closing_value": res_item.closing_value,
        "aliases": res_item.aliases,
        "price_lists": res_item.price_lists,
        "opening_balances": res_item.opening_balances,
        "boms": [{
            "bom_id": b.bom_id,
            "bom_name": b.bom_name,
            "unit_of_manufacture": b.unit_of_manufacture,
            "is_active": b.is_active,
            "components": [{
                "id": c.id,
                "component_item_id": c.component_item_id,
                "component_name": c.component_item.name if c.component_item else None,
                "godown_id": c.godown_id,
                "quantity": c.quantity,
                "component_type": c.component_type
            } for c in b.components]
        } for b in res_item.boms],
        "price_level_rates": res_item.price_level_rates
    }
    return StockItemResponse(**res_dict)

@router.get("/items/{item_id}", response_model=StockItemResponse)
async def get_stock_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(MstStockItem)
        .options(
            selectinload(MstStockItem.unit),
            selectinload(MstStockItem.group),
            selectinload(MstStockItem.aliases),
            selectinload(MstStockItem.price_lists),
            selectinload(MstStockItem.opening_balances),
            selectinload(MstStockItem.boms).selectinload(StockItemBOM.components).selectinload(StockItemBOMComponent.component_item),
            selectinload(MstStockItem.price_level_rates)
        )
        .where(MstStockItem.stock_item_id == item_id, MstStockItem.company_id == user.company_id)
    )
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Stock item not found.")
        
    res_dict = {
        "stock_item_id": item.stock_item_id,
        "item_id": item.stock_item_id,
        "company_id": item.company_id,
        "name": item.name,
        "stock_group_id": item.stock_group_id,
        "stock_category_id": item.stock_category_id,
        "unit_id": item.unit_id,
        "alt_unit_id": item.alt_unit_id,
        "alt_unit_conversion": item.alt_unit_conversion,
        "description": item.description,
        "standard_cost_price": item.standard_cost_price,
        "standard_selling_price": item.standard_selling_price,
        "image_url": item.image_url,
        "hsn_code": item.hsn_code,
        "gst_rate_percent": item.gst_rate_percent,
        "opening_qty": item.opening_qty,
        "opening_rate": item.opening_rate,
        "reorder_level": item.reorder_level,
        "minimum_order_qty": item.minimum_order_qty,
        "tracking_type": item.tracking_type,
        "shelf_life_days": item.shelf_life_days,
        "is_active": item.is_active,
        "group_name": item.group.name if item.group else None,
        "uom": item.unit.symbol if item.unit else None,
        "closing_balance": item.closing_qty,
        "closing_rate": item.closing_rate,
        "closing_value": item.closing_value,
        "aliases": item.aliases,
        "price_lists": item.price_lists,
        "opening_balances": item.opening_balances,
        "boms": [{
            "bom_id": b.bom_id,
            "bom_name": b.bom_name,
            "unit_of_manufacture": b.unit_of_manufacture,
            "is_active": b.is_active,
            "components": [{
                "id": c.id,
                "component_item_id": c.component_item_id,
                "component_name": c.component_item.name if c.component_item else None,
                "godown_id": c.godown_id,
                "quantity": c.quantity,
                "component_type": c.component_type
            } for c in b.components]
        } for b in item.boms],
        "price_level_rates": item.price_level_rates
    }
    return StockItemResponse(**res_dict)

@router.put("/items/{item_id}", response_model=StockItemResponse)
async def update_stock_item(
    item_id: int,
    req: StockItemCreate,
    user: User = Depends(require_permission("inventory", "update")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(MstStockItem)
        .options(
            selectinload(MstStockItem.aliases),
            selectinload(MstStockItem.price_lists),
            selectinload(MstStockItem.opening_balances),
            selectinload(MstStockItem.boms),
            selectinload(MstStockItem.price_level_rates)
        )
        .where(MstStockItem.stock_item_id == item_id, MstStockItem.company_id == user.company_id)
    )
    res = await db.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Stock item not found.")
        
    # Validations similar to create
    uom_query = await db.execute(select(MstUom).where(MstUom.unit_id == req.unit_id, MstUom.company_id == user.company_id))
    if not uom_query.scalars().first(): raise HTTPException(status_code=400, detail="Unit of Measure not found.")
    
    if req.stock_group_id:
        g_query = await db.execute(select(MstStockGroup).where(MstStockGroup.stock_group_id == req.stock_group_id, MstStockGroup.company_id == user.company_id))
        if not g_query.scalars().first(): raise HTTPException(status_code=400, detail="Stock group not found.")
            
    if req.stock_category_id:
        c_query = await db.execute(select(MstStockCategory).where(MstStockCategory.stock_category_id == req.stock_category_id, MstStockCategory.company_id == user.company_id))
        if not c_query.scalars().first(): raise HTTPException(status_code=400, detail="Stock category not found.")
        
    item.name = req.name
    item.stock_group_id = req.stock_group_id
    item.stock_category_id = req.stock_category_id
    item.unit_id = req.unit_id
    item.alt_unit_id = req.alt_unit_id
    item.alt_unit_conversion = req.alt_unit_conversion
    item.description = req.description
    item.standard_cost_price = req.standard_cost_price
    item.standard_selling_price = req.standard_selling_price
    item.image_url = req.image_url
    item.hsn_code = req.hsn_code
    item.gst_rate_percent = req.gst_rate_percent
    item.opening_qty = req.opening_qty
    item.opening_rate = req.opening_rate
    item.reorder_level = req.reorder_level
    item.minimum_order_qty = req.minimum_order_qty
    item.tracking_type = req.tracking_type
    item.shelf_life_days = req.shelf_life_days
    item.is_active = req.is_active
    
    # Update nested records
    await db.execute(StockItemAlias.__table__.delete().where(StockItemAlias.stock_item_id == item_id))
    for alias in req.aliases: db.add(StockItemAlias(stock_item_id=item_id, alias=alias.alias, alias_type=alias.alias_type))
        
    await db.execute(StockItemPriceList.__table__.delete().where(StockItemPriceList.stock_item_id == item_id))
    for pl in req.price_lists: db.add(StockItemPriceList(stock_item_id=item_id, price_type=pl.price_type, effective_from=pl.effective_from, rate=pl.rate))
        
    await db.execute(StockItemOpeningBalance.__table__.delete().where(StockItemOpeningBalance.stock_item_id == item_id))
    for ob in req.opening_balances: db.add(StockItemOpeningBalance(stock_item_id=item_id, godown_id=ob.godown_id, batch_name=ob.batch_name, quantity=ob.quantity, rate=ob.rate, amount=ob.amount))
    
    await db.execute(StockItemBOM.__table__.delete().where(StockItemBOM.stock_item_id == item_id))
    for bom_req in req.boms:
        bom = StockItemBOM(stock_item_id=item_id, bom_name=bom_req.bom_name, unit_of_manufacture=bom_req.unit_of_manufacture, is_active=bom_req.is_active)
        db.add(bom)
        await db.flush()
        for comp in bom_req.components:
            db.add(StockItemBOMComponent(bom_id=bom.bom_id, component_item_id=comp.component_item_id, godown_id=comp.godown_id, quantity=comp.quantity, component_type=comp.component_type))
            
    await db.execute(StockItemPriceLevelRate.__table__.delete().where(StockItemPriceLevelRate.stock_item_id == item_id))
    for plr in req.price_level_rates:
        db.add(StockItemPriceLevelRate(
            stock_item_id=item_id,
            price_level_id=plr.price_level_id,
            effective_from=plr.effective_from,
            qty_from=plr.qty_from,
            qty_to=plr.qty_to,
            rate=plr.rate,
            discount_percent=plr.discount_percent
        ))

    # Sync Queue & Realtime Push to Tally
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockItem",
        record_id=item_id,
        action="Alter",
    )
    db.add(sync_item)
    await db.commit()
    
    from app.routers.sync import try_push_stock_item_realtime
    await try_push_stock_item_realtime(item_id, sync_item.sync_id, "Alter", db)
    
    final = await db.execute(
        select(MstStockItem)
        .options(
            selectinload(MstStockItem.unit),
            selectinload(MstStockItem.group),
            selectinload(MstStockItem.aliases),
            selectinload(MstStockItem.price_lists),
            selectinload(MstStockItem.opening_balances),
            selectinload(MstStockItem.boms).selectinload(StockItemBOM.components).selectinload(StockItemBOMComponent.component_item),
            selectinload(MstStockItem.price_level_rates)
        )
        .where(MstStockItem.stock_item_id == item_id)
    )
    res_item = final.scalars().first()
    
    res_dict = {
        "stock_item_id": res_item.stock_item_id,
        "item_id": res_item.stock_item_id,
        "company_id": res_item.company_id,
        "name": res_item.name,
        "stock_group_id": res_item.stock_group_id,
        "stock_category_id": res_item.stock_category_id,
        "unit_id": res_item.unit_id,
        "alt_unit_id": res_item.alt_unit_id,
        "alt_unit_conversion": res_item.alt_unit_conversion,
        "description": res_item.description,
        "standard_cost_price": res_item.standard_cost_price,
        "standard_selling_price": res_item.standard_selling_price,
        "image_url": res_item.image_url,
        "hsn_code": res_item.hsn_code,
        "gst_rate_percent": res_item.gst_rate_percent,
        "opening_qty": res_item.opening_qty,
        "opening_rate": res_item.opening_rate,
        "reorder_level": res_item.reorder_level,
        "minimum_order_qty": res_item.minimum_order_qty,
        "tracking_type": res_item.tracking_type,
        "shelf_life_days": res_item.shelf_life_days,
        "is_active": res_item.is_active,
        "group_name": res_item.group.name if res_item.group else None,
        "uom": res_item.unit.symbol if res_item.unit else None,
        "closing_balance": res_item.closing_qty,
        "closing_rate": res_item.closing_rate,
        "closing_value": res_item.closing_value,
        "aliases": res_item.aliases,
        "price_lists": res_item.price_lists,
        "opening_balances": res_item.opening_balances,
        "boms": [{
            "bom_id": b.bom_id,
            "bom_name": b.bom_name,
            "unit_of_manufacture": b.unit_of_manufacture,
            "is_active": b.is_active,
            "components": [{
                "id": c.id,
                "component_item_id": c.component_item_id,
                "component_name": c.component_item.name if c.component_item else None,
                "godown_id": c.godown_id,
                "quantity": c.quantity,
                "component_type": c.component_type
            } for c in res_item.boms]
        } for b in res_item.boms],
        "price_level_rates": res_item.price_level_rates
    }
    return StockItemResponse(**res_dict)

@router.delete("/items/{item_id}")
async def delete_stock_item(
    item_id: int,
    user: User = Depends(require_permission("inventory", "delete")),
    db: AsyncSession = Depends(get_db)
):
    item = (await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == item_id, MstStockItem.company_id == user.company_id))).scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Stock item not found.")

    snapshot = {
        "stock_item_id": item.stock_item_id,
        "company_id": item.company_id,
        "name": item.name,
        "group_id": item.group_id,
        "unit_id": item.unit_id,
        "closing_qty": float(item.closing_qty or 0)
    }
    del_audit = DeletedRecordAudit(
        company_id=user.company_id,
        entity_type="StockItem",
        record_id=item_id,
        tally_guid=getattr(item, 'guid', None) or f"MYTALLY-ITEM-{item_id}",
        entity_identifier=item.name,
        deleted_by_user_id=user.user_id,
        tally_sync_status="PENDING",
        snapshot_data=snapshot
    )
    db.add(del_audit)

    sync_item = SyncQueue(
        company_id=user.company_id,
        record_type="StockItem",
        record_id=item_id,
        action="Delete",
    )
    db.add(sync_item)
    await db.flush()

    from app.routers.sync import try_push_stock_item_realtime
    tally_ok, tally_status, tally_err = await try_push_stock_item_realtime(item_id, sync_item.sync_id, "Delete", db)

    await db.delete(item)
    await db.commit()
    return {
        "message": "Stock item deleted successfully in MyTally.",
        "tally_synced": tally_ok,
        "tally_status": tally_status,
        "tally_message": tally_err
    }

@router.get("/items", response_model=List[StockItemResponse])
async def get_stock_items(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from decimal import Decimal
    stmt = (
        select(MstStockItem)
        .options(selectinload(MstStockItem.unit), selectinload(MstStockItem.group))
        .where(MstStockItem.company_id == user.company_id)
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    # Fetch all stock entries for this company
    from app.models.tally_core import TrnInventory
    from app.models.tally_core import TrnVoucher
    entry_stmt = (
        select(TrnInventory)
        .join(TrnVoucher, TrnInventory.voucher_id == TrnVoucher.voucher_id)
        .where(TrnVoucher.company_id == user.company_id)
    )
    entry_res = await db.execute(entry_stmt)
    entries = entry_res.scalars().all()

    # Group entries by stock_item_id
    entries_by_item = {}
    for entry in entries:
        if entry.stock_item_id not in entries_by_item:
            entries_by_item[entry.stock_item_id] = []
        entries_by_item[entry.stock_item_id].append(entry)

    out = []
    for item in items:
        in_qty = Decimal("0.000")
        in_val = Decimal("0.00")
        out_qty = Decimal("0.000")
        out_val = Decimal("0.00")

        item_entries = entries_by_item.get(item.stock_item_id, [])
        for entry in item_entries:
            if entry.is_inward:
                in_qty += entry.quantity
                in_val += entry.amount
            else:
                out_qty += entry.quantity
                out_val += entry.amount

        # Weighted average rate calculation (Opening + Inward)
        total_in_qty = item.opening_qty + in_qty
        total_in_val = (item.opening_qty * item.opening_rate) + in_val
        avg_cost = Decimal("0.00")
        if total_in_qty > 0:
            avg_cost = total_in_val / total_in_qty

        cons_value = out_qty * avg_cost
        gp_value = out_val - cons_value
        gp_percent = Decimal("0.00")
        if out_val > 0:
            gp_percent = (gp_value / out_val) * 100

        # Construct response object
        out.append(StockItemResponse(
            stock_item_id=item.stock_item_id,
            item_id=item.stock_item_id,
            company_id=item.company_id,
            name=item.name,
            stock_group_id=item.stock_group_id,
            stock_category_id=item.stock_category_id,
            unit_id=item.unit_id,
            hsn_code=item.hsn_code,
            gst_rate_percent=item.gst_rate_percent,
            opening_qty=item.opening_qty,
            opening_rate=item.opening_rate,
            reorder_level=item.reorder_level,
            tracking_type=item.tracking_type,
            shelf_life_days=item.shelf_life_days,
            is_active=item.is_active,
            group_name=item.group_name,
            uom=item.uom,
            closing_balance=item.closing_qty,
            closing_rate=item.closing_rate,
            closing_value=item.closing_value,
            inward_qty=in_qty,
            inward_value=in_val,
            outward_qty=out_qty,
            outward_value=out_val,
            cons_value=cons_value,
            gp_value=gp_value,
            gp_percent=gp_percent
        ))

    return out


@router.get("/items/{item_id}/vouchers")
async def get_item_vouchers(
    item_id: int,
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Return individual stock transaction vouchers for a specific stock item,
    including party name (Sundry Debtors / Sundry Creditors ledger on the voucher)."""
    from sqlalchemy import text as sa_text
    sql = sa_text(f"""
        SELECT
            se.stock_entry_id,
            se.quantity,
            se.amount,
            se.is_inward,
            v.voucher_id,
            v.voucher_number,
            v.voucher_date,
            v.reference_number,
            vt.name AS voucher_type,
            COALESCE(party_sub.party_name, party_sub2.party_name, 'Cash Account') AS party_name
        FROM {settings.TALLY_DATABASE_NAME}.stock_entries se
        JOIN {settings.TALLY_DATABASE_NAME}.vouchers v ON se.voucher_id = v.voucher_id
        JOIN {settings.TALLY_DATABASE_NAME}.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        LEFT JOIN (
            SELECT ve.voucher_id, MAX(le.name) AS party_name
            FROM {settings.TALLY_DATABASE_NAME}.voucher_entries ve
            JOIN {settings.TALLY_DATABASE_NAME}.ledgers le ON ve.ledger_id = le.ledger_id
            JOIN {settings.TALLY_DATABASE_NAME}.account_groups ag ON le.group_id = ag.group_id
            WHERE ag.name IN ('Sundry Debtors', 'Sundry Creditors')
            GROUP BY ve.voucher_id
        ) party_sub ON party_sub.voucher_id = v.voucher_id
        LEFT JOIN (
            SELECT ve.voucher_id, MAX(le.name) AS party_name
            FROM {settings.TALLY_DATABASE_NAME}.voucher_entries ve
            JOIN {settings.TALLY_DATABASE_NAME}.ledgers le ON ve.ledger_id = le.ledger_id
            GROUP BY ve.voucher_id
        ) party_sub2 ON party_sub2.voucher_id = v.voucher_id
        WHERE se.stock_item_id = :item_id
          AND v.company_id = :company_id
        ORDER BY v.voucher_date DESC, se.stock_entry_id DESC
    """)
    result = await db.execute(sql, {"item_id": item_id, "company_id": user.company_id})
    rows = result.fetchall()

    return [
        {
            "stock_entry_id": r.stock_entry_id,
            "quantity": float(r.quantity),
            "amount": float(r.amount),
            "is_inward": bool(r.is_inward),
            "voucher_id": r.voucher_id,
            "voucher_number": r.voucher_number,
            "voucher_date": str(r.voucher_date),
            "reference_number": r.reference_number or "",
            "voucher_type": r.voucher_type,
            "party_name": r.party_name or "—",
        }
        for r in rows
    ]


# --- Bill of Materials (BOM) ---


@router.post("/boms", response_model=BillOfMaterialsResponse)
async def create_bom(
    req: BillOfMaterialsCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Verify stock item exists
    item_query = await db.execute(
        select(MstStockItem).where(
            MstStockItem.stock_item_id == req.stock_item_id,
            MstStockItem.company_id == user.company_id
        )
    )
    if not item_query.scalars().first():
        raise HTTPException(status_code=400, detail="Product Stock item not found.")
        
    bom = BillOfMaterials(
        company_id=user.company_id,
        stock_item_id=req.stock_item_id,
        name=req.name,
        qty_to_produce=req.qty_to_produce
    )
    db.add(bom)
    await db.flush()
    
    for bi in req.bom_items:
        # Verify ingredient stock item
        ing_query = await db.execute(
            select(MstStockItem).where(
                MstStockItem.stock_item_id == bi.stock_item_id,
                MstStockItem.company_id == user.company_id
            )
        )
        if not ing_query.scalars().first():
            raise HTTPException(status_code=400, detail=f"Ingredient Stock item ID {bi.stock_item_id} not found.")
            
        bom_item = BomItem(
            bom_id=bom.bom_id,
            stock_item_id=bi.stock_item_id,
            qty_needed=bi.qty_needed
        )
        db.add(bom_item)
        
    await db.commit()
    
    final_query = await db.execute(
        select(BillOfMaterials)
        .options(selectinload(BillOfMaterials.bom_items))
        .where(BillOfMaterials.bom_id == bom.bom_id)
    )
    return final_query.scalars().first()

@router.get("/boms", response_model=List[BillOfMaterialsResponse])
async def get_boms(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(BillOfMaterials)
        .options(selectinload(BillOfMaterials.bom_items))
        .where(BillOfMaterials.company_id == user.company_id)
    )
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Batches ---

@router.post("/batches", response_model=BatchResponse)
async def create_batch(
    req: BatchCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Verify stock item
    item_query = await db.execute(
        select(MstStockItem).where(
            MstStockItem.stock_item_id == req.stock_item_id,
            MstStockItem.company_id == user.company_id
        )
    )
    if not item_query.scalars().first():
        raise HTTPException(status_code=400, detail="Stock item not found.")
        
    mdate = datetime.strptime(req.manufacture_date, "%Y-%m-%d").date() if req.manufacture_date else None
    edate = datetime.strptime(req.expiry_date, "%Y-%m-%d").date() if req.expiry_date else None
    
    batch = Batch(
        company_id=user.company_id,
        stock_item_id=req.stock_item_id,
        batch_number=req.batch_number,
        manufacture_date=mdate,
        expiry_date=edate,
        quantity_received=req.quantity_received,
        quantity_available=req.quantity_available,
        purchase_voucher_id=req.purchase_voucher_id
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch

@router.get("/batches", response_model=List[BatchResponse])
async def get_batches(
    stock_item_id: Optional[int] = None,
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Batch).where(Batch.company_id == user.company_id)
    if stock_item_id:
        stmt = stmt.where(Batch.stock_item_id == stock_item_id)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Serial Numbers ---

@router.post("/serials", response_model=SerialNumberResponse)
async def create_serial(
    req: SerialNumberCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Verify stock item
    item_query = await db.execute(
        select(MstStockItem).where(
            MstStockItem.stock_item_id == req.stock_item_id,
            MstStockItem.company_id == user.company_id
        )
    )
    if not item_query.scalars().first():
        raise HTTPException(status_code=400, detail="Stock item not found.")
        
    wdate = datetime.strptime(req.warranty_expiry, "%Y-%m-%d").date() if req.warranty_expiry else None
    
    serial = SerialNumber(
        company_id=user.company_id,
        stock_item_id=req.stock_item_id,
        serial_number=req.serial_number,
        godown_id=req.godown_id,
        status=req.status,
        purchase_voucher_id=req.purchase_voucher_id,
        sale_voucher_id=req.sale_voucher_id,
        warranty_expiry=wdate
    )
    db.add(serial)
    await db.commit()
    await db.refresh(serial)
    return serial

@router.get("/serials", response_model=List[SerialNumberResponse])
async def get_serials(
    stock_item_id: Optional[int] = None,
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(SerialNumber).where(SerialNumber.company_id == user.company_id)
    if stock_item_id:
        stmt = stmt.where(SerialNumber.stock_item_id == stock_item_id)
    res = await db.execute(stmt)
    return res.scalars().all()
