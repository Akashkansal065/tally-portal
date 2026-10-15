"""
invoices.py – GST-compliant invoice generation and sequential numbering.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import get_ist_now
from app.models.billing import (
    AccountBillingProfile, BillingInvoice, BillingInvoiceCounter, BillingOrder,
)

logger = logging.getLogger("app.services.billing.invoices")

SAC_CODE = "998313"  # Information technology software services


# The GSTIN earlier versions shipped as a default. It was never a real registration.
_PLACEHOLDER_GSTINS = {"07AAAAA0000A1Z5"}


def seller_state_code() -> Optional[str]:
    """The seller's GST state: set explicitly, else the first two digits of the GSTIN."""
    if settings.BILLING_SELLER_STATE_CODE:
        return settings.BILLING_SELLER_STATE_CODE
    gstin = (settings.BILLING_SELLER_GSTIN or "").strip()
    return gstin[:2] if len(gstin) == 15 and gstin[:2].isdigit() else None


def seller_configured() -> bool:
    """True once a tax invoice can be issued: a legal name and a real 15-character GSTIN are set."""
    gstin = (settings.BILLING_SELLER_GSTIN or "").strip().upper()
    return bool(
        (settings.BILLING_SELLER_NAME or "").strip()
        and len(gstin) == 15 and gstin[:2].isdigit()
        and gstin not in _PLACEHOLDER_GSTINS
    )


# CGST Rule 46(b): a tax invoice's serial number has at most 16 characters
MAX_INVOICE_NUMBER_LENGTH = 16
# Room the prefix leaves for "/2627/00001"
_NUMBER_TAIL_LENGTH = len("/2627/00001")


def invoice_prefixes_fit() -> bool:
    """True when both number series stay within the legal length for the first 99,999 documents of a year."""
    return all(len(prefix or "") + _NUMBER_TAIL_LENGTH <= MAX_INVOICE_NUMBER_LENGTH
               for prefix in (settings.BILLING_INVOICE_PREFIX, settings.BILLING_CREDIT_NOTE_PREFIX))


def require_seller_configured() -> None:
    if not seller_configured():
        raise ValueError(
            "Billing is not set up: the seller's legal name and GSTIN (BILLING_SELLER_NAME, "
            "BILLING_SELLER_GSTIN) must be configured before anything can be sold."
        )
    if not invoice_prefixes_fit():
        raise ValueError(
            f"BILLING_INVOICE_PREFIX and BILLING_CREDIT_NOTE_PREFIX may be at most "
            f"{MAX_INVOICE_NUMBER_LENGTH - _NUMBER_TAIL_LENGTH} characters: a GST invoice number is limited to "
            f"{MAX_INVOICE_NUMBER_LENGTH} characters."
        )


def get_seller_snapshot() -> dict:
    """Dynamic seller snapshot derived from app configuration."""
    return {
        "legal_name": settings.BILLING_SELLER_NAME,
        "trade_name": settings.BILLING_SELLER_TRADE_NAME,
        "gstin": settings.BILLING_SELLER_GSTIN,
        "state_code": seller_state_code(),
        "state_name": settings.BILLING_SELLER_STATE_NAME,
        "address": settings.BILLING_SELLER_ADDRESS,
        "email": settings.BILLING_SELLER_EMAIL,
        "phone": settings.BILLING_SELLER_PHONE,
    }




def get_current_fy(dt: Optional[datetime] = None) -> str:
    """Return Indian Financial Year string, e.g. '2026-27'. The year turns over at midnight IST on 1 April."""
    now = dt or get_ist_now()
    start = now.year if now.month >= 4 else now.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


async def get_next_invoice_number(
    db: AsyncSession,
    kind: str = "invoice",
) -> str:
    """
    Generate sequential invoice number within the current FY using a row-level lock.
    Format: MT/2627/00001 (credit notes MTCN/2627/00001), at most 16 characters as GST requires.
    """
    fy = get_current_fy()

    # Query counter with row-lock
    stmt = (
        select(BillingInvoiceCounter)
        .where(BillingInvoiceCounter.fy == fy, BillingInvoiceCounter.kind == kind)
        .with_for_update()
    )
    counter = (await db.execute(stmt)).scalars().first()

    if not counter:
        counter = BillingInvoiceCounter(fy=fy, kind=kind, last_number=0)
        db.add(counter)
        await db.flush()

    counter.last_number += 1
    num = counter.last_number
    await db.flush()

    prefix = settings.BILLING_INVOICE_PREFIX if kind == "invoice" else settings.BILLING_CREDIT_NOTE_PREFIX
    start, end = fy.split("-")
    number = f"{prefix}/{start[-2:]}{end}/{num:05d}"
    if len(number) > MAX_INVOICE_NUMBER_LENGTH:
        raise ValueError(f"Invoice number {number!r} is longer than the {MAX_INVOICE_NUMBER_LENGTH} characters GST "
                         f"allows. Shorten BILLING_INVOICE_PREFIX / BILLING_CREDIT_NOTE_PREFIX.")
    return number


