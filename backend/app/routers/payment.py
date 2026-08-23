from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, datetime

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.models.tally_core import MstLedger
from app.models.tally_core import TrnBill, BillAllocation
from app.models.portal_core import ShopPayment
from app.models.tally_core import TrnVoucher, TrnAccounting
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
    
    bill_query = await db.execute(select(TrnBill).where(TrnBill.bill_id == bill_id))
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
        select(TrnAccounting).where(TrnAccounting.entry_id == req.voucher_entry_id)
    )
    entry = entry_query.scalars().first()
    if not entry:
        raise HTTPException(status_code=400, detail="Voucher entry not found.")
        
    # Verify bill
    if req.bill_id:
        bill_query = await db.execute(
            select(TrnBill).where(TrnBill.bill_id == req.bill_id, TrnBill.company_id == user.company_id)
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
        select(TrnBill)
        .options(selectinload(TrnBill.party))
        .where(
            TrnBill.company_id == user.company_id,
            TrnBill.status != "Settled"
        )
    )
    if party_ledger_id:
        stmt = stmt.where(TrnBill.party_ledger_id == party_ledger_id)

    res = await db.execute(stmt)
    bills = res.scalars().all()
    
    output = []
    today = date.today()
    for b in bills:
        outstanding = float(b.bill_amount - b.settled_amount)
        days = (today - b.bill_date).days if b.bill_date else 0
        output.append({
            "bill_id": b.bill_id,
            "party_name": b.party.name if b.party else "Unknown",
            "bill_reference": b.bill_reference,
            "bill_date": b.bill_date.isoformat() if b.bill_date else "",
            "due_date": b.due_date.isoformat() if b.due_date else None,
            "bill_amount": float(b.bill_amount),
            "settled_amount": float(b.settled_amount),
            "outstanding_amount": outstanding,
            "days_overdue": max(0, days),
            "status": b.status
        })
    return output


import urllib.parse
from app.core.config import settings
from app.models.portal_core import Company
from app.schemas.payment import (
    CustomerAgingBill, CustomerAgingSummary, AgingKPISummary, AgingDashboardResponse,
    ReminderMessageRequest, ReminderMessageResponse, BulkReminderRequest, BulkReminderResponse
)

def _build_dunning_message(
    party_name: str,
    company_name: str,
    total_due: float,
    bills: List[TrnBill],
    vpa: str,
    dunning_level: str
) -> tuple[str, str]:
    params = {
        "pa": vpa,
        "pn": company_name,
        "am": f"{float(total_due):.2f}",
        "cu": "INR",
        "tn": f"Bill Due {party_name[:15]}"
    }
    upi_uri = f"upi://pay?{urllib.parse.urlencode(params)}"

    header = "⚡ *PAYMENT REMINDER*"
    if dunning_level == "URGENT":
        header = "🚨 *URGENT OVERDUE PAYMENT NOTICE*"
    elif dunning_level == "FORMAL":
        header = "⚠️ *OUTSTANDING PAYMENT REMINDER*"

    lines = [
        f"{header} — *{company_name}*",
        "",
        f"Dear *{party_name}*,",
        f"Hope you are doing well.",
        "",
        f"This is a reminder that you have a total outstanding balance of *₹{total_due:,.2f}* across *{len(bills)} pending bill(s)*.",
        "",
        "📋 *Pending Invoices:*"
    ]

    for b in bills[:5]:
        amt = float(b.bill_amount - b.settled_amount)
        b_ref = b.bill_reference or f"#{b.bill_id}"
        d_str = f"Due: {b.due_date}" if b.due_date else f"Dated: {b.bill_date}"
        lines.append(f" • *{b_ref}* ({d_str}): ₹{amt:,.2f}")

    if len(bills) > 5:
        lines.append(f" • ... and {len(bills) - 5} more invoice(s)")

    lines.extend([
        "",
        "💳 *Instant Direct UPI Payment:*",
        f"UPI ID: *{vpa}*",
        f"Direct Link: {upi_uri}",
        "",
        "Kindly clear this at your earliest convenience. If payment has already been made, please reply with the UTR number.",
        "",
        f"Warm regards,",
        f"*{company_name}*"
    ])

    return "\n".join(lines), upi_uri

