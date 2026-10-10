"""
Orders Router — temporary order creation and management.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Index, desc
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from app.core.database import get_db, Base
from app.core.permissions import require_permission, get_effective_permission
from app.models.portal_core import User
from app.core.config import settings
from app.core.datetime_utils import get_ist_now, to_ist_iso

async def can_manage_all_orders(user: User, db: AsyncSession) -> bool:
    """Determine whether user has manager/admin-level access to view/edit all orders."""
    admin_perms = await get_effective_permission(user, "admin", db)
    if admin_perms.get("can_read", False):
        return True
    orders_perms = await get_effective_permission(user, "orders", db)
    return bool(orders_perms.get("can_update", False) and orders_perms.get("can_delete", False))

def check_order_editable(order: "TempOrder", is_manager: bool) -> bool:
    # Managers/admins can edit orders at any time
    if is_manager:
        return True
    if order.status != "pending":
        return False
    if not order.created_at:
        return True
    now_ist = get_ist_now()
    created = order.created_at.replace(tzinfo=None) if order.created_at.tzinfo else order.created_at
    elapsed_seconds = (now_ist - created).total_seconds()
    return elapsed_seconds <= 1800  # 30 minutes

def format_datetime_utc(dt: Optional[datetime]) -> Optional[str]:
    return to_ist_iso(dt)

# ─── Models ──────────────────────────────────────────────────────────────────

class TempOrder(Base):
    __tablename__ = "temp_orders"
    __table_args__ = (
        Index("ix_temp_orders_company", "company_id"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, index=True)
    # The company the order was taken for. Not read yet: lists still go by the owner's active company.
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=True)
    custom_customer_name = Column(String(256), nullable=True)
    custom_customer_gstin = Column(String(15), nullable=True)
    status = Column(String(32), default="pending")  # pending, done, cancelled
    acted_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id"), nullable=True)
    acted_at = Column(DateTime, nullable=True)
    status_reason = Column(String(1024), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    acted_by = relationship("User", foreign_keys=[acted_by_user_id])
    ledger = relationship("MstLedger", foreign_keys=[ledger_id])
    items = relationship("TempOrderItem", back_populates="order", cascade="all, delete-orphan")


class TempOrderItem(Base):
    __tablename__ = "temp_order_items"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.temp_orders.id", ondelete="CASCADE"), nullable=False)
    stock_item_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.stock_items.stock_item_id"), nullable=True)
    custom_item_name = Column(String(256), nullable=True)
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    is_bill_required = Column(Boolean, default=True)
    is_sent = Column(Boolean, default=False)
    sent_qty = Column(Float, nullable=True, default=0.0)
    sent_at = Column(DateTime, nullable=True)

    order = relationship("TempOrder", back_populates="items")
    stock_item = relationship("MstStockItem", foreign_keys=[stock_item_id])


def recalculate_order_dispatch_state(order: TempOrder, now_ist: datetime) -> None:
    """
    Recalculate order status based on item-level dispatch state.
    - If status was cancelled, keep as cancelled.
    - If all items are sent (sent_qty >= qty), status becomes 'done'.
    - If at least one item is sent (or has sent_qty > 0) but not all, status becomes 'partial'.
    - If no items are sent, status becomes 'pending'.
    """
    if order.status == "cancelled":
        return

    total_items = len(order.items)
    if total_items == 0:
        return

    sent_count = 0
    any_partial = False
    for it in order.items:
        it_qty = float(it.qty or 0)
        it_sent_qty = float(it.sent_qty if it.sent_qty is not None else 0.0) if it.is_sent else 0.0
        if it.is_sent:
            if it_sent_qty >= it_qty:
                sent_count += 1
            else:
                any_partial = True
        elif it_sent_qty > 0:
            any_partial = True

    if sent_count == total_items:
        order.status = "done"
    elif sent_count > 0 or any_partial:
        order.status = "partial"
    else:
        order.status = "pending"


def format_order_response(o: TempOrder) -> dict:
    items_list = []
    total = 0.0
    sent_total = 0.0
    sent_items_count = 0

    for item in o.items:
        qty = float(item.qty or 0)
        price = float(item.price or 0)
        subtotal = qty * price
        total += subtotal

        is_item_sent = bool(item.is_sent)
        sent_qty = float(item.sent_qty if item.sent_qty is not None else (qty if is_item_sent else 0.0))
        if is_item_sent:
            sent_items_count += 1
            sent_subtotal = min(qty, sent_qty) * price
        else:
            sent_subtotal = 0.0
        sent_total += sent_subtotal
        remaining_subtotal = max(0.0, subtotal - sent_subtotal)

        c_name = (
            item.stock_item.group_name
            if (item.stock_item and item.stock_item.group_name not in ("All", " Primary"))
            else None
        )
        item_name = item.stock_item.name if item.stock_item else (item.custom_item_name or "Custom Item")
        items_list.append({
            "id": item.id,
            "stock_item_id": item.stock_item_id,
            "custom_item_name": item.custom_item_name,
            "stock_item_name": item_name,
            "company_name": c_name,
            "qty": item.qty,
            "price": item.price,
            "is_bill_required": item.is_bill_required,
            "has_gst": item.is_bill_required,
            "is_custom": bool(item.custom_item_name and not item.stock_item_id),
            "is_sent": is_item_sent,
            "sent_qty": sent_qty,
            "sent_at": format_datetime_utc(item.sent_at),
            "subtotal": round(subtotal, 2),
            "sent_subtotal": round(sent_subtotal, 2),
            "remaining_subtotal": round(remaining_subtotal, 2),
        })

    raw_gstin = o.ledger.gstin if o.ledger else o.custom_customer_gstin
    customer_gstin = raw_gstin.strip().upper() if raw_gstin else None
    remaining_total = max(0.0, total - sent_total)

    return {
        "id": o.id,
        "user_id": o.user_id,
        "salesperson": o.user.username if o.user else "Salesperson",
        "ledger_id": o.ledger_id,
        "customer_name": o.ledger.name if o.ledger else o.custom_customer_name or "Unknown Customer",
        "custom_customer_name": o.custom_customer_name,
        "custom_customer_gstin": o.custom_customer_gstin.strip().upper() if o.custom_customer_gstin else None,
        "customer_gstin": customer_gstin,
        "status": o.status,
        "acted_by_id": o.acted_by_user_id,
        "acted_by_name": o.acted_by.username if o.acted_by else None,
        "acted_at": format_datetime_utc(o.acted_at),
        "status_reason": o.status_reason,
        "created_at": format_datetime_utc(o.created_at),
        "total": round(total, 2),
        "sent_total": round(sent_total, 2),
        "remaining_total": round(remaining_total, 2),
        "sent_items_count": sent_items_count,
        "total_items_count": len(o.items),
        "items": items_list,
    }

# ─── Schemas ─────────────────────────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    stock_item_id: Optional[int] = None
    custom_item_name: Optional[str] = None
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
    custom_customer_gstin: Optional[str] = None
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

    clean_gstin = (
        req.custom_customer_gstin.strip().upper()[:15]
        if req.custom_customer_gstin and req.custom_customer_gstin.strip()
        else None
    )

    order = TempOrder(
        user_id=user.user_id,
        ledger_id=req.ledger_id,
        custom_customer_name=req.custom_customer_name[:256] if req.custom_customer_name else None,
        custom_customer_gstin=clean_gstin if not req.ledger_id else None,
        status="pending",
        created_at=get_ist_now(),
        updated_at=get_ist_now(),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    for item in req.items:
        if not item.stock_item_id and not (item.custom_item_name and item.custom_item_name.strip()):
            raise HTTPException(status_code=400, detail="Each item must have either stock_item_id or custom_item_name.")

        if item.stock_item_id:
            stock_query = await db.execute(
                select(MstStockItem).where(MstStockItem.stock_item_id == item.stock_item_id, MstStockItem.company_id == user.company_id)
            )
            stock = stock_query.scalars().first()
            if not stock:
                raise HTTPException(status_code=400, detail=f"Stock item {item.stock_item_id} not found.")

        order_item = TempOrderItem(
            order_id=order.id,
            stock_item_id=item.stock_item_id,
            custom_item_name=item.custom_item_name.strip()[:256] if item.custom_item_name else None,
            qty=item.qty,
            price=item.price,
            is_bill_required=item.bill_required,
        )
        db.add(order_item)

    await db.commit()

    # Notify admins of new temp order
    from app.routers.notifications import notify_admins
    from app.services.notifications import order_link
    cust_name = req.custom_customer_name or (ledger.name if req.ledger_id and 'ledger' in locals() and ledger else "Customer")
    await notify_admins(
        db=db,
        company_id=user.company_id,
        type="order_created",
        title="New Order Created",
        message=f"{user.username} placed order #{order.id} for {cust_name}",
        reference_id=str(order.id),
        reference_type="order",
        link=order_link(order.id, "pending"),
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
        .options(
            selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group),
            selectinload(TempOrder.ledger),
            selectinload(TempOrder.user),
            selectinload(TempOrder.acted_by),
        )
        .order_by(desc(TempOrder.created_at))
        .limit(100)
    )
    orders = result.scalars().all()
    return [format_order_response(o) for o in orders]


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
        .join(User, TempOrder.user_id == User.user_id)
        .where(User.company_id == current_user.company_id)
        .options(
            selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group),
            selectinload(TempOrder.ledger),
            selectinload(TempOrder.user),
            selectinload(TempOrder.acted_by),
        )
        .order_by(desc(TempOrder.created_at))
        .limit(500)
    )
    orders = result.scalars().all()
    return [format_order_response(o) for o in orders]


@router.get("/dispatch-summary")
async def get_dispatch_summary(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = "active",  # "pending", "done", "active" (pending + done), "all", "cancelled"
    salesperson_id: Optional[int] = None,
    user: User = Depends(require_permission("orders", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Consolidated item-wise and customer-wise dispatch summary for temporary orders per day.
    Helps warehouse and managers easily see total quantities needed per item for next-day dispatch.
    """
    from app.models.tally_core import MstLedger
    from app.models.tally_core import MstStockItem
    from sqlalchemy.orm import selectinload
    from datetime import time as dt_time
    from app.core.datetime_utils import get_ist_date

    # 1. Resolve date range (defaults to current date in IST)
    ist_today = get_ist_date()
    if start_date and end_date:
        try:
            s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    elif date:
        try:
            s_date = datetime.strptime(date, "%Y-%m-%d").date()
            e_date = s_date
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        s_date = ist_today
        e_date = ist_today

    start_dt = datetime.combine(s_date, dt_time.min)
    end_dt = datetime.combine(e_date, dt_time.max)

    # 2. Check manager permissions
    is_manager = await can_manage_all_orders(user, db)

    # 3. Build query
    query = (
        select(TempOrder)
        .join(User, TempOrder.user_id == User.user_id)
        .where(
            User.company_id == user.company_id,
            TempOrder.created_at >= start_dt,
            TempOrder.created_at <= end_dt,
        )
    )

    if not is_manager:
        query = query.where(TempOrder.user_id == user.user_id)
    elif salesperson_id:
        query = query.where(TempOrder.user_id == salesperson_id)

    # Status filtering
    clean_status = (status or "active").lower().strip()
    if clean_status == "pending":
        query = query.where(TempOrder.status == "pending")
    elif clean_status == "partial":
        query = query.where(TempOrder.status == "partial")
    elif clean_status == "done":
        query = query.where(TempOrder.status == "done")
    elif clean_status == "cancelled":
        query = query.where(TempOrder.status == "cancelled")
    elif clean_status == "active":
        query = query.where(TempOrder.status.in_(["pending", "partial", "done"]))
    # if clean_status == "all", no filter applied

    query = query.options(
        selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group),
        selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.unit),
        selectinload(TempOrder.ledger),
        selectinload(TempOrder.user),
    ).order_by(desc(TempOrder.created_at))

    result = await db.execute(query)
    orders = result.scalars().all()

    # 4. Aggregate items and orders
    items_map = {}
    orders_summary = []
    total_qty_sum = 0.0
    total_val_sum = 0.0

    for o in orders:
        cust_name = o.ledger.name if o.ledger else (o.custom_customer_name or "Unknown Customer")
        raw_gstin = o.ledger.gstin if o.ledger else o.custom_customer_gstin
        cust_gstin = raw_gstin.strip().upper() if raw_gstin else None
        sp_name = o.user.username if o.user else "Salesperson"

        order_qty_total = 0.0
        order_val_total = 0.0
        order_items_list = []

        for item in o.items:
            qty = float(item.qty or 0)
            price = float(item.price or 0)
            subtotal = qty * price

            order_qty_total += qty
            order_val_total += subtotal
            total_qty_sum += qty
            total_val_sum += subtotal

            if item.stock_item_id and item.stock_item:
                item_key = f"stock_{item.stock_item_id}"
                item_name = item.stock_item.name
                c_name = item.stock_item.group_name if (item.stock_item.group_name not in ("All", " Primary")) else None
                unit_sym = item.stock_item.uom or "PCS"
                closing_stock = float(item.stock_item.closing_balance) if item.stock_item.closing_balance is not None else None
                is_custom = False
            else:
                c_item_name = (item.custom_item_name or "Custom Item").strip()
                item_key = f"custom_{c_item_name.lower()}"
                item_name = c_item_name
                c_name = None
                unit_sym = "Units"
                closing_stock = None
                is_custom = True

            order_items_list.append({
                "item_name": item_name,
                "company_name": c_name,
                "qty": qty,
                "unit": unit_sym,
                "price": price,
                "subtotal": round(subtotal, 2),
                "is_custom": is_custom,
            })

            if item_key not in items_map:
                items_map[item_key] = {
                    "key": item_key,
                    "stock_item_id": item.stock_item_id,
                    "item_name": item_name,
                    "company_name": c_name,
                    "unit": unit_sym,
                    "closing_stock": closing_stock,
                    "is_custom": is_custom,
                    "total_qty": 0.0,
                    "total_amount": 0.0,
                    "orders_count": 0,
                    "customers_count": set(),
                    "order_breakdown": [],
                }

            entry = items_map[item_key]
            entry["total_qty"] += qty
            entry["total_amount"] += subtotal
            entry["orders_count"] += 1
            entry["customers_count"].add(cust_name)
            entry["order_breakdown"].append({
                "order_id": o.id,
                "customer_name": cust_name,
                "customer_gstin": cust_gstin,
                "salesperson": sp_name,
                "qty": qty,
                "unit": unit_sym,
                "price": price,
                "subtotal": round(subtotal, 2),
                "status": o.status,
                "created_at": format_datetime_utc(o.created_at),
            })

        orders_summary.append({
            "order_id": o.id,
            "user_id": o.user_id,
            "salesperson": sp_name,
            "customer_name": cust_name,
            "customer_gstin": cust_gstin,
            "items_count": len(o.items),
            "total_qty": round(order_qty_total, 2),
            "total_amount": round(order_val_total, 2),
            "status": o.status,
            "created_at": format_datetime_utc(o.created_at),
            "items": order_items_list,
        })

    final_items = []
    for item in items_map.values():
        item["total_qty"] = round(item["total_qty"], 2)
        item["total_amount"] = round(item["total_amount"], 2)
        item["unique_customers_count"] = len(item["customers_count"])
        del item["customers_count"]
        final_items.append(item)

    # Sort descending by total_qty
    final_items.sort(key=lambda x: x["total_qty"], reverse=True)

    return {
        "date": s_date.isoformat(),
        "start_date": s_date.isoformat(),
        "end_date": e_date.isoformat(),
        "status_filter": clean_status,
        "is_manager": is_manager,
        "total_orders": len(orders),
        "total_distinct_items": len(final_items),
        "total_quantity": round(total_qty_sum, 2),
        "total_amount": round(total_val_sum, 2),
        "items": final_items,
        "orders": orders_summary,
    }


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
        .join(User, TempOrder.user_id == User.user_id)
        .where(TempOrder.id == order_id, User.company_id == user.company_id)
        .options(
            selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group),
            selectinload(TempOrder.ledger),
            selectinload(TempOrder.user),
            selectinload(TempOrder.acted_by),
        )
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    is_manager = await can_manage_all_orders(user, db)

    # Access control: managers can view any order; regular salesperson only their own
    if not is_manager and order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    # Time check (30 minutes edit window for regular salesperson; managers can edit anytime)
    is_editable = check_order_editable(order, is_manager)

    res = format_order_response(order)
    res["is_editable"] = is_editable
    return res


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
        .join(User, TempOrder.user_id == User.user_id)
        .where(TempOrder.id == order_id, User.company_id == user.company_id)
        .options(selectinload(TempOrder.items))
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    is_manager = await can_manage_all_orders(user, db)

    if not is_manager and order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this order")

    if not check_order_editable(order, is_manager):
        if order.status != "pending":
            raise HTTPException(status_code=400, detail="Only pending orders can be edited")
        raise HTTPException(status_code=400, detail="The 30-minute editing window has expired")

    if not req.ledger_id and not req.custom_customer_name:
        raise HTTPException(status_code=400, detail="Either ledger_id or custom_customer_name is required")

    clean_gstin = (
        req.custom_customer_gstin.strip().upper()[:15]
        if req.custom_customer_gstin and req.custom_customer_gstin.strip()
        else None
    )

    if req.ledger_id:
        ledger_query = await db.execute(
            select(MstLedger).where(MstLedger.ledger_id == req.ledger_id, MstLedger.company_id == user.company_id)
        )
        ledger = ledger_query.scalars().first()
        if not ledger:
            raise HTTPException(status_code=400, detail="Customer ledger not found")
        order.ledger_id = req.ledger_id
        order.custom_customer_name = None
        order.custom_customer_gstin = None
    else:
        order.ledger_id = None
        order.custom_customer_name = req.custom_customer_name[:256]
        order.custom_customer_gstin = clean_gstin

    # Delete existing items
    for item in order.items:
        await db.delete(item)
    await db.flush()

    for item in req.items:
        if not item.stock_item_id and not (item.custom_item_name and item.custom_item_name.strip()):
            raise HTTPException(status_code=400, detail="Each item must have either stock_item_id or custom_item_name.")

        if item.stock_item_id:
            stock_query = await db.execute(
                select(MstStockItem).where(MstStockItem.stock_item_id == item.stock_item_id, MstStockItem.company_id == user.company_id)
            )
            stock = stock_query.scalars().first()
            if not stock:
                raise HTTPException(status_code=400, detail=f"Stock item {item.stock_item_id} not found")

        order_item = TempOrderItem(
            order_id=order.id,
            stock_item_id=item.stock_item_id,
            custom_item_name=item.custom_item_name.strip()[:256] if item.custom_item_name else None,
            qty=item.qty,
            price=item.price,
            is_bill_required=item.bill_required,
        )
        db.add(order_item)

    order.updated_at = get_ist_now()
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
    from sqlalchemy.orm import selectinload
    from app.models.tally_core import MstStockItem, MstLedger
    result = await db.execute(
        select(TempOrder)
        .join(User, TempOrder.user_id == User.user_id)
        .where(TempOrder.id == order_id, User.company_id == user.company_id)
        .options(
            selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group),
            selectinload(TempOrder.ledger),
            selectinload(TempOrder.user),
            selectinload(TempOrder.acted_by),
        )
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if req.status not in {"done", "cancelled", "pending"}:
        raise HTTPException(status_code=400, detail="Status must be 'done', 'cancelled', or 'pending'")

    now_ist = get_ist_now()
    order.status = req.status
    if req.status in {"done", "cancelled"}:
        order.acted_by_user_id = user.user_id
        order.acted_at = now_ist
        order.status_reason = req.reason.strip() if req.reason and req.reason.strip() else None
    elif req.status == "pending":
        order.acted_by_user_id = None
        order.acted_at = None
        order.status_reason = None

    if req.status == "done":
        # Mark all items sent as well
        for it in order.items:
            it.is_sent = True
            it.sent_qty = float(it.qty or 0)
            it.sent_at = now_ist
    elif req.status == "pending":
        # Reset all items to unsent
        for it in order.items:
            it.is_sent = False
            it.sent_qty = 0.0
            it.sent_at = None

    order.updated_at = now_ist
    await db.commit()

    # Notify order creator (salesperson)
    from app.routers.notifications import notify_user
    from app.services.notifications import order_link
    status_label = "approved" if req.status == "done" else (
        "rejected" if req.status == "cancelled" else req.status
    )
    reason_text = f" Reason: {req.reason.strip()}" if req.reason and req.reason.strip() else ""
    await notify_user(
        db=db,
        company_id=user.company_id,
        user_id=order.user_id,
        type="order_status",
        title=f"Order #{order.id} {status_label.title()}",
        message=f"Your order #{order.id} has been {status_label} by {user.username}.{reason_text}",
        reference_id=str(order.id),
        reference_type="order",
        link=order_link(order.id, order.status),
        auto_commit=True,
    )

    res = format_order_response(order)
    res["success"] = True
    return res


