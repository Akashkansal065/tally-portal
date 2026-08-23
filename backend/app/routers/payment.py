from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Any
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
    from app.models.tally_core import MstGroup

    stmt = (
        select(TrnBill)
        .join(MstLedger, TrnBill.party_ledger_id == MstLedger.ledger_id)
        .options(selectinload(TrnBill.party))
        .where(
            TrnBill.company_id == user.company_id,
            TrnBill.status != "Settled"
        )
    )
    if party_ledger_id:
        stmt = stmt.where(TrnBill.party_ledger_id == party_ledger_id)
    else:
        # Filter to Sundry Debtors hierarchy only
        all_groups_res = await db.execute(
            select(MstGroup).where(MstGroup.company_id == user.company_id)
        )
        all_groups = all_groups_res.scalars().all()
        debtor_group_ids = set()
        for g in all_groups:
            if g.name.strip().lower() == "sundry debtors":
                debtor_group_ids.add(g.group_id)
        changed = True
        while changed:
            changed = False
            for g in all_groups:
                if g.parent_group_id in debtor_group_ids and g.group_id not in debtor_group_ids:
                    debtor_group_ids.add(g.group_id)
                    changed = True
        if debtor_group_ids:
            stmt = stmt.where(MstLedger.group_id.in_(debtor_group_ids))

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
    bills: List[Any],
    vpa: str,
    dunning_level: str,
    bucket_name: Optional[str] = None
) -> tuple[str, str]:
    params = {
        "pa": vpa,
        "pn": company_name,
        "am": f"{float(total_due):.2f}",
        "cu": "INR",
        "tn": f"Bill Due {party_name[:15]}"
    }
    upi_uri = f"upi://pay?{urllib.parse.urlencode(params)}"

    header = "*PAYMENT REMINDER*"
    if dunning_level == "URGENT":
        header = "*[URGENT] OVERDUE PAYMENT NOTICE*"
    elif dunning_level == "FORMAL":
        header = "*OUTSTANDING PAYMENT REMINDER*"

    bucket_desc = f" ({bucket_name} overdue)" if bucket_name and bucket_name.upper() not in ["ALL", "OVERDUE"] else ""
    lines = [
        f"{header} — *{company_name}*",
        "",
        f"Dear *{party_name}*,",
        f"Hope you are doing well.",
        "",
        f"This is a reminder that you have a pending balance of *₹{total_due:,.2f}*{bucket_desc} across *{len(bills)} bill(s)*.",
        "",
        "*Itemized Invoices:*"
    ]

    for b in bills[:5]:
        amt = float(getattr(b, "outstanding_amount", None) or (getattr(b, "bill_amount", 0) - getattr(b, "settled_amount", 0)))
        b_ref = getattr(b, "bill_reference", None) or f"#{getattr(b, 'bill_id', '')}"
        due_val = getattr(b, "due_date", None)
        bill_val = getattr(b, "bill_date", None)
        d_str = f"Due: {due_val}" if due_val else (f"Dated: {bill_val}" if bill_val else "")
        lines.append(f"• *{b_ref}* ({d_str}): ₹{amt:,.2f}")

    if len(bills) > 5:
        lines.append(f"• ... and {len(bills) - 5} more invoice(s)")

    lines.extend([
        "",
        "*Instant Direct UPI Payment:*",
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

    # 2. Resolve Sundry Debtors group IDs (including sub-groups)
    #    Only DEBTORS should appear in aging — never Sundry Creditors (suppliers/vendors)
    from app.models.tally_core import MstGroup
    from datetime import timedelta
    from sqlalchemy import text

    all_groups_res = await db.execute(
        select(MstGroup).where(MstGroup.company_id == user.company_id)
    )
    all_groups = all_groups_res.scalars().all()
    debtor_group_ids = set()

    for g in all_groups:
        if g.name.strip().lower() == "sundry debtors":
            debtor_group_ids.add(g.group_id)

    changed = True
    while changed:
        changed = False
        for g in all_groups:
            if g.parent_group_id in debtor_group_ids and g.group_id not in debtor_group_ids:
                debtor_group_ids.add(g.group_id)
                changed = True

    if not debtor_group_ids:
        debtor_group_ids = {0}

    # 3. Query all debtors with net balance strictly from voucher entries (Debits - Credits)
    group_ids_str = ",".join(str(gid) for gid in debtor_group_ids)
    debtors_q = await db.execute(text(f"""
        SELECT 
            l.ledger_id, 
            l.name as party_name,
            l.mobile,
            l.phone,
            l.email,
            l.credit_period_days,
            COALESCE(SUM(e.debit_amount), 0) as total_debit,
            COALESCE(SUM(e.credit_amount), 0) as total_credit
        FROM tally_sync.ledgers l
        LEFT JOIN tally_sync.voucher_entries e ON l.ledger_id = e.ledger_id
        LEFT JOIN tally_sync.vouchers v ON e.voucher_id = v.voucher_id AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
        WHERE l.company_id = :comp_id AND l.group_id IN ({group_ids_str})
        GROUP BY l.ledger_id, l.name, l.mobile, l.phone, l.email, l.credit_period_days
    """), {"comp_id": user.company_id})
    debtors = debtors_q.all()

    today = date.today()
    party_map: dict[int, dict] = {}

    total_receivables = 0.0
    total_overdue = 0.0
    total_current = 0.0
    bucket_0_30 = 0.0
    bucket_31_60 = 0.0
    bucket_61_90 = 0.0
    bucket_90_plus = 0.0

    for d in debtors:
        net_bal = float(d.total_debit) - float(d.total_credit)
        
        # If customer has settled or has advance credit balance, no debt to collect
        if net_bal <= 0.01:
            continue

        net_bal = round(net_bal, 2)
        total_receivables += net_bal
        party_id = d.ledger_id
        credit_period = d.credit_period_days or 0
        rem_bal = net_bal

        p_current = 0.0
        p_1_30 = 0.0
        p_31_60 = 0.0
        p_61_90 = 0.0
        p_90_plus = 0.0
        bills_list = []

        # Fetch customer's sales vouchers in descending order (FIFO backwards from most recent)
        sales_q = await db.execute(text("""
            SELECT v.voucher_id, v.voucher_number, v.voucher_date, v.total_amount
            FROM tally_sync.vouchers v
            JOIN tally_sync.voucher_types vt ON v.voucher_type_id = vt.voucher_type_id
            JOIN tally_sync.voucher_entries e ON v.voucher_id = e.voucher_id
            WHERE e.ledger_id = :ledger_id AND vt.name = 'Sales' 
              AND COALESCE(v.is_cancelled, FALSE) = FALSE AND COALESCE(v.is_optional, FALSE) = FALSE
            ORDER BY v.voucher_date DESC, v.voucher_id DESC
        """), {"ledger_id": party_id})
        sales_invoices = sales_q.all()

        for inv in sales_invoices:
            if rem_bal <= 0.001:
                break
            inv_amt = float(inv.total_amount or 0.0)
            allocated = min(rem_bal, inv_amt)
            if allocated <= 0:
                continue

            inv_date = inv.voucher_date
            effective_due_date = inv_date + timedelta(days=credit_period) if inv_date else None
            days_overdue = (today - effective_due_date).days if effective_due_date else 0
            days_overdue = max(0, days_overdue)

            if days_overdue == 0:
                p_current += allocated
                total_current += allocated
            elif days_overdue <= 30:
                p_1_30 += allocated
                bucket_0_30 += allocated
                total_overdue += allocated
            elif days_overdue <= 60:
                p_31_60 += allocated
                bucket_31_60 += allocated
                total_overdue += allocated
            elif days_overdue <= 90:
                p_61_90 += allocated
                bucket_61_90 += allocated
                total_overdue += allocated
            else:
                p_90_plus += allocated
                bucket_90_plus += allocated
                total_overdue += allocated

            bill_item = CustomerAgingBill(
                bill_id=inv.voucher_id,
                voucher_id=inv.voucher_id,
                bill_reference=inv.voucher_number or f"INV-{inv.voucher_id}",
                bill_date=inv_date.isoformat() if inv_date else "",
                due_date=effective_due_date.isoformat() if effective_due_date else None,
                bill_amount=inv_amt,
                settled_amount=round(inv_amt - allocated, 2),
                outstanding_amount=round(allocated, 2),
                days_overdue=days_overdue,
                status="Partially Settled" if allocated < inv_amt else "Open"
            )
            bills_list.append(bill_item)
            rem_bal -= allocated

        # If opening balance or historic pre-sync invoices remain unpaid
        if rem_bal > 0.01:
            p_90_plus += rem_bal
            bucket_90_plus += rem_bal
            total_overdue += rem_bal
            bills_list.append(CustomerAgingBill(
                bill_id=0,
                voucher_id=None,
                bill_reference="Opening / Historic Balance",
                bill_date="",
                due_date=None,
                bill_amount=round(rem_bal, 2),
                settled_amount=0.0,
                outstanding_amount=round(rem_bal, 2),
                days_overdue=91,
                status="Open"
            ))

        party_map[party_id] = {
            "party_ledger_id": party_id,
            "party_name": d.party_name,
            "phone": d.mobile or d.phone,
            "email": d.email,
            "credit_period_days": credit_period,
            "total_outstanding": net_bal,
            "current_not_due": round(p_current, 2),
            "days_1_30": round(p_1_30, 2),
            "days_31_60": round(p_31_60, 2),
            "days_61_90": round(p_61_90, 2),
            "days_90_plus": round(p_90_plus, 2),
            "open_bills_count": len(bills_list),
            "overdue_bills_count": sum(1 for b in bills_list if b.days_overdue > 0),
            "bills": bills_list
        }

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

    aging_data = await get_aging_dashboard(user=user, db=db)
    cust = next((c for c in aging_data.customers if c.party_ledger_id == req.party_ledger_id), None)
    if not cust:
        # Fallback in case party is not found in debtor aging
        party_res = await db.execute(
            select(MstLedger).where(MstLedger.ledger_id == req.party_ledger_id, MstLedger.company_id == user.company_id)
        )
        party = party_res.scalars().first()
        if not party:
            raise HTTPException(status_code=404, detail="Party ledger not found.")
        raise HTTPException(status_code=400, detail="Party has no outstanding balance to collect.")

    bucket_filter = (req.aging_bucket or "ALL").upper().strip()
    if bucket_filter in ["90+", "90", "90+ DAYS", "OVERDUE > 90 DAYS"]:
        target_bills = [b for b in cust.bills if b.days_overdue > 90]
        total_due = cust.days_90_plus or sum(b.outstanding_amount for b in target_bills)
    elif bucket_filter in ["61-90", "61-90 DAYS", "60-90"]:
        target_bills = [b for b in cust.bills if 60 < b.days_overdue <= 90]
        total_due = cust.days_61_90 or sum(b.outstanding_amount for b in target_bills)
    elif bucket_filter in ["31-60", "31-60 DAYS", "30-60"]:
        target_bills = [b for b in cust.bills if 30 < b.days_overdue <= 60]
        total_due = cust.days_31_60 or sum(b.outstanding_amount for b in target_bills)
    elif bucket_filter in ["0-30", "0-30 DAYS", "1-30", "1-30 DAYS"]:
        target_bills = [b for b in cust.bills if b.days_overdue <= 30]
        total_due = (cust.current_not_due + cust.days_1_30) or sum(b.outstanding_amount for b in target_bills)
    elif bucket_filter == "OVERDUE":
        target_bills = [b for b in cust.bills if b.days_overdue > 0]
        total_due = sum(b.outstanding_amount for b in target_bills)
    else:
        target_bills = cust.bills
        total_due = cust.total_outstanding

    bills = target_bills if target_bills else cust.bills
    if not target_bills:
        total_due = cust.total_outstanding

    dunning = req.dunning_level.upper() if req.dunning_level != "auto" else cust.dunning_level
    msg_text, upi_uri = _build_dunning_message(
        cust.party_name,
        company_name,
        total_due,
        bills,
        vpa,
        dunning,
        bucket_name=bucket_filter if bucket_filter != "ALL" else None
    )

    raw_phone = cust.phone or ""
    clean_phone = "".join(filter(str.isdigit, raw_phone))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone

    whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(msg_text)}" if clean_phone else f"https://wa.me/?text={urllib.parse.quote(msg_text)}"

    return ReminderMessageResponse(
        party_ledger_id=cust.party_ledger_id,
        party_name=cust.party_name,
        phone=cust.phone,
        email=cust.email,
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