@router.get("/aging/dashboard", response_model=AgingDashboardResponse)
async def get_aging_dashboard(
    user: User = Depends(require_permission("payments", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns complete Debtors Aging Analysis (0-30, 31-60, 61-90, 90+ days),
    customer-level aggregated summaries, bill-level breakdowns, and dynamic UPI config.
    """
    # 1. Fetch Company for Name & UPI VPA (dynamic resolution)
    comp_res = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_res.scalars().first()
    merchant_name = company.name if company else "Merchant"
    company_upi = None
    if company and company.features and isinstance(company.features, dict):
        company_upi = company.features.get("upi_id") or company.features.get("upi_vpa")
    vpa = company_upi or settings.DEFAULT_UPI_VPA or ""

    # 2. Fetch all open bills with party ledger
    bills_stmt = (
        select(TrnBill)
        .options(selectinload(TrnBill.party))
        .where(
            TrnBill.company_id == user.company_id,
            TrnBill.status != "Settled"
        )
        .order_by(TrnBill.bill_date.asc())
    )
    bills_res = await db.execute(bills_stmt)
    bills = bills_res.scalars().all()

    # 3. Group by customer party_ledger_id
    today = date.today()
    party_map: dict[int, dict] = {}

    total_receivables = 0.0
    total_overdue = 0.0
    total_current = 0.0
    bucket_0_30 = 0.0
    bucket_31_60 = 0.0
    bucket_61_90 = 0.0
    bucket_90_plus = 0.0

    for b in bills:
        outstanding = float(b.bill_amount - b.settled_amount)
        if outstanding <= 0:
            continue

        total_receivables += outstanding
        party_id = b.party_ledger_id
        party = b.party

        credit_period = getattr(party, "bill_credit_period", 0) or 0
        effective_due_date = b.due_date
        if not effective_due_date and b.bill_date:
            from datetime import timedelta
            effective_due_date = b.bill_date + timedelta(days=credit_period)
        
        days_overdue = (today - effective_due_date).days if effective_due_date else 0
        days_overdue = max(0, days_overdue)

        if days_overdue > 0:
            total_overdue += outstanding
        else:
            total_current += outstanding

        b_current = 0.0
        b_1_30 = 0.0
        b_31_60 = 0.0
        b_61_90 = 0.0
        b_90_plus = 0.0

        if days_overdue == 0:
            b_current = outstanding
        elif days_overdue <= 30:
            b_1_30 = outstanding
            bucket_0_30 += outstanding
        elif days_overdue <= 60:
            b_31_60 = outstanding
            bucket_31_60 += outstanding
        elif days_overdue <= 90:
            b_61_90 = outstanding
            bucket_61_90 += outstanding
        else:
            b_90_plus = outstanding
            bucket_90_plus += outstanding

        bill_item = CustomerAgingBill(
            bill_id=b.bill_id,
            voucher_id=b.voucher_id,
            bill_reference=b.bill_reference or f"BILL-{b.bill_id}",
            bill_date=b.bill_date.isoformat() if b.bill_date else "",
            due_date=effective_due_date.isoformat() if effective_due_date else None,
            bill_amount=float(b.bill_amount),
            settled_amount=float(b.settled_amount),
            outstanding_amount=outstanding,
            days_overdue=days_overdue,
            status=b.status
        )

        if party_id not in party_map:
            party_map[party_id] = {
                "party_ledger_id": party_id,
                "party_name": party.name if party else f"Party #{party_id}",
                "phone": getattr(party, "mobile", None) or getattr(party, "phone", None),
                "email": getattr(party, "email", None),
                "credit_period_days": credit_period,
                "total_outstanding": 0.0,
                "current_not_due": 0.0,
                "days_1_30": 0.0,
                "days_31_60": 0.0,
                "days_61_90": 0.0,
                "days_90_plus": 0.0,
                "open_bills_count": 0,
                "overdue_bills_count": 0,
                "bills": []
            }

        p = party_map[party_id]
        p["total_outstanding"] += outstanding
        p["current_not_due"] += b_current
        p["days_1_30"] += b_1_30
        p["days_31_60"] += b_31_60
        p["days_61_90"] += b_61_90
        p["days_90_plus"] += b_90_plus
        p["open_bills_count"] += 1
        if days_overdue > 0:
            p["overdue_bills_count"] += 1
        p["bills"].append(bill_item)

    customers = []
    overdue_debtors_count = 0
    for p_id, p_data in party_map.items():
        if p_data["overdue_bills_count"] > 0:
            overdue_debtors_count += 1

        if p_data["days_90_plus"] > 0 or p_data["days_61_90"] > 0:
            dunning = "URGENT"
        elif p_data["days_31_60"] > 0:
            dunning = "FORMAL"
        elif p_data["days_1_30"] > 0:
            dunning = "GENTLE"
        else:
            dunning = "CURRENT"

        customers.append(CustomerAgingSummary(
            party_ledger_id=p_data["party_ledger_id"],
            party_name=p_data["party_name"],
            phone=p_data["phone"],
            email=p_data["email"],
            credit_period_days=p_data["credit_period_days"],
            total_outstanding=round(p_data["total_outstanding"], 2),
            current_not_due=round(p_data["current_not_due"], 2),
            days_1_30=round(p_data["days_1_30"], 2),
            days_31_60=round(p_data["days_31_60"], 2),
            days_61_90=round(p_data["days_61_90"], 2),
            days_90_plus=round(p_data["days_90_plus"], 2),
            open_bills_count=p_data["open_bills_count"],
            overdue_bills_count=p_data["overdue_bills_count"],
            dunning_level=dunning,
            bills=p_data["bills"]
        ))

    customers.sort(key=lambda x: x.total_outstanding, reverse=True)

    kpis = AgingKPISummary(
        total_receivables=round(total_receivables, 2),
        total_overdue=round(total_overdue, 2),
        total_current=round(total_current, 2),
        bucket_0_30=round(bucket_0_30, 2),
        bucket_31_60=round(bucket_31_60, 2),
        bucket_61_90=round(bucket_61_90, 2),
        bucket_90_plus=round(bucket_90_plus, 2),
        total_debtors_count=len(customers),
        overdue_debtors_count=overdue_debtors_count
    )

    return AgingDashboardResponse(
        kpis=kpis,
        customers=customers,
        upi_vpa=vpa,
        merchant_name=merchant_name
    )

@router.post("/reminders/generate-whatsapp", response_model=ReminderMessageResponse)
async def generate_whatsapp_reminder(
    req: ReminderMessageRequest,
    user: User = Depends(require_permission("payments", "create")),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a personalized WhatsApp payment reminder with live invoice list and direct UPI paylink.
    """
    comp_res = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_res.scalars().first()
    company_name = company.name if company else "Company"
    company_upi = None
    if company and company.features and isinstance(company.features, dict):
        company_upi = company.features.get("upi_id") or company.features.get("upi_vpa")
    vpa = company_upi or settings.DEFAULT_UPI_VPA or ""

    party_res = await db.execute(
        select(MstLedger).where(MstLedger.ledger_id == req.party_ledger_id, MstLedger.company_id == user.company_id)
    )
    party = party_res.scalars().first()
    if not party:
        raise HTTPException(status_code=404, detail="Party ledger not found.")

    bills_res = await db.execute(
        select(TrnBill).where(
            TrnBill.party_ledger_id == req.party_ledger_id,
            TrnBill.company_id == user.company_id,
            TrnBill.status != "Settled"
        ).order_by(TrnBill.bill_date.asc())
    )
    bills = bills_res.scalars().all()
    total_due = sum(float(b.bill_amount - b.settled_amount) for b in bills)

    dunning = req.dunning_level.upper() if req.dunning_level != "auto" else "FORMAL"
    msg_text, upi_uri = _build_dunning_message(party.name, company_name, total_due, bills, vpa, dunning)

    raw_phone = getattr(party, "mobile", None) or getattr(party, "phone", None) or ""
    clean_phone = "".join(filter(str.isdigit, raw_phone))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone

    whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(msg_text)}" if clean_phone else f"https://wa.me/?text={urllib.parse.quote(msg_text)}"

    return ReminderMessageResponse(
        party_ledger_id=party.ledger_id,
        party_name=party.name,
        phone=party.mobile or party.phone,
        email=party.email,
        total_due=round(total_due, 2),
        overdue_bills_count=len(bills),
        dunning_level=dunning,
        message_text=msg_text,
        whatsapp_url=whatsapp_url,
        upi_uri=upi_uri,
        upi_vpa=vpa
    )

@router.post("/reminders/bulk", response_model=BulkReminderResponse)
async def send_bulk_reminders(
    req: BulkReminderRequest,
    user: User = Depends(require_permission("payments", "create")),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates batch payment reminders for all selected parties or an entire aging bucket.
    """
    aging_data = await get_aging_dashboard(user=user, db=db)
    target_customers = []

    for cust in aging_data.customers:
        if req.party_ledger_ids and cust.party_ledger_id in req.party_ledger_ids:
            target_customers.append(cust)
        elif req.aging_bucket:
            if req.aging_bucket == "ALL_OVERDUE" and cust.overdue_bills_count > 0:
                target_customers.append(cust)
            elif req.aging_bucket == "1-30" and cust.days_1_30 > 0:
                target_customers.append(cust)
            elif req.aging_bucket == "31-60" and cust.days_31_60 > 0:
                target_customers.append(cust)
            elif req.aging_bucket == "61-90" and cust.days_61_90 > 0:
                target_customers.append(cust)
            elif req.aging_bucket == "90_PLUS" and cust.days_90_plus > 0:
                target_customers.append(cust)

    reminders = []
    for c in target_customers:
        party_bills_res = await db.execute(
            select(TrnBill).where(
                TrnBill.party_ledger_id == c.party_ledger_id,
                TrnBill.company_id == user.company_id,
                TrnBill.status != "Settled"
            )
        )
        bills = party_bills_res.scalars().all()
        msg_text, upi_uri = _build_dunning_message(c.party_name, aging_data.merchant_name, c.total_outstanding, bills, aging_data.upi_vpa, c.dunning_level)
        
        raw_phone = c.phone or ""
        clean_phone = "".join(filter(str.isdigit, raw_phone))
        if len(clean_phone) == 10:
            clean_phone = "91" + clean_phone
        whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(msg_text)}" if clean_phone else f"https://wa.me/?text={urllib.parse.quote(msg_text)}"

        reminders.append(ReminderMessageResponse(
            party_ledger_id=c.party_ledger_id,
            party_name=c.party_name,
            phone=c.phone,
            email=c.email,
            total_due=c.total_outstanding,
            overdue_bills_count=c.overdue_bills_count,
            dunning_level=c.dunning_level,
            message_text=msg_text,
            whatsapp_url=whatsapp_url,
            upi_uri=upi_uri,
            upi_vpa=aging_data.upi_vpa
        ))

    return BulkReminderResponse(
        total_targeted=len(reminders),
        reminders=reminders
    )

from pydantic import BaseModel

class CollectRequest(BaseModel):
    ledger_id: int
    amount: float
    payment_mode: str
    cheque_date: Optional[str] = None
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

    # Photo proof is mandatory for ALL payment modes
    if not req.photo_base64 or not req.photo_base64.strip():
        raise HTTPException(status_code=400, detail="Receipt photo proof is mandatory for all payment collections.")

    # Cheque date validation if payment mode is Cheque
    cheque_dt = None
    if req.payment_mode.lower() == "cheque":
        if not req.cheque_date:
            raise HTTPException(status_code=400, detail="Cheque date is mandatory when payment mode is Cheque.")
        try:
            cheque_dt = datetime.strptime(req.cheque_date, "%Y-%m-%d").date()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cheque date format. Use YYYY-MM-DD.")

    payment = ShopPayment(
        user_id=user.user_id,
        ledger_id=req.ledger_id,
        amount=req.amount,
        payment_mode=req.payment_mode,
        cheque_date=cheque_dt,
        comments=req.comments[:1024] if req.comments else None,
        photo_url=req.photo_base64,
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
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(ShopPayment)
        .where(ShopPayment.user_id == user.user_id)
        .options(selectinload(ShopPayment.ledger), selectinload(ShopPayment.user))
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
            "cheque_date": p.cheque_date.isoformat() if p.cheque_date else None,
            "comments": p.comments,
            "status": p.status,
            "photo_url": p.photo_url,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "user_name": p.user.username if p.user else "Salesperson",
        }
        for p in payments
    ]


@router.get("/all")
async def get_all_payments(
    current_user: User = Depends(require_permission("admin", "read")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(ShopPayment)
        .options(selectinload(ShopPayment.ledger), selectinload(ShopPayment.user))
        .order_by(ShopPayment.created_at.desc())
        .limit(500)
    )
    payments = result.scalars().all()
    return [
        {
            "id": p.id,
            "ledger_name": p.ledger.name if p.ledger else "Unknown Party",
            "amount": float(p.amount),
            "payment_mode": p.payment_mode,
            "cheque_date": p.cheque_date.isoformat() if p.cheque_date else None,
            "comments": p.comments,
            "status": p.status,
            "photo_url": p.photo_url,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "user_name": p.user.username if p.user else "Salesperson",
        }
        for p in payments
    ]


class PaymentStatusUpdate(BaseModel):
    status: str  # success | cancelled
    reason: Optional[str] = None


@router.put("/{payment_id}/status")
async def update_payment_status(
    payment_id: int,
    req: PaymentStatusUpdate,
    user: User = Depends(require_permission("admin", "update")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ShopPayment).where(ShopPayment.id == payment_id))
    payment = result.scalars().first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if req.status not in {"success", "cancelled", "pending"}:
        raise HTTPException(status_code=400, detail="Status must be 'success', 'cancelled', or 'pending'")

    payment.status = req.status
    await db.commit()
    return {"success": True, "status": payment.status}

