"""Stock direction and sales/purchase side by voucher type, as TallyPrime stores them (audit log, Step 7)."""
from types import SimpleNamespace

import pytest

from app.services.voucher_kinds import is_sales_side, stock_leaves


@pytest.mark.parametrize("name, leaves, sales", [
    ("Sales", True, True), ("Delivery Note", True, True), ("Credit Note", False, True),
    ("Purchase", False, False), ("Receipt Note", False, False), ("Debit Note", True, False),
    ("Journal", False, False), ("Contra", False, False),
])
def test_built_in_types(name, leaves, sales):
    vt = SimpleNamespace(name=name, parent_type=name)
    assert (stock_leaves(vt), is_sales_side(vt)) == (leaves, sales)


def test_a_custom_type_follows_the_type_it_is_based_on():
    vt = SimpleNamespace(name="Export Return", parent_type="Credit Note")
    assert (stock_leaves(vt), is_sales_side(vt)) == (False, True)