def _term_label(quote_data: dict) -> str:
    count = quote_data.get("interval_count") or quote_data.get("years") or 1
    unit = "Month" if quote_data.get("interval") == "month" else "Year"
    return f"{count} {unit}{'s' if count != 1 else ''}"


async def issue_invoice_for_order(
    db: AsyncSession,
    order: BillingOrder,
    kind: str = "invoice",
) -> BillingInvoice:
    """
    Idempotently generate and persist a GST invoice or credit note for a paid order.
    """
    # 1. Check if invoice already issued
    existing = (await db.execute(
        select(BillingInvoice).where(
            BillingInvoice.order_id == order.id,
            BillingInvoice.kind == kind,
        )
    )).scalars().first()

    if existing:
        return existing

    # 2. Sequential number
    invoice_number = await get_next_invoice_number(db, kind=kind)

    # 3. Buyer: as frozen on the order when it was priced, so the invoice shows the party and the state the
    # tax was worked out for. Orders from before that was recorded fall back to the saved profile.
    buyer_snapshot: dict = {}
    if order.buyer_snapshot:
        try:
            buyer_snapshot = json.loads(order.buyer_snapshot) or {}
        except Exception:
            buyer_snapshot = {}
    if not buyer_snapshot:
        buyer: Optional[AccountBillingProfile] = (await db.execute(
            select(AccountBillingProfile).where(AccountBillingProfile.account_id == order.account_id)
        )).scalars().first()
        if buyer:
            buyer_snapshot = {
                "legal_name": buyer.legal_name,
                "gstin": buyer.gstin,
                "address": buyer.address,
                "state_code": buyer.state_code,
                "email": buyer.email,
                "phone": buyer.phone,
            }

    quote_data: dict = {}
    if order.quote:
        try:
            quote_data = json.loads(order.quote)
        except Exception:
            quote_data = {}

    place_of_supply = quote_data.get("buyer_state_code") or buyer_snapshot.get("state_code") or seller_state_code()

    # 4. Lines
    lines = []
    if quote_data:
        if quote_data.get("base_plan_paise"):
            lines.append({
                "description": f"MyTally {quote_data.get('plan_name', 'Cloud')} Plan ({_term_label(quote_data)})",
                "sac": SAC_CODE,
                "amount_paise": quote_data.get("base_plan_paise"),
            })
        if quote_data.get("extra_users_paise"):
            lines.append({
                "description": f"Additional User Licenses ({quote_data.get('extra_users')})",
                "sac": SAC_CODE,
                "amount_paise": quote_data.get("extra_users_paise"),
            })
        if quote_data.get("extra_companies_paise"):
            lines.append({
                "description": f"Additional Company Slots ({quote_data.get('extra_companies')})",
                "sac": SAC_CODE,
                "amount_paise": quote_data.get("extra_companies_paise"),
            })
        if quote_data.get("discount_paise"):
            coupon_lbl = quote_data.get("coupon_code") or "Coupon"
            lines.append({
                "description": f"Promotional Discount ({coupon_lbl})",
                "sac": SAC_CODE,
                "amount_paise": -quote_data.get("discount_paise"),
            })
        if quote_data.get("proration_credit_paise"):
            lines.append({
                "description": "Proration Credit for Plan Upgrade",
                "sac": SAC_CODE,
                "amount_paise": -quote_data.get("proration_credit_paise"),
            })

    if not lines:
        lines.append({
            "description": f"Subscription {order.order_ref}",
            "sac": SAC_CODE,
            "amount_paise": order.taxable_paise,
        })

    invoice = BillingInvoice(
        invoice_number=invoice_number,
        kind=kind,
        order_id=order.id,
        buyer_snapshot=json.dumps(buyer_snapshot),
        seller_snapshot=json.dumps(get_seller_snapshot()),
        place_of_supply=place_of_supply,
        sac=SAC_CODE,
        lines=json.dumps(lines),
        taxable_paise=order.taxable_paise,
        cgst_paise=order.cgst_paise,
        sgst_paise=order.sgst_paise,
        igst_paise=order.igst_paise,
        total_paise=order.total_paise,
    )
    db.add(invoice)
    await db.flush()

    logger.info(f"Issued {kind} #{invoice.invoice_number} for order {order.order_ref} (₹{round(order.total_paise / 100, 2)})")
    return invoice
