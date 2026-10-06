"""Customer greetings (Phase 5): who to greet. The cards themselves are drawn in the browser with the company's
branding and shared by WhatsApp / the share sheet, so nothing here sends anything."""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.datetime_utils import get_ist_date
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.models.tally_core import MstLedger, MstVoucherType, TrnAccounting, TrnVoucher
from app.services.receivables import group_ids_under, live_voucher, sales_voucher_type
from app.services.reminders import contacts_for

router = APIRouter(prefix="/greetings", tags=["Customer greetings"])


@router.get("/customers")
async def customers(
    days: int = Query(60, ge=0, le=3650, description="No sale in this many days; 0 = every customer"),
    search: Optional[str] = Query(None, max_length=100),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Customers (Sundry Debtors and sub-groups) with their last sale, inactive ones first."""
    cid = user.company_id
    groups = await group_ids_under(db, cid, "Sundry Debtors")
    if not groups:
        return []
    stmt = select(MstLedger.ledger_id, MstLedger.name).where(MstLedger.company_id == cid, MstLedger.group_id.in_(groups))
    if search:
        stmt = stmt.where(MstLedger.name.ilike(f"%{search.strip()}%"))
    ledgers = (await db.execute(stmt)).all()
    if not ledgers:
        return []
    ids = [l.ledger_id for l in ledgers]
    last_sale = dict((await db.execute(
        select(TrnAccounting.ledger_id, func.max(TrnVoucher.voucher_date))
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .where(TrnVoucher.company_id == cid, TrnAccounting.ledger_id.in_(ids), live_voucher(), sales_voucher_type())
        .group_by(TrnAccounting.ledger_id))).all())
    contacts = await contacts_for(db, cid, ids)
    today = get_ist_date()
    cutoff = today - timedelta(days=days)
    out = []
    for l in ledgers:
        last = last_sale.get(l.ledger_id)
        if days and last and last > cutoff:
            continue
        out.append({
            "ledger_id": l.ledger_id, "name": l.name, "last_sale": last.isoformat() if last else None,
            "days_since": (today - last).days if last else None, "whatsapp": contacts[l.ledger_id].whatsapp,
        })
    # Longest without a sale first (never bought last), then by name
    out.sort(key=lambda c: (c["days_since"] is None, -(c["days_since"] or 0), c["name"].lower()))
    return out