class ItemDispatchUpdate(BaseModel):
    is_sent: bool
    sent_qty: Optional[float] = None


@router.put("/{order_id}/items/{item_id}/dispatch")
async def update_order_item_dispatch(
    order_id: int,
    item_id: int,
    req: ItemDispatchUpdate,
    user: User = Depends(require_permission("orders", "update")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload
    from app.models.tally_core import MstStockItem, MstLedger
    result = await db.execute(
        select(TempOrder)
        .join(User, TempOrder.user_id == User.user_id)
        .where(TempOrder.id == order_id, User.company_id == user.company_id)
        .options(
            selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group),
            selectinload(TempOrder.ledger),
            selectinload(TempOrder.user),
            selectinload(TempOrder.acted_by),
        )
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot dispatch items on a cancelled order")

    is_manager = await can_manage_all_orders(user, db)
    if not is_manager and order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this order")

    target_item = next((it for it in order.items if it.id == item_id), None)
    if not target_item:
        raise HTTPException(status_code=404, detail="Order item not found")

    now_ist = get_ist_now()
    target_item.is_sent = req.is_sent
    if req.is_sent:
        if req.sent_qty is not None and req.sent_qty > 0:
            target_item.sent_qty = min(float(target_item.qty), float(req.sent_qty))
        else:
            target_item.sent_qty = float(target_item.qty)
        target_item.sent_at = now_ist
    else:
        target_item.sent_qty = 0.0
        target_item.sent_at = None

    recalculate_order_dispatch_state(order, now_ist)
    order.acted_by_user_id = user.user_id
    order.acted_at = now_ist
    order.updated_at = now_ist
    await db.commit()

    return format_order_response(order)


class BatchItemDispatchEntry(BaseModel):
    item_id: int
    is_sent: bool
    sent_qty: Optional[float] = None


class BatchItemDispatchPayload(BaseModel):
    items: List[BatchItemDispatchEntry]


@router.put("/{order_id}/items-dispatch")
async def update_order_items_dispatch_batch(
    order_id: int,
    req: BatchItemDispatchPayload,
    user: User = Depends(require_permission("orders", "update")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload
    from app.models.tally_core import MstStockItem, MstLedger
    result = await db.execute(
        select(TempOrder)
        .join(User, TempOrder.user_id == User.user_id)
        .where(TempOrder.id == order_id, User.company_id == user.company_id)
        .options(
            selectinload(TempOrder.items).selectinload(TempOrderItem.stock_item).selectinload(MstStockItem.group),
            selectinload(TempOrder.ledger),
            selectinload(TempOrder.user),
            selectinload(TempOrder.acted_by),
        )
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot dispatch items on a cancelled order")

    is_manager = await can_manage_all_orders(user, db)
    if not is_manager and order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this order")

    now_ist = get_ist_now()
    items_map = {it.id: it for it in order.items}
    for entry in req.items:
        it = items_map.get(entry.item_id)
        if it:
            it.is_sent = entry.is_sent
            if entry.is_sent:
                if entry.sent_qty is not None and entry.sent_qty > 0:
                    it.sent_qty = min(float(it.qty), float(entry.sent_qty))
                else:
                    it.sent_qty = float(it.qty)
                it.sent_at = now_ist
            else:
                it.sent_qty = 0.0
                it.sent_at = None

    recalculate_order_dispatch_state(order, now_ist)
    order.acted_by_user_id = user.user_id
    order.acted_at = now_ist
    order.updated_at = now_ist
    await db.commit()

    return format_order_response(order)

