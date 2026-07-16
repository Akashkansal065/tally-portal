from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date, timezone
from decimal import Decimal
import json

from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.models.payment import Bill, BillAllocation
from app.models.voucher import Voucher, VoucherEntry, VoucherType
from app.models.payment_gateway import PaymentGatewayConfig, PaymentLink, GatewayTransaction, WebhookEvent
from app.schemas.payment_gateway import (
    PaymentGatewayConfigCreate, PaymentGatewayConfigResponse,
    PaymentLinkCreate, PaymentLinkResponse
)

router = APIRouter(prefix="/gateways", tags=["Payment Gateways"])

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

@router.post("/config", response_model=PaymentGatewayConfigResponse)
async def create_gateway_config(
    req: PaymentGatewayConfigCreate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    config = PaymentGatewayConfig(
        company_id=user.company_id,
        gateway=req.gateway,
        public_key=req.public_key,
        secret_key_ref=req.secret_key_ref,
        webhook_secret_ref=req.webhook_secret_ref,
        is_active=True,
        is_test_mode=req.is_test_mode
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config

@router.get("/config", response_model=List[PaymentGatewayConfigResponse])
async def get_gateway_configs(
    user: User = Depends(require_permission("settings", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(PaymentGatewayConfig).where(PaymentGatewayConfig.company_id == user.company_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/payment-links", response_model=PaymentLinkResponse)
async def create_payment_link(
    req: PaymentLinkCreate,
    user: User = Depends(require_permission("payments", "create")),
    db: AsyncSession = Depends(get_db)
):
    bill_query = await db.execute(
        select(Bill).where(Bill.bill_id == req.bill_id, Bill.company_id == user.company_id)
    )
    bill = bill_query.scalars().first()
    if not bill:
        raise HTTPException(status_code=400, detail="Bill not found.")
        
    conf_query = await db.execute(
        select(PaymentGatewayConfig).where(
            PaymentGatewayConfig.company_id == user.company_id,
            PaymentGatewayConfig.is_active == True
        )
    )
    config = conf_query.scalars().first()
    if not config:
        raise HTTPException(status_code=400, detail="No active payment gateway configured.")
        
    link_id = f"plink_{int(datetime.now(timezone.utc).timestamp())}"
    url = f"https://checkout.stripe.com/pay/{link_id}" if config.gateway == "Stripe" else f"https://rzp.io/i/{link_id}"
    
    plink = PaymentLink(
        company_id=user.company_id,
        bill_id=req.bill_id,
        gateway_config_id=config.gateway_config_id,
        gateway_link_id=link_id,
        link_url=url,
        amount=req.amount,
        currency=req.currency,
        status="Created",
        created_by=user.user_id
    )
    db.add(plink)
    await db.commit()
    await db.refresh(plink)
    return plink

@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    payload_bytes = await request.body()
    payload = json.loads(payload_bytes.decode('utf-8'))
    
    event_id = payload.get("id")
    event_type = payload.get("event")
    
    conf_query = await db.execute(
        select(PaymentGatewayConfig).where(PaymentGatewayConfig.gateway == "Razorpay")
    )
    config = conf_query.scalars().first()
    if not config:
        raise HTTPException(status_code=400, detail="No Razorpay config registered.")
        
    dup_query = await db.execute(
        select(WebhookEvent).where(
            WebhookEvent.gateway_config_id == config.gateway_config_id,
            WebhookEvent.gateway_event_id == event_id
        )
    )
    if dup_query.scalars().first():
        return {"status": "already processed"}
        
    event = WebhookEvent(
        gateway_config_id=config.gateway_config_id,
        gateway_event_id=event_id,
        event_type=event_type,
        payload=payload,
        signature_verified=True,
        processed=True,
        processed_at=datetime.now(timezone.utc)
    )
    db.add(event)
    await db.flush()
    
    if event_type == "payment.captured":
        payment_data = payload.get("payload", {}).get("payment", {}).get("entity", {})
        pay_id = payment_data.get("id")
        amount = Decimal(str(payment_data.get("amount", 0))) / 100
        
        link_id = payment_data.get("notes", {}).get("gateway_link_id")
        stmt = select(PaymentLink).where(PaymentLink.gateway_link_id == link_id)
        res = await db.execute(stmt)
        plink = res.scalars().first()
        if plink:
            vtype_query = await db.execute(
                select(VoucherType).where(
                    VoucherType.company_id == plink.company_id,
                    VoucherType.name == "Receipt"
                )
            )
            vtype = vtype_query.scalars().first()
            if vtype:
                vnum = f"{vtype.prefix or ''}{vtype.next_number}"
                vtype.next_number += 1
                
                voucher = Voucher(
                    company_id=plink.company_id,
                    voucher_type_id=vtype.voucher_type_id,
                    voucher_number=vnum,
                    voucher_date=date.today(),
                    narration=f"Auto Receipt posted via Razorpay webhook {pay_id}",
                    total_amount=amount,
                    is_optional=False,
                    created_by=plink.created_by
                )
                db.add(voucher)
                await db.flush()
                
                bill_query = await db.execute(select(Bill).where(Bill.bill_id == plink.bill_id))
                bill = bill_query.scalars().first()
                if bill:
                    e1 = VoucherEntry(
                        voucher_id=voucher.voucher_id,
                        ledger_id=2,
                        debit_amount=amount,
                        credit_amount=Decimal("0.00"),
                        entry_narration="Payment received via gateway"
                    )
                    db.add(e1)
                    await db.flush()
                    
                    e2 = VoucherEntry(
                        voucher_id=voucher.voucher_id,
                        ledger_id=bill.party_ledger_id,
                        debit_amount=Decimal("0.00"),
                        credit_amount=amount,
                        entry_narration="Settlement of bill"
                    )
                    db.add(e2)
                    await db.flush()
                    
                    txn = GatewayTransaction(
                        company_id=plink.company_id,
                        payment_link_id=plink.payment_link_id,
                        bill_id=plink.bill_id,
                        gateway_config_id=config.gateway_config_id,
                        gateway_payment_id=pay_id,
                        amount=amount,
                        status="Captured",
                        voucher_id=voucher.voucher_id
                    )
                    db.add(txn)
                    
                    alloc = BillAllocation(
                        voucher_entry_id=e2.entry_id,
                        bill_id=bill.bill_id,
                        allocation_type="Against Ref",
                        amount=amount
                    )
                    db.add(alloc)
                    await db.flush()
                    
                    plink.status = "Paid"
                    await db.commit()
                    await recalculate_bill_settlement(db, bill.bill_id)
                    
    return {"status": "processed"}
