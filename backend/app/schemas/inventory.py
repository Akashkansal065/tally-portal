from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime

class UnitOfMeasureCreate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    original_name: Optional[str] = None
    decimal_places: int = 2
    is_simple_unit: bool = True
    base_unit_id: Optional[int] = None
    additional_unit_id: Optional[int] = None
    conversion_factor: Optional[Decimal] = None

class UnitOfMeasureResponse(UnitOfMeasureCreate):
    unit_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class StockGroupAlias(BaseModel):
    alias: str
    
    class Config:
        from_attributes = True

class StockGroupCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    is_active: bool = True
    aliases: List[str] = []

class StockGroupResponse(StockGroupCreate):
    stock_group_id: int
    company_id: int
    aliases: List[StockGroupAlias] = []
    
    class Config:
        from_attributes = True

class StockCategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    is_active: bool = True

class StockCategoryResponse(StockCategoryCreate):
    stock_category_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class GodownCreate(BaseModel):
    name: str
    address: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: bool = True
    contact_person: Optional[str] = None
    phone: Optional[str] = None

class GodownResponse(GodownCreate):
    godown_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class StockItemAliasCreate(BaseModel):
    alias: str
    alias_type: str = "name"

class StockItemAliasResponse(StockItemAliasCreate):
    id: int
    
    class Config:
        from_attributes = True

class StockItemPriceListCreate(BaseModel):
    price_type: str
    effective_from: date
    rate: Decimal

class StockItemPriceListResponse(StockItemPriceListCreate):
    id: int
    
    class Config:
        from_attributes = True

class StockItemOpeningBalanceCreate(BaseModel):
    godown_id: Optional[int] = None
    batch_name: Optional[str] = None
    quantity: Decimal
    rate: Decimal
    amount: Decimal

class StockItemOpeningBalanceResponse(StockItemOpeningBalanceCreate):
    id: int
    
    class Config:
        from_attributes = True

class PriceLevelCreate(BaseModel):
    name: str
    is_active: bool = True

class PriceLevelResponse(PriceLevelCreate):
    price_level_id: int
    company_id: int
    
    class Config:
        from_attributes = True

class StockItemPriceLevelRateCreate(BaseModel):
    price_level_id: int
    effective_from: date
    qty_from: Optional[Decimal] = None
    qty_to: Optional[Decimal] = None
    rate: Decimal
    discount_percent: Optional[Decimal] = Decimal("0.00")

class StockItemPriceLevelRateResponse(StockItemPriceLevelRateCreate):
    id: int
    
    class Config:
        from_attributes = True

class StockItemBOMComponentCreate(BaseModel):
    component_item_id: int
    godown_id: Optional[int] = None
    quantity: Decimal
    component_type: str = "Component"

class StockItemBOMComponentResponse(StockItemBOMComponentCreate):
    id: int
    component_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class StockItemBOMCreate(BaseModel):
    bom_name: str
    unit_of_manufacture: Decimal = Decimal("1.000")
    is_active: bool = True
    components: List[StockItemBOMComponentCreate] = []

class StockItemBOMResponse(StockItemBOMCreate):
    bom_id: int
    components: List[StockItemBOMComponentResponse] = []
    
    class Config:
        from_attributes = True

class BulkPriceLevelRateItem(BaseModel):
    stock_item_id: int
    qty_from: Optional[Decimal] = None
    qty_to: Optional[Decimal] = None
    rate: Decimal
    discount_percent: Optional[Decimal] = Decimal("0.00")

class PriceLevelRatesBulkCreate(BaseModel):
    stock_group_id: Optional[int] = None
    effective_from: date
    rates: List[BulkPriceLevelRateItem]

class StockItemCreate(BaseModel):
    name: str
    stock_group_id: Optional[int] = None
    stock_category_id: Optional[int] = None
    unit_id: Optional[int] = None
    alt_unit_id: Optional[int] = None
    alt_unit_conversion: Optional[Decimal] = None
    description: Optional[str] = None
    standard_cost_price: Optional[Decimal] = None
    standard_selling_price: Optional[Decimal] = None
    image_url: Optional[str] = None
    
    hsn_code: Optional[str] = None
    gst_rate_percent: Decimal = Decimal("0.00")
    
    opening_qty: Decimal = Decimal("0.000")
    opening_rate: Decimal = Decimal("0.00")
    reorder_level: Decimal = Decimal("0.000")
    minimum_order_qty: Decimal = Decimal("0.000")
    tracking_type: str = "None"  # 'None', 'Batch', 'Serial'
    shelf_life_days: Optional[int] = None
    is_active: bool = True
    
    aliases: List[StockItemAliasCreate] = []
    price_lists: List[StockItemPriceListCreate] = []
    opening_balances: List[StockItemOpeningBalanceCreate] = []
    boms: List[StockItemBOMCreate] = []
    price_level_rates: List[StockItemPriceLevelRateCreate] = []

class StockItemResponse(StockItemCreate):
    stock_item_id: int
    item_id: int
    company_id: int
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
    
    aliases: List[StockItemAliasResponse] = []
    price_lists: List[StockItemPriceListResponse] = []
    opening_balances: List[StockItemOpeningBalanceResponse] = []
    boms: List[StockItemBOMResponse] = []
    price_level_rates: List[StockItemPriceLevelRateResponse] = []
    
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
