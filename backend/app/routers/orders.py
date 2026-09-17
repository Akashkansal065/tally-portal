"""
Orders Router — temporary order creation and management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, desc
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from app.core.database import get_db, Base
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.core.config import settings

def check_is_admin(user: User) -> bool:
    if not user:
        return False
    if user.role and user.role.name and user.role.name.lower() in {"admin", "owner", "superadmin"}:
        return True
    if getattr(user, "role_id", None) == 1:
        return True
    return False

def check_order_editable(order: "TempOrder", user: User) -> bool:
    # Admin can edit orders at any time
    if check_is_admin(user):
        return True
    if order.status != "pending":
        return False
    if not order.created_at:
        return True
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    created_utc = order.created_at.replace(tzinfo=None) if order.created_at.tzinfo else order.created_at
    elapsed_seconds = (now_utc - created_utc).total_seconds()
    return elapsed_seconds <= 1800  # 30 minutes

def format_datetime_utc(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    iso = dt.isoformat()
    if not iso.endswith("Z") and "+" not in iso:
        iso += "Z"
    return iso

# ─── Models ──────────────────────────────────────────────────────────────────

class TempOrder(Base):
    __tablename__ = "temp_orders"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=True)
    custom_customer_name = Column(String(256), nullable=True)
    status = Column(String(32), default="pending")  # pending, done, cancelled
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    ledger = relationship("MstLedger", foreign_keys=[ledger_id])
    items = relationship("TempOrderItem", back_populates="order", cascade="all, delete-orphan")


class TempOrderItem(Base):
    __tablename__ = "temp_order_items"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.temp_orders.id", ondelete="CASCADE"), nullable=False)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id"), nullable=False)
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    is_bill_required = Column(Boolean, default=True)

    order = relationship("TempOrder", back_populates="items")
    stock_item = relationship("MstStockItem", foreign_keys=[stock_item_id])

# ─── Schemas ─────────────────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    stock_item_id: int
    qty: float
    price: float
    is_bill_required: Optional[bool] = None
    has_gst: Optional[bool] = None

    @property
    def bill_required(self) -> bool:
        if self.is_bill_required is not None:
            return self.is_bill_required
        if self.has_gst is not None:
            return self.has_gst
        return True

class OrderCreateRequest(BaseModel):
    ledger_id: Optional[int] = None
    custom_customer_name: Optional[str] = None
    items: List[OrderItemCreate]

# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/temporders", tags=["Orders"])


@router.post("")
async def create_order(
    req: OrderCreateRequest,
    user: User = Depends(require_permission("orders", "create")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.tally_core import MstLedger
    from app.models.tally_core import MstStockItem

    if not req.ledger_id and not req.custom_customer_name:
        raise HTTPException(status_code=400, detail="Either ledger_id or custom_customer_name is required.")

    # Verify customer ledger if provided
    if req.ledger_id:
        ledger_query = await db.execute(
            select(MstLedger).where(MstLedger.ledger_id == req.ledger_id, MstLedger.company_id == user.company_id)
        )
        ledger = ledger_query.scalars().first()
        if not ledger:
            raise HTTPException(status_code=400, detail="Customer ledger not found.")

    if not req.items:
        raise HTTPException(status_code=400, detail="At least one item is required.")

    order = TempOrder(
        user_id=user.user_id,
        ledger_id=req.ledger_id,
        custom_customer_name=req.custom_customer_name[:256] if req.custom_customer_name else None,
        status="pending",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    for item in req.items:
        # Verify stock item exists
        stock_query = await db.execute(
            select(MstStockItem).where(MstStockItem.stock_item_id == item.stock_item_id, MstStockItem.company_id == user.company_id)
        )
        stock = stock_query.scalars().first()
        if not stock:
            raise HTTPException(status_code=400, detail=f"Stock item {item.stock_item_id} not found.")

        order_item = TempOrderItem(
            order_id=order.id,
            stock_item_id=item.stock_item_id,
            qty=item.qty,
            price=item.price,
            is_bill_required=item.bill_required,
        )
        db.add(order_item)

    await db.commit()

    # Notify admins of new temp order
    from app.routers.notifications import notify_admins
    cust_name = req.custom_customer_name or (ledger.name if req.ledger_id and 'ledger' in locals() and ledger else "Customer")
    await notify_admins(
        db=db,
        company_id=user.company_id,
        type="order_created",
        title="New Order Created",
        message=f"{user.username} placed order #{order.id} for {cust_name}",
        reference_id=str(order.id),
        reference_type="order",
        exclude_user_id=user.user_id,
        auto_commit=True,
    )

    return {"success": True, "id": order.id, "message": "Order created successfully"}


@router.get("")
async def list_orders(
    user: User = Depends(require_permission("orders", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.tally_core import MstLedger
    from app.models.tally_core import MstStockItem
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(TempOrder)
        .where(TempOrder.user_id == user.user_id)
        .options(selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group), selectinload(TempOrder.ledger))
        .order_by(desc(TempOrder.created_at))
        .limit(100)
    )
    orders = result.scalars().all()

    output = []
    for o in orders:
        items_list = []
        total = 0.0
        for item in o.items:
            subtotal = item.qty * item.price
            total += subtotal

            c_name = item.stock_item.group_name if (item.stock_item and item.stock_item.group_name not in ("All", " Primary")) else None
            items_list.append({
                "stock_item_id": item.stock_item_id,
                "stock_item_name": item.stock_item.name if item.stock_item else "Unknown Item",
                "company_name": c_name,
                "qty": item.qty,
                "price": item.price,
                "is_bill_required": item.is_bill_required,
                "has_gst": item.is_bill_required,
            })

        output.append({
            "id": o.id,
            "user_id": o.user_id,
            "salesperson": o.user.username if o.user else "Salesperson",
            "customer_name": o.ledger.name if o.ledger else o.custom_customer_name or "Unknown Customer",
            "status": o.status,
            "created_at": format_datetime_utc(o.created_at),
            "total": round(total, 2),
            "items": items_list,
        })
    return output


@router.get("/all")
async def list_all_orders(
    current_user: User = Depends(require_permission("admin", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.tally_core import MstLedger
    from app.models.tally_core import MstStockItem
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(TempOrder)
        .options(selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group), selectinload(TempOrder.ledger))
        .order_by(desc(TempOrder.created_at))
        .limit(500)
    )
    orders = result.scalars().all()

    output = []
    for o in orders:
        items_list = []
        total = 0.0
        for item in o.items:
            subtotal = item.qty * item.price
            total += subtotal

            c_name = item.stock_item.group_name if (item.stock_item and item.stock_item.group_name not in ("All", " Primary")) else None
            items_list.append({
                "stock_item_id": item.stock_item_id,
                "stock_item_name": item.stock_item.name if item.stock_item else "Unknown Item",
                "company_name": c_name,
                "qty": item.qty,
                "price": item.price,
                "is_bill_required": item.is_bill_required,
                "has_gst": item.is_bill_required,
            })

        output.append({
            "id": o.id,
            "user_id": o.user_id,
            "salesperson": o.user.username if o.user else "Salesperson",
            "customer_name": o.ledger.name if o.ledger else o.custom_customer_name or "Unknown Customer",
            "status": o.status,
            "created_at": format_datetime_utc(o.created_at),
            "total": round(total, 2),
            "items": items_list,
        })
    return output


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    user: User = Depends(require_permission("orders", "read")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.tally_core import MstLedger
    from app.models.tally_core import MstStockItem
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(TempOrder)
        .where(TempOrder.id == order_id)
        .options(selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group), selectinload(TempOrder.ledger))
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    is_admin = check_is_admin(user)

    # Access control: admin can view any order; regular salesperson only their own
    if not is_admin and order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    # Time check (30 minutes edit window for regular salesperson; admin can edit anytime)
    is_editable = check_order_editable(order, user)

    items_list = []
    total = 0.0
    for item in order.items:
        subtotal = item.qty * item.price
        total += subtotal

        c_name = item.stock_item.group_name if (item.stock_item and item.stock_item.group_name not in ("All", " Primary")) else None
        items_list.append({
            "stock_item_id": item.stock_item_id,
            "stock_item_name": item.stock_item.name if item.stock_item else "Unknown Item",
            "company_name": c_name,
            "qty": item.qty,
            "price": item.price,
            "is_bill_required": item.is_bill_required,
            "has_gst": item.is_bill_required,
        })

    return {
        "id": order.id,
        "user_id": order.user_id,
        "salesperson": order.user.username if order.user else "Salesperson",
        "ledger_id": order.ledger_id,
        "custom_customer_name": order.custom_customer_name,
        "customer_name": order.ledger.name if order.ledger else order.custom_customer_name or "Unknown Customer",
        "status": order.status,
        "created_at": format_datetime_utc(order.created_at),
        "total": round(total, 2),
        "items": items_list,
        "is_editable": is_editable,
    }


@router.put("/{order_id}")
async def edit_order(
    order_id: int,
    req: OrderCreateRequest,
    user: User = Depends(require_permission("orders", "update")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.tally_core import MstLedger
    from app.models.tally_core import MstStockItem
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(TempOrder)
        .where(TempOrder.id == order_id)
        .options(selectinload(TempOrder.items))
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    is_admin = check_is_admin(user)

    if not is_admin and order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this order")

    if not check_order_editable(order, user):
        if order.status != "pending":
            raise HTTPException(status_code=400, detail="Only pending orders can be edited")
        raise HTTPException(status_code=400, detail="The 30-minute editing window has expired")

    if not req.ledger_id and not req.custom_customer_name:
        raise HTTPException(status_code=400, detail="Either ledger_id or custom_customer_name is required")

    if req.ledger_id:
        ledger_query = await db.execute(
            select(MstLedger).where(MstLedger.ledger_id == req.ledger_id, MstLedger.company_id == user.company_id)
        )
        ledger = ledger_query.scalars().first()
        if not ledger:
            raise HTTPException(status_code=400, detail="Customer ledger not found")
        order.ledger_id = req.ledger_id
        order.custom_customer_name = None
    else:
        order.ledger_id = None
        order.custom_customer_name = req.custom_customer_name[:256]

    # Delete existing items
    for item in order.items:
        await db.delete(item)
    await db.flush()

    for item in req.items:
        stock_query = await db.execute(
            select(MstStockItem).where(MstStockItem.stock_item_id == item.stock_item_id, MstStockItem.company_id == user.company_id)
        )
        stock = stock_query.scalars().first()
        if not stock:
            raise HTTPException(status_code=400, detail=f"Stock item {item.stock_item_id} not found")

        order_item = TempOrderItem(
            order_id=order.id,
            stock_item_id=item.stock_item_id,
            qty=item.qty,
            price=item.price,
            is_bill_required=item.bill_required,
        )
        db.add(order_item)

    await db.commit()
    return {"success": True, "message": "Order updated successfully"}


class OrderStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None


@router.put("/{order_id}/status")
async def update_order_status(
    order_id: int,
    req: OrderStatusUpdate,
    user: User = Depends(require_permission("admin", "update")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(TempOrder).where(TempOrder.id == order_id))
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if req.status not in {"done", "cancelled", "pending"}:
        raise HTTPException(status_code=400, detail="Status must be 'done', 'cancelled', or 'pending'")

    order.status = req.status
    await db.commit()

    # Notify order creator (salesperson)
    from app.routers.notifications import notify_user
    status_label = "approved" if req.status == "done" else ("rejected" if req.status == "cancelled" else req.status)
    await notify_user(
        db=db,
        company_id=user.company_id,
        user_id=order.user_id,
        type="order_status",
        title=f"Order #{order.id} {status_label.title()}",
        message=f"Your order #{order.id} has been {status_label}.",
        reference_id=str(order.id),
        reference_type="order",
        auto_commit=True,
    )

    return {"success": True, "status": order.status}

