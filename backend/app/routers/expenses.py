"""
Expenses Router — expense claim submission and admin approval.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, desc
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

from app.core.database import get_db, Base
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.core.config import settings

# ─── Model ───────────────────────────────────────────────────────────────────

class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    salesperson_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    amount = Column(Float, nullable=False)
    expense_date = Column(Date, nullable=False)
    category = Column(String(128), nullable=False)
    payment_mode = Column(String(64), nullable=False)
    narration = Column(String(1024), nullable=True)
    reference_no = Column(String(256), nullable=True)
    receipt_photo_url = Column(String(1024), nullable=True)
    status = Column(String(32), default="pending")  # pending, approved, rejected
    cancel_reason = Column(String(1024), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    salesperson = relationship("User", foreign_keys=[salesperson_user_id])

# ─── Schemas ─────────────────────────────────────────────────────────────────

class ExpenseCreate(BaseModel):
    amount: float
    date: str
    category: str
    payment_mode: str
    is_salesman_related: Optional[bool] = False
    salesperson_user_id: Optional[int] = None
    narration: Optional[str] = None
    reference_no: Optional[str] = None
    photo_base64: Optional[str] = None

class ExpenseApprove(BaseModel):
    status: str  # approved | rejected
    reason: Optional[str] = None
    cancel_reason: Optional[str] = None

# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/expenses", tags=["Expenses"])

VALID_CATEGORIES = {
    'Office Rent',
    'Salary',
    'Travel / Commute',
    'Transport/E-Rickshaw',
    'Food & Meals',
    'Utilities / Internet',
    'Fuel / Maintenance',
    'Stationery',
    'Miscellaneous / Others',
    # Legacy compatibility
    'Travel',
    'Food',
    'Petrol',
    'Toll',
    'Accommodation',
    'Other',
}
VALID_MODES = {'Cash', 'Bank', 'Online'}


@router.get("/salespersons")
async def get_expense_salespersons(
    user: User = Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List team members in current company for expense attribution."""
    query = await db.execute(
        select(User).options(selectinload(User.role)).where(
            User.company_id == user.company_id,
            User.is_active == True
        )
    )
    users = query.scalars().all()
    return [
        {
            "user_id": u.user_id,
            "username": u.username,
            "role_name": u.role.name if u.role else "Salesperson"
        }
        for u in users
    ]


