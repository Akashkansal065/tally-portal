"""WS-10 family 3: stock item fields the agent now asks Tally for (HSN/GST details, aliases) are read and stored."""
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.models.tally_core as T
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import run

ITEM = """<STOCKITEM NAME="Sample Widget"><GUID>si-guid-1</GUID><MASTERID> 91</MASTERID><ALTERID> {alter}</ALTERID>
<PARENT>Primary</PARENT><BASEUNITS>Nos</BASEUNITS>{extra}</STOCKITEM>"""

EXTRA = """<INFGSTHSNCODE>8481</INFGSTHSNCODE><INFGSTIGSTRATE>18</INFGSTIGSTRATE>
<HSNDETAILS.LIST><APPLICABLEFROM>20250401</APPLICABLEFROM><HSNCODE>8481</HSNCODE><HSNDESCRIPTION>Taps and valves</HSNDESCRIPTION>
<TAXABILITY>Taxable</TAXABILITY></HSNDETAILS.LIST>
<LANGUAGENAME.LIST><NAME.LIST><NAME>Sample Widget</NAME><NAME>SW-100</NAME><NAME>Widget Mk2</NAME></NAME.LIST></LANGUAGENAME.LIST>"""


@pytest.fixture
def company(harness):
    c = harness.company("Alpha")
    harness.user(c, harness.role("Admin"), "owner")
    return c


def load(harness, company, extra, alter=1):
    xml = f"<ENVELOPE><BODY><DATA><COLLECTION>{ITEM.format(extra=extra, alter=alter)}</COLLECTION></DATA></BODY></ENVELOPE>"

    async def go():
        async with harness.Session() as db:
            res = await import_tally_xml(xml, db, 1, target_company_id=company.company_id)
            await db.commit()
            return res
    return run(go())


def item(harness):
    return harness.query(select(T.MstStockItem).where(T.MstStockItem.name == "Sample Widget"))[0][0]


def test_hsn_gst_and_aliases_are_stored(harness, company):
    load(harness, company, EXTRA)
    i = item(harness)
    assert (i.hsn_code, i.gst_rate_percent) == ("8481", Decimal("18.00"))
    (h,) = [r[0] for r in harness.query(select(T.MstHsnDetail).where(T.MstHsnDetail.stock_item_id == i.stock_item_id))]
    assert (h.hsn_code, h.hsn_description, h.taxability) == ("8481", "Taps and valves", "Taxable")
    aliases = sorted(r[0] for r in harness.query(select(T.StockItemAlias.alias)))
    assert aliases == ["SW-100", "Widget Mk2"]


def test_a_second_export_does_not_duplicate_children(harness, company):
    load(harness, company, EXTRA, alter=1)
    load(harness, company, EXTRA, alter=2)
    assert len(harness.query(select(T.MstHsnDetail))) == 1
    assert len(harness.query(select(T.StockItemAlias))) == 2


def test_an_item_without_the_new_tags_imports_unchanged(harness, company):
    load(harness, company, "")
    i = item(harness)
    assert i.hsn_code is None and harness.query(select(T.MstHsnDetail)) == []
    assert harness.query(select(T.StockItemAlias)) == []


def test_malformed_rate_does_not_fail_the_import(harness, company):
    res = load(harness, company, "<INFGSTIGSTRATE>eighteen</INFGSTIGSTRATE><HSNDETAILS.LIST><HSNCODE>8481</HSNCODE></HSNDETAILS.LIST>")
    assert res.get("status") != "error"
    assert item(harness).name == "Sample Widget"
