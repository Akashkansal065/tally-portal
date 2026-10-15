"""Table-driven checks for the Tally number and parent-name helpers."""
from decimal import Decimal

import pytest

from app.services.tally_xml_importer import _decimal_or_none, tally_parent_name


@pytest.mark.parametrize("raw,expected", [
    (" 30", Decimal("30")),
    ("-4838.71 Days", Decimal("-4838.71")),
    ("1,250.50", Decimal("1250.50")),
    ("(1,250.50)", Decimal("-1250.50")),
    ("5,000.00/Nos", Decimal("5000.00")),
    ("5,000.00 Nos", Decimal("5000.00")),
    ("12/Kgs", Decimal("12")),
    ("", None), (None, None), ("abc", None), ("()", None), ("/Nos", None),
])
def test_decimal_or_none(raw, expected):
    assert _decimal_or_none(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("&#4; Primary", None), ("\x04 Primary", None), ("\x04Primary", None), (" Primary", None),
    ("primary", None), ("", None), (None, None),
    ("Sundry Debtors", "Sundry Debtors"), ("&#4; Sundry Debtors", "Sundry Debtors"),
])
def test_tally_parent_name(raw, expected):
    assert tally_parent_name(raw) == expected
