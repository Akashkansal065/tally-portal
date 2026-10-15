"""
credits.py – Pack credits ledger management (e-invoicing, WhatsApp).

The balance of credits for any account is SUM(delta) from billing_credit_ledger.
All operations are atomic and append-only.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingCreditLedger

logger = logging.getLogger("app.services.billing.credits")


async def get_credit_balance(
    db: AsyncSession,
    account_id: int,
    credit_type: str,
) -> int:
    """Return the current non-negative credit balance for the given account and type."""
    stmt = select(func.coalesce(func.sum(BillingCreditLedger.delta), 0)).where(
        BillingCreditLedger.account_id == account_id,
        BillingCreditLedger.credit_type == credit_type,
    )
    result = await db.execute(stmt)
    balance = result.scalar() or 0
    return max(0, int(balance))


async def get_all_credit_balances(
    db: AsyncSession,
    account_id: int,
) -> Dict[str, int]:
    """Return credit balances for all active credit types (e.g. einvoice, whatsapp)."""
    stmt = (
        select(
            BillingCreditLedger.credit_type,
            func.coalesce(func.sum(BillingCreditLedger.delta), 0).label("balance"),
        )
        .where(BillingCreditLedger.account_id == account_id)
        .group_by(BillingCreditLedger.credit_type)
    )
    rows = (await db.execute(stmt)).all()
    balances: Dict[str, int] = {"einvoice": 0, "whatsapp": 0}
    for row in rows:
        balances[row.credit_type] = max(0, int(row.balance))
    return balances


async def grant_credits(
    db: AsyncSession,
    *,
    account_id: int,
    credit_type: str,
    qty: int,
    reason: str,
    reference: str,
) -> BillingCreditLedger:
    """
    Credit positive quantity to the account's ledger.
    Duplicate reference for the same (account_id, credit_type) is ignored / idempotent.
    """
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}")

    # Check for existing reference
    existing = (await db.execute(
        select(BillingCreditLedger).where(
            BillingCreditLedger.account_id == account_id,
            BillingCreditLedger.credit_type == credit_type,
            BillingCreditLedger.reference == reference,
        )
    )).scalars().first()

    if existing:
        logger.info(f"Credit entry with ref '{reference}' already exists for account {account_id}.")
        return existing

    entry = BillingCreditLedger(
        account_id=account_id,
        credit_type=credit_type,
        delta=qty,
        reason=reason,
        reference=reference,
    )
    db.add(entry)
    await db.flush()
    logger.info(f"Granted {qty} {credit_type} credits to account {account_id} (ref={reference})")
    return entry


async def consume_credits(
    db: AsyncSession,
    *,
    account_id: int,
    credit_type: str,
    qty: int,
    reason: str,
    reference: str,
) -> Tuple[bool, int]:
    """
    Attempt to consume credits. Returns (success, remaining_balance).
    If balance is insufficient, returns (False, current_balance) without deducting.
    """
    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}")

    current = await get_credit_balance(db, account_id, credit_type)
    if current < qty:
        logger.warning(
            f"Account {account_id} attempted to consume {qty} {credit_type} credits with balance {current}."
        )
        return False, current

    entry = BillingCreditLedger(
        account_id=account_id,
        credit_type=credit_type,
        delta=-qty,
        reason=reason,
        reference=reference,
    )
    db.add(entry)
    await db.flush()
    return True, current - qty
