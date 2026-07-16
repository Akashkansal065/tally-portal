"""
Expenses Router — expense claim submission and admin approval.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, desc
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date

from app.core.database import get_db, Base
from app.core.permissions import require_permission
from app.models.user import User

# ─── Model ───────────────────────────────────────────────────────────────────

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
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

# ─── Schemas ─────────────────────────────────────────────────────────────────

class ExpenseCreate(BaseModel):
    amount: float
    date: str
    category: str
    payment_mode: str
    narration: Optional[str] = None
    reference_no: Optional[str] = None
    photo_base64: Optional[str] = None

class ExpenseApprove(BaseModel):
    status: str  # approved | rejected
    reason: Optional[str] = None

# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/expenses", tags=["Expenses"])

VALID_CATEGORIES = {'Travel', 'Food', 'Petrol', 'Toll', 'Accommodation', 'Stationery', 'Other'}
VALID_MODES = {'Cash', 'Bank', 'Online'}


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

    expense = Expense(
        user_id=user.user_id,
        amount=req.amount,
        expense_date=exp_date,
        category=req.category,
        payment_mode=req.payment_mode,
        narration=req.narration[:1024] if req.narration else None,
        reference_no=req.reference_no[:256] if req.reference_no else None,
        status="pending",
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return {"success": True, "id": expense.id, "message": "Expense submitted successfully"}


@router.get("")
async def list_expenses(
    user: User = Depends(require_permission("expenses", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List current user's own expenses."""
    result = await db.execute(
        select(Expense)
        .where(Expense.user_id == user.user_id)
        .order_by(desc(Expense.created_at))
        .limit(100)
    )
    expenses = result.scalars().all()
    return [
        {
            "id": e.id,
            "amount": e.amount,
            "date": e.expense_date.isoformat() if e.expense_date else None,
            "category": e.category,
            "payment_mode": e.payment_mode,
            "narration": e.narration,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in expenses
    ]


@router.get("/all")
async def list_all_expenses(
    current_user: User = Depends(require_permission("admin", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Admin: list all expenses."""
    result = await db.execute(
        select(Expense).order_by(desc(Expense.created_at)).limit(500)
    )
    return result.scalars().all()


@router.patch("/{expense_id}/approve")
async def approve_expense(
    expense_id: int,
    req: ExpenseApprove,
    current_user: User = Depends(require_permission("admin", "update")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Expense).where(Expense.id == expense_id))
    expense = result.scalars().first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if req.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")
    expense.status = req.status
    if req.reason:
        expense.cancel_reason = req.reason[:1024]
    await db.commit()
    return {"success": True, "status": expense.status}
