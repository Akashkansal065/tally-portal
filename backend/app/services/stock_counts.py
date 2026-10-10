"""
Physical Stock counts and the stock figure of the items they cover.

A count says "on this date there were N". Everything dated up to the count is absorbed by it; only movements
after the latest count change the stock from there. The app keeps one running stock figure per item and each
count line as the movement that brings the books to the counted quantity, so whenever something changes for
an item that has counts (a count added, altered, cancelled or deleted, or any voucher entered or removed
around one), those movements are worked out again in date order and the item's stock follows.

A movement on the same date as a count is taken to be before it: the count is that day's closing figure.
"""
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tally_core import MstStockItem, MstVoucherType, TrnInventory, TrnVoucher
from app.services.voucher_kinds import is_physical_stock


def _signed(line: TrnInventory) -> Decimal:
    quantity = Decimal(str(line.quantity or 0))
    return quantity if line.is_inward else -quantity


async def items_with_counts(db: AsyncSession, company_id: int) -> set:
    """Every item of the company that has a line on a Physical Stock voucher."""
    rows = (await db.execute(
        select(TrnInventory.stock_item_id, MstVoucherType)
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnInventory.voucher_id)
        .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .where(TrnVoucher.company_id == company_id)
    )).all()
    return {item_id for item_id, vtype in rows if is_physical_stock(vtype)}


async def rebalance_stock_counts(db: AsyncSession, company_id: int, item_ids: Iterable[int]) -> None:
    """Re-derives the count adjustments and the stock figure of these items. Flushes, does not commit."""
    for item_id in {i for i in item_ids if i}:
        rows = (await db.execute(
            select(TrnInventory, TrnVoucher.voucher_date, TrnVoucher.voucher_id, MstVoucherType)
            .join(TrnVoucher, TrnVoucher.voucher_id == TrnInventory.voucher_id)
            .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
            .where(TrnVoucher.company_id == company_id, TrnVoucher.status == "confirmed", TrnInventory.stock_item_id == item_id)
            .execution_options(populate_existing=True)
        )).all()
        counts = sorted(((day, voucher_id, line) for line, day, voucher_id, vtype in rows
                         if is_physical_stock(vtype) and line.actual_quantity is not None), key=lambda c: (c[0], c[1]))
        if not counts:
            continue
        moves = [(day, _signed(line)) for line, day, _, vtype in rows if not is_physical_stock(vtype)]
        item = (await db.execute(select(MstStockItem).where(MstStockItem.stock_item_id == item_id)
                                 .execution_options(populate_existing=True))).scalars().first()
        if item is None:
            continue

        # Stock as the books alone would have it, before any movement: the current figure with every count
        # adjustment and every movement taken back out
        start = (Decimal(str(item.closing_qty or 0)) - sum((_signed(line) for _, _, line in counts), Decimal("0"))
                 - sum((qty for _, qty in moves), Decimal("0")))

        level, last_day = None, None
        for day, _, line in counts:
            if level is None:
                book = start + sum((qty for d, qty in moves if d <= day), Decimal("0"))
            else:
                book = level + sum((qty for d, qty in moves if last_day < d <= day), Decimal("0"))
            counted = Decimal(str(line.actual_quantity))
            difference = counted - book
            line.quantity = abs(difference)
            line.billed_qty = abs(difference)
            line.is_inward = line.is_deemed_positive = difference >= 0
            level, last_day = counted, day
        item.closing_qty = level + sum((qty for d, qty in moves if d > last_day), Decimal("0"))
    await db.flush()


async def rebalance_counted_items(db: AsyncSession, company_id: int, item_ids: Iterable[int]) -> None:
    """rebalance_stock_counts() for those of the given items that have a count at all."""
    wanted = {i for i in item_ids if i}
    if wanted:
        await rebalance_stock_counts(db, company_id, wanted & await items_with_counts(db, company_id))
