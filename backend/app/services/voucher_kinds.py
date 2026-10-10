"""
What a voucher type means for stock and for the books, by the Tally voucher type it is based on.

Two independent questions, which only coincide for plain Sales and Purchase:

  * Does stock leave or arrive?           (a Debit Note sends goods back to the supplier: stock leaves)
  * Is it the sales or the purchase side? (that same Debit Note reverses a purchase: purchase ledger)

                    stock      party      ledger
  Sales             leaves     debited    sales
  Delivery Note     leaves     debited    sales
  Credit Note       arrives    credited   sales      (goods returned by a customer)
  Purchase          arrives    credited   purchase
  Receipt Note      arrives    credited   purchase
  Debit Note        leaves     debited    purchase   (goods returned to a supplier)

Verified against TallyPrime (audit log, Step 7).
"""
STOCK_LEAVES = {"sales", "delivery note", "debit note", "sales order", "rejections out", "material out"}
SALES_SIDE = {"sales", "delivery note", "credit note", "sales order", "rejections in"}


def base_type(voucher_type) -> str:
    """The Tally voucher type this one is based on (its parent, or itself for a built-in type)."""
    if voucher_type is None:
        return ""
    return (getattr(voucher_type, "parent_type", None) or getattr(voucher_type, "name", None) or "").strip().lower()


def stock_leaves(voucher_type) -> bool:
    """True when the voucher sends stock out; the party is then the one debited."""
    return base_type(voucher_type) in STOCK_LEAVES or (getattr(voucher_type, "name", "") or "").strip().lower() in STOCK_LEAVES


def is_sales_side(voucher_type) -> bool:
    """True when the item lines post to a sales ledger, False for a purchase ledger."""
    return base_type(voucher_type) in SALES_SIDE or (getattr(voucher_type, "name", "") or "").strip().lower() in SALES_SIDE


def is_stock_journal(voucher_type) -> bool:
    """A voucher that only moves stock: items consumed (source) and items produced (destination), no ledgers."""
    return "stock journal" in (base_type(voucher_type), (getattr(voucher_type, "name", "") or "").strip().lower())


def is_physical_stock(voucher_type) -> bool:
    """
    A stock count: each line says how much of an item is actually there. In the app such a line is kept as the
    movement that brings the books to the count (quantity and direction), with the counted figure itself in
    actual_quantity, so everything that reverses a voucher's stock effect works on it unchanged.
    """
    return "physical stock" in (base_type(voucher_type), (getattr(voucher_type, "name", "") or "").strip().lower())


def is_attendance(voucher_type) -> bool:
    """Days (or other units) of an attendance type per employee; no ledgers, no items."""
    return "attendance" in (base_type(voucher_type), (getattr(voucher_type, "name", "") or "").strip().lower())


def is_payroll(voucher_type) -> bool:
    """Pay heads per employee, posted to the pay head ledgers against a payable ledger."""
    return "payroll" in (base_type(voucher_type), (getattr(voucher_type, "name", "") or "").strip().lower())
