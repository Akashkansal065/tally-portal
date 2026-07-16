from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, datetime

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.ledger import Ledger
from app.models.payment import Bill, BillAllocation, ShopPayment
from app.models.voucher import Voucher, VoucherEntry
from app.schemas.payment import (
    BillResponse, BillAllocationCreate, BillAllocationResponse,
    OutstandingBill, AgingBucket
)

router = APIRouter(prefix="/payment", tags=["Outstanding & Payments"])

# Helper to recalculate settled amount
async def recalculate_bill_settlement(db: AsyncSession, bill_id: int):
    allocs_query = await db.execute(
        select(BillAllocation).where(BillAllocation.bill_id == bill_id)
    )
    allocs = allocs_query.scalars().all()
    settled = sum(a.amount for a in allocs)
    
    bill_query = await db.execute(select(Bill).where(Bill.bill_id == bill_id))
    bill = bill_query.scalars().first()
    if bill:
        bill.settled_amount = settled
        if settled >= bill.bill_amount:
            bill.status = "Settled"
        elif settled > 0:
            bill.status = "Partially Settled"
        else:
            bill.status = "Open"
        await db.commit()

@router.post("/allocate", response_model=BillAllocationResponse)
async def allocate_payment(
    req: BillAllocationCreate,
    user: User = Depends(require_permission("payments", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Verify voucher entry
    entry_query = await db.execute(
        select(VoucherEntry).where(VoucherEntry.entry_id == req.voucher_entry_id)
    )
    entry = entry_query.scalars().first()
    if not entry:
        raise HTTPException(status_code=400, detail="Voucher entry not found.")
        
    # Verify bill
    if req.bill_id:
        bill_query = await db.execute(
            select(Bill).where(Bill.bill_id == req.bill_id, Bill.company_id == user.company_id)
        )
        bill = bill_query.scalars().first()
        if not bill:
            raise HTTPException(status_code=400, detail="Outstanding bill not found.")
            
        # Check allocation limit
        remaining = bill.bill_amount - bill.settled_amount
        if req.amount > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Allocation amount ({req.amount}) exceeds outstanding bill amount ({remaining})."
            )
            
    allocation = BillAllocation(
        voucher_entry_id=req.voucher_entry_id,
        bill_id=req.bill_id,
        allocation_type=req.allocation_type,
        amount=req.amount
    )
    db.add(allocation)
    await db.commit()
    await db.refresh(allocation)
    
    if req.bill_id:
        await recalculate_bill_settlement(db, req.bill_id)
        
    return allocation

@router.get("/outstanding", response_model=List[OutstandingBill])
async def get_outstanding_bills(
    party_ledger_id: Optional[int] = None,
    user: User = Depends(require_permission("payments", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Bill)
        .options(selectinload(Bill.party))
        .where(
            Bill.company_id == user.company_id,
            Bill.status != "Settled"
        )
    )
    if party_ledger_id:
        stmt = stmt.where(Bill.party_ledger_id == party_ledger_id)
        
    res = await db.execute(stmt)
    bills = res.scalars().all()
    
    today = date.today()
    outstanding_list = []
    for b in bills:
        outstanding = b.bill_amount - b.settled_amount
        overdue_days = 0
        if b.due_date and today > b.due_date:
            overdue_days = (today - b.due_date).days
            
        outstanding_list.append(OutstandingBill(
            bill_id=b.bill_id,
            party_name=b.party.name,
            bill_reference=b.bill_reference,
            bill_date=b.bill_date,
            due_date=b.due_date,
            bill_amount=b.bill_amount,
            settled_amount=b.settled_amount,
            outstanding_amount=outstanding,
            overdue_days=overdue_days
        ))
        
    return outstanding_list

@router.get("/aging", response_model=List[AgingBucket])
async def get_aging_report(
    party_ledger_id: Optional[int] = None,
    user: User = Depends(require_permission("payments", "read")),
    db: AsyncSession = Depends(get_db)
):
    outstanding_bills = await get_outstanding_bills(party_ledger_id, user, db)
    
    buckets = {
        "0-30 Days": [],
        "31-60 Days": [],
        "61-90 Days": [],
        "Over 90 Days": []
    }
    
    for b in outstanding_bills:
        days = b.overdue_days
        if days <= 30:
            buckets["0-30 Days"].append(b)
        elif days <= 60:
            buckets["31-60 Days"].append(b)
        elif days <= 90:
            buckets["61-90 Days"].append(b)
        else:
            buckets["Over 90 Days"].append(b)
            
    aging_buckets = []
    for label, list_bills in buckets.items():
        total = sum(b.outstanding_amount for b in list_bills)
        aging_buckets.append(AgingBucket(
            range_label=label,
            total_outstanding=total,
            bills=list_bills
        ))
        
    return aging_buckets

from pydantic import BaseModel

class CollectRequest(BaseModel):
    ledger_id: int
    amount: float
    payment_mode: str
    comments: Optional[str] = None
    photo_base64: Optional[str] = None

@router.post("/collect")
async def collect_payment(
    req: CollectRequest,
    user: User = Depends(require_permission("payments", "create")),
    db: AsyncSession = Depends(get_db),
):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    payment = ShopPayment(
        user_id=user.user_id,
        ledger_id=req.ledger_id,
        amount=req.amount,
        payment_mode=req.payment_mode,
        comments=req.comments[:1024] if req.comments else None,
        status="pending",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return {"success": True, "id": payment.id, "message": "Payment collected and recorded"}

@router.get("/history")
async def get_payment_history(
    user: User = Depends(require_permission("payments", "read")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShopPayment)
        .where(ShopPayment.user_id == user.user_id)
        .options(selectinload(ShopPayment.ledger))
        .order_by(ShopPayment.created_at.desc())
        .limit(100)
    )
    payments = result.scalars().all()
    return [
        {
            "id": p.id,
            "ledger_name": p.ledger.name if p.ledger else "Unknown Party",
            "amount": float(p.amount),
            "payment_mode": p.payment_mode,
            "comments": p.comments,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in payments
    ]

