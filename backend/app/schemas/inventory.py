from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime

class UnitOfMeasureCreate(BaseModel):
    name: str
    symbol: str
    decimal_places: int = 2

class UnitOfMeasureResponse(UnitOfMeasureCreate):
    unit_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class StockGroupCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None

class StockGroupResponse(StockGroupCreate):
    stock_group_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class StockCategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None

class StockCategoryResponse(StockCategoryCreate):
    stock_category_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class GodownCreate(BaseModel):
    name: str
    address: Optional[str] = None

class GodownResponse(GodownCreate):
    godown_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class StockItemCreate(BaseModel):
    name: str
    stock_group_id: Optional[int] = None
    stock_category_id: Optional[int] = None
    unit_id: int
    hsn_code: Optional[str] = None
    gst_rate_percent: Decimal = Decimal("0.00")
    opening_qty: Decimal = Decimal("0.000")
    opening_rate: Decimal = Decimal("0.00")
    reorder_level: Decimal = Decimal("0.000")
    tracking_type: str = "None"  # 'None', 'Batch', 'Serial'
    shelf_life_days: Optional[int] = None

class StockItemResponse(StockItemCreate):
    stock_item_id: int
    item_id: int
    company_id: int
    is_active: bool
    group_name: Optional[str] = None
    uom: Optional[str] = None
    closing_balance: Decimal = Decimal("0.000")
    closing_rate: Decimal = Decimal("0.00")
    closing_value: Decimal = Decimal("0.00")
    
    inward_qty: Decimal = Decimal("0.000")
    inward_value: Decimal = Decimal("0.00")
    outward_qty: Decimal = Decimal("0.000")
    outward_value: Decimal = Decimal("0.00")
    cons_value: Decimal = Decimal("0.00")
    gp_value: Decimal = Decimal("0.00")
    gp_percent: Decimal = Decimal("0.00")
    
    class Config:
        from_attributes = True

class BomItemCreate(BaseModel):
    stock_item_id: int
    qty_needed: Decimal

class BomItemResponse(BomItemCreate):
    bom_item_id: int
    bom_id: int
    
    class Config:
        from_attributes = True

class BillOfMaterialsCreate(BaseModel):
    stock_item_id: int
    name: str
    qty_to_produce: Decimal = Decimal("1.000")
    bom_items: List[BomItemCreate]

class BillOfMaterialsResponse(BaseModel):
    bom_id: int
    company_id: int
    stock_item_id: int
    name: str
    qty_to_produce: Decimal
    created_at: datetime
    bom_items: List[BomItemResponse]
    
    class Config:
        from_attributes = True

class BatchCreate(BaseModel):
    stock_item_id: int
    batch_number: str
    manufacture_date: Optional[str] = None  # YYYY-MM-DD
    expiry_date: Optional[str] = None       # YYYY-MM-DD
    quantity_received: Decimal
    quantity_available: Decimal
    purchase_voucher_id: Optional[int] = None

class BatchResponse(BaseModel):
    batch_id: int
    company_id: int
    stock_item_id: int
    batch_number: str
    manufacture_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quantity_received: Decimal
    quantity_available: Decimal
    purchase_voucher_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class SerialNumberCreate(BaseModel):
    stock_item_id: int
    serial_number: str
    godown_id: Optional[int] = None
    status: str = "Available"
    purchase_voucher_id: Optional[int] = None
    sale_voucher_id: Optional[int] = None
    warranty_expiry: Optional[str] = None  # YYYY-MM-DD

class SerialNumberResponse(BaseModel):
    serial_id: int
    company_id: int
    stock_item_id: int
    serial_number: str
    godown_id: Optional[int] = None
    status: str
    purchase_voucher_id: Optional[int] = None
    sale_voucher_id: Optional[int] = None
    warranty_expiry: Optional[date] = None
    
    class Config:
        from_attributes = True
        
class StockEntryCreate(BaseModel):
    stock_item_id: int
    godown_id: int
    batch_id: Optional[int] = None
    serial_id: Optional[int] = None
    quantity: Decimal
    rate: Decimal
    amount: Decimal

class StockEntryResponse(StockEntryCreate):
    stock_entry_id: int
    voucher_id: int
    
    class Config:
        from_attributes = True
