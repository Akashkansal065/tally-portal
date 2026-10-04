from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date, timezone
from decimal import Decimal
import json
import hmac
import hashlib

from app.core.cache import clear_company_cache
from app.core.database import get_db
from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.core.logging_config import get_logger
from app.core.permissions import require_permission
from app.models.portal_core import User, SyncQueue
from app.models.tally_core import TrnBill, BillAllocation, MstLedger
from app.models.tally_core import TrnVoucher, TrnAccounting, MstVoucherType
from app.models.portal_core import PaymentGatewayConfig, PaymentLink, GatewayTransaction, WebhookEvent
from app.schemas.payment_gateway import (
    PaymentGatewayConfigCreate, PaymentGatewayConfigResponse,
    PaymentLinkCreate, PaymentLinkResponse
)

router = APIRouter(prefix="/gateways", tags=["Payment Gateways"])
logger = get_logger("app.routers.payment_gateway")

# Razorpay events that carry a captured payment for one of our payment links
SETTLEMENT_EVENTS = ("payment.captured", "payment_link.paid")

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

@router.post("/config", response_model=PaymentGatewayConfigResponse)
async def create_gateway_config(
    req: PaymentGatewayConfigCreate,
    user: User = Depends(require_permission("settings", "update")),
    db: AsyncSession = Depends(get_db)
):
    ledger_query = await db.execute(
        select(MstLedger.ledger_id).where(
            MstLedger.ledger_id == req.settlement_ledger_id,
            MstLedger.company_id == user.company_id
        )
    )
    if ledger_query.scalars().first() is None:
        raise HTTPException(status_code=400, detail="Settlement ledger not found in this company.")

    config = PaymentGatewayConfig(
        company_id=user.company_id,
        gateway=req.gateway,
        public_key=req.public_key,
        secret_key_ref=req.secret_key_ref,
        webhook_secret_ref=req.webhook_secret_ref,
        settlement_ledger_id=req.settlement_ledger_id,
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
        select(TrnBill).where(TrnBill.bill_id == req.bill_id, TrnBill.company_id == user.company_id)
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

def _razorpay_signature_valid(secret: str, body: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return bool(signature) and hmac.compare_digest(expected, signature)


def _payment_link_id(payload: dict) -> Optional[str]:
    """Our gateway_link_id, from a payment_link entity or from the payment's notes."""
    body = payload.get("payload") or {}
    link_entity = (body.get("payment_link") or {}).get("entity") or {}
    if link_entity.get("id"):
        return link_entity["id"]
    notes = ((body.get("payment") or {}).get("entity") or {}).get("notes")
    # Razorpay sends notes as [] when a payment has none
    return notes.get("gateway_link_id") if isinstance(notes, dict) else None


class _WebhookNotPostable(Exception):
    """A verified payment that cannot be posted yet (e.g. missing setup). Razorpay will retry."""


@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    # 1. Resolve the tenant from our own payment link; the config is always that link's company's.
    link_id = _payment_link_id(payload)
    plink = None
    if link_id:
        plink = (await db.execute(
            select(PaymentLink).where(PaymentLink.gateway_link_id == link_id)
        )).scalars().first()
    config = None
    if plink:
        config = (await db.execute(
            select(PaymentGatewayConfig).where(
                PaymentGatewayConfig.gateway_config_id == plink.gateway_config_id,
                PaymentGatewayConfig.company_id == plink.company_id,
                PaymentGatewayConfig.gateway == "Razorpay"
            )
        )).scalars().first()
    if not plink or not config:
        # Not one of our payment links: acknowledge without touching the database
        return {"status": "ignored"}

    # 2. Fail closed: no secret means no way to authenticate the caller.
    webhook_secret = config.webhook_secret_ref or settings.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret:
        logger.error(f"Razorpay webhook rejected: no webhook secret configured for gateway config #{config.gateway_config_id}")
        raise HTTPException(status_code=503, detail="Webhook secret not configured.")
    if not _razorpay_signature_valid(webhook_secret, body, signature):
        logger.warning(f"Razorpay webhook rejected: invalid signature for gateway config #{config.gateway_config_id}")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    # 3. Idempotency per delivery. Razorpay puts the event id in a header, not the body.
    event_id = (
        request.headers.get("X-Razorpay-Event-Id")
        or payload.get("id")
        or hashlib.sha256(body).hexdigest()
    )
    event_type = payload.get("event") or "unknown"
    event = (await db.execute(
        select(WebhookEvent).where(
            WebhookEvent.gateway_config_id == config.gateway_config_id,
            WebhookEvent.gateway_event_id == event_id
        )
    )).scalars().first()
    if event and event.processed:
        return {"status": "already processed"}
    if not event:
        event = WebhookEvent(
            gateway_config_id=config.gateway_config_id,
            gateway_event_id=event_id,
            event_type=event_type,
            payload=payload,
            signature_verified=True,
            processed=False
        )
        db.add(event)
        await db.flush()

    if event_type not in SETTLEMENT_EVENTS:
        event.processed = True
        event.processed_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "ignored"}

    try:
        result = await _post_gateway_receipt(db, payload, plink, config)
    except _WebhookNotPostable as e:
        event.processing_error = str(e)[:500]
        await db.commit()
        logger.error(f"Razorpay payment for link {link_id} not posted: {e}")
        # Non-2xx so Razorpay retries after the setup is fixed
        raise HTTPException(status_code=503, detail="Payment could not be posted yet.")

    event.processed = True
    event.processed_at = datetime.now(timezone.utc)
    event.processing_error = None
    await db.commit()

    if result.get("bill_id"):
        await recalculate_bill_settlement(db, result["bill_id"])
        clear_company_cache(plink.company_id)
    return {"status": result["status"]}


async def _post_gateway_receipt(db: AsyncSession, payload: dict, plink: PaymentLink, config: PaymentGatewayConfig) -> dict:
    """Posts a Receipt voucher for a captured payment, scoped entirely to the payment link's company,
    and queues it for Tally. Leaves committing to the caller."""
    company_id = plink.company_id
    payment = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
    pay_id = payment.get("id")
    if not pay_id or payment.get("status") not in (None, "captured"):
        raise _WebhookNotPostable(f"Payment entity missing or not captured (status={payment.get('status')}).")
    amount = (Decimal(str(payment.get("amount", 0))) / 100).quantize(Decimal("0.01"))
    if amount <= 0:
        raise _WebhookNotPostable("Payment amount is zero.")

    # Lock the link so concurrent deliveries for the same payment (payment.captured and
    # payment_link.paid) serialize; locking reads also see the other delivery's committed rows.
    plink = (await db.execute(
        select(PaymentLink).where(PaymentLink.payment_link_id == plink.payment_link_id)
        .with_for_update().execution_options(populate_existing=True)
    )).scalars().first()
    already_posted = (await db.execute(
        select(GatewayTransaction).where(
            GatewayTransaction.gateway_config_id == config.gateway_config_id,
            GatewayTransaction.gateway_payment_id == pay_id
        ).with_for_update()
    )).scalars().first()
    if already_posted:
        return {"status": "duplicate payment"}

    settlement_ledger = None
    if config.settlement_ledger_id:
        settlement_ledger = (await db.execute(
            select(MstLedger).where(
                MstLedger.ledger_id == config.settlement_ledger_id,
                MstLedger.company_id == company_id
            )
        )).scalars().first()
    if not settlement_ledger:
        raise _WebhookNotPostable(f"Gateway config #{config.gateway_config_id} has no valid settlement ledger.")

    bill = (await db.execute(
        select(TrnBill).where(TrnBill.bill_id == plink.bill_id, TrnBill.company_id == company_id)
    )).scalars().first()
    if not bill:
        raise _WebhookNotPostable(f"Bill #{plink.bill_id} not found in company #{company_id}.")

    vtype = (await db.execute(
        select(MstVoucherType).where(
            MstVoucherType.company_id == company_id,
            MstVoucherType.name == "Receipt"
        ).with_for_update().execution_options(populate_existing=True)
    )).scalars().first()
    if not vtype:
        raise _WebhookNotPostable(f"No 'Receipt' voucher type in company #{company_id}.")

    vnum = f"{vtype.prefix or ''}{vtype.next_number}"
    vtype.next_number += 1

    voucher = TrnVoucher(
        company_id=company_id,
        voucher_type_id=vtype.voucher_type_id,
        voucher_number=vnum,
        voucher_date=get_ist_now().date(),
        reference_number=pay_id,
        narration=f"Auto Receipt posted via Razorpay webhook {pay_id}",
        total_amount=amount,
        status="confirmed",
        party_ledger_id=bill.party_ledger_id,
        is_optional=False,
        created_by=plink.created_by
    )
    db.add(voucher)
    await db.flush()

    debit = TrnAccounting(
        voucher_id=voucher.voucher_id,
        ledger_id=settlement_ledger.ledger_id,
        debit_amount=amount,
        credit_amount=Decimal("0.00"),
        entry_narration="Payment received via gateway"
    )
    credit = TrnAccounting(
        voucher_id=voucher.voucher_id,
        ledger_id=bill.party_ledger_id,
        debit_amount=Decimal("0.00"),
        credit_amount=amount,
        entry_narration="Settlement of bill"
    )
    db.add_all([debit, credit])
    await db.flush()

    db.add(BillAllocation(
        voucher_entry_id=credit.entry_id,
        bill_id=bill.bill_id,
        allocation_type="Against Ref",
        amount=amount
    ))
    db.add(GatewayTransaction(
        company_id=company_id,
        payment_link_id=plink.payment_link_id,
        bill_id=bill.bill_id,
        gateway_config_id=config.gateway_config_id,
        gateway_payment_id=pay_id,
        gateway_order_id=payment.get("order_id"),
        amount=amount,
        status="Captured",
        method=payment.get("method"),
        voucher_id=voucher.voucher_id,
        raw_payload=payment
    ))
    plink.status = "Paid"

    # Queue for the Desktop Sync Agent. No inline Tally push: Razorpay times out webhooks after a few seconds.
    db.add(SyncQueue(company_id=company_id, record_type="Voucher", record_id=voucher.voucher_id, action="Create"))
    await db.flush()

    logger.info(f"Razorpay payment {pay_id} posted as Receipt {vnum} (voucher #{voucher.voucher_id}) for company #{company_id}")
    return {"status": "processed", "bill_id": bill.bill_id}
