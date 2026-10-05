"""Net sales figures shared by the target, city and collections reports."""
from collections import defaultdict
from datetime import date
from typing import Dict, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tally_core import MstLedger, MstVoucherType, TrnAccounting, TrnVoucher
from app.services.receivables import group_ids_under, live_voucher


async def net_sales_by_customer(
    db: AsyncSession, company_id: int, start: date, end: date
) -> Tuple[Dict[int, float], Dict[int, int], float]:
    """Net sales before GST per customer between two dates (inclusive).

    Each voucher's net sales (credits minus debits on ledgers under Sales Accounts, so credit notes count
    negative) goes to the debtor ledger on that voucher. Returns (sales by ledger, sales invoices by ledger,
    sales with no debtor on the voucher, e.g. cash sales)."""
    sales_groups = await group_ids_under(db, company_id, "Sales Accounts")
    debtor_groups = await group_ids_under(db, company_id, "Sundry Debtors")
    if not sales_groups:
        return {}, {}, 0.0
    in_range = (TrnVoucher.company_id == company_id, live_voucher(),
                TrnVoucher.voucher_date >= start, TrnVoucher.voucher_date <= end)

    net_rows = await db.execute(
        select(TrnVoucher.voucher_id, func.sum(TrnAccounting.credit_amount - TrnAccounting.debit_amount))
        .join(TrnAccounting, TrnAccounting.voucher_id == TrnVoucher.voucher_id)
        .join(MstLedger, MstLedger.ledger_id == TrnAccounting.ledger_id)
        .where(*in_range, MstLedger.group_id.in_(sales_groups))
        .group_by(TrnVoucher.voucher_id)
    )
    net_by_voucher = {vid: float(amount or 0) for vid, amount in net_rows.all()}
    if not net_by_voucher:
        return {}, {}, 0.0

    party_by_voucher: Dict[int, int] = {}
    if debtor_groups:
        party_rows = await db.execute(
            select(TrnVoucher.voucher_id, func.min(TrnAccounting.ledger_id))
            .join(TrnAccounting, TrnAccounting.voucher_id == TrnVoucher.voucher_id)
            .join(MstLedger, MstLedger.ledger_id == TrnAccounting.ledger_id)
            .where(*in_range, MstLedger.group_id.in_(debtor_groups))
            .group_by(TrnVoucher.voucher_id)
        )
        party_by_voucher = dict(party_rows.all())

    type_rows = await db.execute(
        select(TrnVoucher.voucher_id, MstVoucherType.name, MstVoucherType.parent_type)
        .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .where(TrnVoucher.voucher_id.in_(list(net_by_voucher)))
    )
    is_invoice = {vid: "Sales" in (name, parent) for vid, name, parent in type_rows.all()}

    sales: Dict[int, float] = defaultdict(float)
    invoices: Dict[int, int] = defaultdict(int)
    unattributed = 0.0
    for vid, amount in net_by_voucher.items():
        party = party_by_voucher.get(vid)
        if party is None:
            unattributed += amount
            continue
        sales[party] += amount
        if is_invoice.get(vid):
            invoices[party] += 1
    return dict(sales), dict(invoices), round(unattributed, 2)