@router.post("")
async def create_expense(
    req: ExpenseCreate,
    user: User = Depends(require_permission("expenses", "create")),
    db: AsyncSession = Depends(get_db),
):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    if req.amount > 10_000_000:
        raise HTTPException(status_code=400, detail="Amount exceeds maximum limit")
    if req.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Choose from: {', '.join(VALID_CATEGORIES)}")
    if req.payment_mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid payment mode. Choose from: {', '.join(VALID_MODES)}")

    try:
        exp_date = date.fromisoformat(req.date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    receipt_url = None
    if req.photo_base64:
        try:
            from app.services.imagekit_service import upload_customer_photo
            import time
            ik_res = upload_customer_photo(
                file_base64=req.photo_base64,
                file_name=f"expense_{user.user_id}_{int(time.time())}.jpg",
                folder=f"/expenses/user_{user.user_id}",
                tags=["expense_receipt", f"user_{user.user_id}"]
            )
            receipt_url = ik_res.get("url")
        except Exception as ik_err:
            print(f"Warning: ImageKit upload failed for expense: {ik_err}")
            if len(req.photo_base64) < 500_000:
                receipt_url = req.photo_base64

    # Determine salesperson attribution
    assigned_salesperson_id = None
    if req.is_salesman_related:
        assigned_salesperson_id = req.salesperson_user_id or user.user_id
    elif not user.role or user.role.name.lower() not in ("admin", "superadmin", "owner"):
        # If created by a regular salesperson, attribute to themselves
        assigned_salesperson_id = user.user_id

    expense = Expense(
        user_id=user.user_id,
        salesperson_user_id=assigned_salesperson_id,
        amount=req.amount,
        expense_date=exp_date,
        category=req.category,
        payment_mode=req.payment_mode,
        narration=req.narration[:1024] if req.narration else None,
        reference_no=req.reference_no[:256] if req.reference_no else None,
        receipt_photo_url=receipt_url,
        status="pending",
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)

    # Notify admins of submitted expense
    from app.routers.notifications import notify_admins
    await notify_admins(
        db=db,
        company_id=user.company_id,
        type="expense_created",
        title="New Expense Submitted",
        message=f"{user.username} submitted an expense of ₹{float(expense.amount):,.2f} ({expense.category})",
        reference_id=str(expense.id),
        reference_type="expense",
        exclude_user_id=user.user_id,
        auto_commit=True,
    )

    return {"success": True, "id": expense.id, "message": "Expense submitted successfully"}


def format_expense_item(e: Expense) -> dict:
    salesperson_name = None
    if e.salesperson:
        salesperson_name = e.salesperson.username or e.salesperson.email
    elif e.salesperson_user_id:
        salesperson_name = f"User #{e.salesperson_user_id}"
    elif e.user:
        salesperson_name = e.user.username or e.user.email

    return {
        "id": e.id,
        "amount": e.amount,
        "date": e.expense_date.isoformat() if e.expense_date else None,
        "category": e.category,
        "payment_mode": e.payment_mode,
        "narration": e.narration,
        "reference_no": e.reference_no,
        "receipt_photo_url": e.receipt_photo_url,
        "status": e.status,
        "cancel_reason": e.cancel_reason,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "user_id": e.user_id,
        "created_by": e.user.username if e.user else f"User #{e.user_id}",
        "salesperson_user_id": e.salesperson_user_id,
        "salesperson": salesperson_name if e.salesperson_user_id else None,
        "is_salesman_related": bool(e.salesperson_user_id),
    }


@router.get("")
async def list_expenses(
    scope: Optional[str] = Query(None, description="'all' to view team claims (admin only), 'my' for personal claims"),
    status: Optional[str] = Query(None),
    salesperson_id: Optional[int] = Query(None),
    user: User = Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    """
    List expenses.
    If current user is an Admin, defaults to all company team expenses (or filtered by scope/salesperson).
    Non-admins only see their own expenses.
    """
    is_admin = bool(user.role and user.role.name.lower() in ("admin", "superadmin", "owner"))

    if is_admin and scope != "my":
        stmt = (
            select(Expense)
            .options(selectinload(Expense.user), selectinload(Expense.salesperson))
            .join(User, Expense.user_id == User.user_id)
            .where(User.company_id == user.company_id)
        )
        if salesperson_id:
            from sqlalchemy import or_
            stmt = stmt.where(or_(Expense.salesperson_user_id == salesperson_id, Expense.user_id == salesperson_id))
    else:
        stmt = (
            select(Expense)
            .options(selectinload(Expense.user), selectinload(Expense.salesperson))
            .where(Expense.user_id == user.user_id)
        )

    if status and status != "all":
        stmt = stmt.where(Expense.status == status)

    stmt = stmt.order_by(desc(Expense.created_at)).limit(200)
    result = await db.execute(stmt)
    expenses = result.scalars().all()
    return [format_expense_item(e) for e in expenses]


@router.get("/all")
async def list_all_expenses(
    current_user: User = Depends(require_permission("admin", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Admin: list all expenses for current company."""
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.user), selectinload(Expense.salesperson))
        .join(User, Expense.user_id == User.user_id)
        .where(User.company_id == current_user.company_id)
        .order_by(desc(Expense.created_at))
        .limit(500)
    )
    expenses = result.scalars().all()
    return [format_expense_item(e) for e in expenses]


@router.put("/{expense_id}/status")
@router.patch("/{expense_id}/approve")
async def approve_expense(
    expense_id: int,
    req: ExpenseApprove,
    current_user: User = Depends(require_permission("admin", "update")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Expense)
        .join(User, Expense.user_id == User.user_id)
        .where(Expense.id == expense_id, User.company_id == current_user.company_id)
    )
    expense = result.scalars().first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if req.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")
    expense.status = req.status
    reason = req.cancel_reason or req.reason
    if reason:
        expense.cancel_reason = reason[:1024]
    await db.commit()

    # Notify expense creator (salesperson)
    from app.routers.notifications import notify_user
    await notify_user(
        db=db,
        company_id=current_user.company_id,
        user_id=expense.user_id,
        type="expense_status",
        title=f"Expense #{expense.id} {expense.status.title()}",
        message=f"Your expense #{expense.id} for ₹{float(expense.amount):,.2f} has been {expense.status}." + (f" Reason: {reason}" if reason else ""),
        reference_id=str(expense.id),
        reference_type="expense",
        auto_commit=True,
    )

    return {"success": True, "status": expense.status}

