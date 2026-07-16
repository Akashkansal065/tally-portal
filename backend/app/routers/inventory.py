from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.inventory import (
    MstUom, MstStockGroup, MstStockCategory, MstGodown, MstStockItem,
    BillOfMaterials, BomItem, Batch, SerialNumber
)
from app.schemas.inventory import (
    UnitOfMeasureCreate, UnitOfMeasureResponse,
    StockGroupCreate, StockGroupResponse,
    StockCategoryCreate, StockCategoryResponse,
    GodownCreate, GodownResponse,
    StockItemCreate, StockItemResponse,
    BillOfMaterialsCreate, BillOfMaterialsResponse,
    BatchCreate, BatchResponse,
    SerialNumberCreate, SerialNumberResponse
)

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

# --- Unit of Measure (UOM) ---

@router.post("/uoms", response_model=UnitOfMeasureResponse)
async def create_uom(
    req: UnitOfMeasureCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    uom = MstUom(
        company_id=user.company_id,
        name=req.name,
        symbol=req.symbol,
        decimal_places=req.decimal_places
    )
    db.add(uom)
    await db.commit()
    await db.refresh(uom)
    return uom

@router.get("/uoms", response_model=List[UnitOfMeasureResponse])
async def get_uoms(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MstUom).where(MstUom.company_id == user.company_id)
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
        parent_id=req.parent_id
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group

@router.get("/groups", response_model=List[StockGroupResponse])
async def get_stock_groups(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MstStockGroup).where(MstStockGroup.company_id == user.company_id)
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
        parent_id=req.parent_id
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat

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
    g = MstGodown(
        company_id=user.company_id,
        name=req.name,
        address=req.address
    )
    db.add(g)
    await db.commit()
    await db.refresh(g)
    return g

@router.get("/godowns", response_model=List[GodownResponse])
async def get_godowns(
    user: User = Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(MstGodown).where(MstGodown.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

# --- Stock Items ---

@router.post("/items", response_model=StockItemResponse)
async def create_stock_item(
    req: StockItemCreate,
    user: User = Depends(require_permission("inventory", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Verify UOM exists
    uom_query = await db.execute(
        select(MstUom).where(
            MstUom.unit_id == req.unit_id,
            MstUom.company_id == user.company_id
        )
    )
    if not uom_query.scalars().first():
        raise HTTPException(status_code=400, detail="Unit of Measure not found.")
        
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
        unit_id=req.unit_id,
        hsn_code=req.hsn_code,
        gst_rate_percent=req.gst_rate_percent,
        opening_qty=req.opening_qty,
        opening_rate=req.opening_rate,
        reorder_level=req.reorder_level,
        tracking_type=req.tracking_type,
        shelf_life_days=req.shelf_life_days,
        is_active=True
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

@router.get("/items", response_model=List[StockItemResponse])
async def get_stock_items(
    user: User = Depends(require_permission("inventory", "read")),
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
    from app.models.inventory import TrnInventory
    from app.models.voucher import TrnVoucher
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
    sql = sa_text("""
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
            party_sub.party_name
        FROM stock_entries se
        JOIN vouchers v ON se.voucher_id = v.voucher_id
        JOIN voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
        LEFT JOIN (
            SELECT ve.voucher_id, MAX(le.name) AS party_name
            FROM voucher_entries ve
            JOIN ledgers le ON ve.ledger_id = le.ledger_id
            JOIN account_groups ag ON le.group_id = ag.group_id
            WHERE ag.name IN ('Sundry Debtors', 'Sundry Creditors')
            GROUP BY ve.voucher_id
        ) party_sub ON party_sub.voucher_id = v.voucher_id
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
