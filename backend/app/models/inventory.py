from sqlalchemy import Column, Integer, BigInteger, String, Date, Boolean, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"
    
    unit_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(20), nullable=False)
    symbol = Column(String(10), nullable=False)
    decimal_places = Column(Integer, default=2)
    
    items = relationship("StockItem", back_populates="unit")

class StockGroup(Base):
    __tablename__ = "stock_groups"
    
    stock_group_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("stock_groups.stock_group_id", ondelete="SET NULL"), nullable=True)
    
    parent = relationship("StockGroup", remote_side=[stock_group_id], backref="sub_groups")
    items = relationship("StockItem", back_populates="group")

class StockCategory(Base):
    __tablename__ = "stock_categories"
    
    stock_category_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("stock_categories.stock_category_id", ondelete="SET NULL"), nullable=True)
    
    parent = relationship("StockCategory", remote_side=[stock_category_id], backref="sub_categories")
    items = relationship("StockItem", back_populates="category")

class Godown(Base):
    __tablename__ = "godowns"
    
    godown_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    address = Column(String(300), nullable=True)
    
    stock_entries = relationship("StockEntry", back_populates="godown")

class StockItem(Base):
    __tablename__ = "stock_items"
    
    stock_item_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    stock_group_id = Column(Integer, ForeignKey("stock_groups.stock_group_id", ondelete="SET NULL"), nullable=True)
    stock_category_id = Column(Integer, ForeignKey("stock_categories.stock_category_id", ondelete="SET NULL"), nullable=True)
    unit_id = Column(Integer, ForeignKey("units_of_measure.unit_id"), nullable=False)
    hsn_code = Column(String(10), nullable=True)
    gst_rate_percent = Column(Numeric(5, 2), default=0.00)
    opening_qty = Column(Numeric(14, 3), default=0.00)
    opening_rate = Column(Numeric(14, 2), default=0.00)
    closing_qty = Column(Numeric(14, 3), default=0.00)
    closing_rate = Column(Numeric(14, 2), default=0.00)
    closing_value = Column(Numeric(14, 2), default=0.00)
    reorder_level = Column(Numeric(14, 3), default=0.00)
    tracking_type = Column(Enum('None', 'Batch', 'Serial', name='tracking_type_enum'), default='None')
    shelf_life_days = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    
    unit = relationship("UnitOfMeasure", back_populates="items")
    group = relationship("StockGroup", back_populates="items")
    category = relationship("StockCategory", back_populates="items")
    boms = relationship("BillOfMaterials", back_populates="stock_item", cascade="all, delete-orphan")

    @property
    def item_id(self):
        return self.stock_item_id

    @property
    def group_name(self):
        return self.group.name if self.group else "All"

    @property
    def uom(self):
        return self.unit.symbol if self.unit else "PCS"

    @property
    def closing_balance(self):
        return self.closing_qty

class StockEntry(Base):
    __tablename__ = "stock_entries"
    
    stock_entry_id = Column(BigInteger, primary_key=True, index=True)
    voucher_id = Column(BigInteger, ForeignKey("vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    stock_item_id = Column(Integer, ForeignKey("stock_items.stock_item_id"), nullable=False)
    godown_id = Column(Integer, ForeignKey("godowns.godown_id"), nullable=True)
    batch_id = Column(BigInteger, ForeignKey("batches.batch_id", ondelete="SET NULL"), nullable=True)
    serial_id = Column(BigInteger, ForeignKey("serial_numbers.serial_id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Numeric(14, 3), nullable=False)
    rate = Column(Numeric(14, 2), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    is_inward = Column(Boolean, default=True)
    
    godown = relationship("Godown", back_populates="stock_entries")
    stock_item = relationship("StockItem")
    batch = relationship("Batch")
    serial = relationship("SerialNumber")

class BillOfMaterials(Base):
    __tablename__ = "bill_of_materials"
    
    bom_id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("stock_items.stock_item_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    qty_to_produce = Column(Numeric(14, 3), default=1.000)
    created_at = Column(DateTime, server_default=func.now())
    
    stock_item = relationship("StockItem", back_populates="boms")
    bom_items = relationship("BomItem", back_populates="bom", cascade="all, delete-orphan")

class BomItem(Base):
    __tablename__ = "bom_items"
    
    bom_item_id = Column(Integer, primary_key=True, index=True)
    bom_id = Column(Integer, ForeignKey("bill_of_materials.bom_id", ondelete="CASCADE"), nullable=False)
    stock_item_id = Column(Integer, ForeignKey("stock_items.stock_item_id"), nullable=False)
    qty_needed = Column(Numeric(14, 3), nullable=False)
    
    bom = relationship("BillOfMaterials", back_populates="bom_items")
    stock_item = relationship("StockItem")

class Batch(Base):
    __tablename__ = "batches"
    
    batch_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("stock_items.stock_item_id"), nullable=False)
    batch_number = Column(String(50), nullable=False)
    manufacture_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    quantity_received = Column(Numeric(14, 3), nullable=False)
    quantity_available = Column(Numeric(14, 3), nullable=False)
    purchase_voucher_id = Column(BigInteger, ForeignKey("vouchers.voucher_id", ondelete="SET NULL"), nullable=True)

class SerialNumber(Base):
    __tablename__ = "serial_numbers"
    
    serial_id = Column(BigInteger, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("stock_items.stock_item_id"), nullable=False)
    serial_number = Column(String(80), nullable=False)
    godown_id = Column(Integer, ForeignKey("godowns.godown_id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum('Available', 'Sold', 'Returned', 'Damaged', 'In Transit', name='serial_status_enum'), default='Available')
    purchase_voucher_id = Column(BigInteger, ForeignKey("vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    sale_voucher_id = Column(BigInteger, ForeignKey("vouchers.voucher_id", ondelete="SET NULL"), nullable=True)
    warranty_expiry = Column(Date, nullable=True)
