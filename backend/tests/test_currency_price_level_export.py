"""WS-10 family 4: currencies (already parsed) and price levels (parsed now) from a Tally-shaped export."""
import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import run

XML = """<ENVELOPE><BODY><DATA><COLLECTION>
<CURRENCY NAME="$"><ORIGINALNAME>$</ORIGINALNAME><EXPANDEDNAME>US Dollar</EXPANDEDNAME><ISOCURRENCYCODE>USD</ISOCURRENCYCODE>
<DECIMALPLACES>2</DECIMALPLACES><INMILLIONS>No</INMILLIONS><ISSUFFIX>No</ISSUFFIX><HASSPACE>Yes</HASSPACE>
<DECIMALSYMBOL>cents</DECIMALSYMBOL><DECIMALPLACESFORPRINTING>2</DECIMALPLACESFORPRINTING>
<MAILINGNAME.LIST><MAILINGNAME>US Dollar</MAILINGNAME></MAILINGNAME.LIST></CURRENCY>
<PRICELEVEL NAME="Wholesale"><ALTERID> 12</ALTERID></PRICELEVEL>
<PRICELEVEL NAME="Retail"><ALTERID> 13</ALTERID></PRICELEVEL>
<PRICELEVEL><ALTERID> 14</ALTERID></PRICELEVEL>
</COLLECTION></DATA></BODY></ENVELOPE>"""


@pytest.fixture
def company(harness):
    c = harness.company("Alpha")
    harness.user(c, harness.role("Admin"), "owner")
    return c


def load(harness, company, xml=XML):
    async def go():
        async with harness.Session() as db:
            res = await import_tally_xml(xml, db, 1, target_company_id=company.company_id)
            await db.commit()
            return res
    return run(go())


def test_currency_and_price_levels_are_stored(harness, company):
    res = load(harness, company)
    assert res["imported_currencies"] == 1
    (c,) = [r[0] for r in harness.query(select(P.Currency).where(P.Currency.company_id == company.company_id,
                                                                  P.Currency.symbol == "$"))]
    assert (c.code, c.symbol, c.formal_name, c.decimal_places) == ("USD", "$", "US Dollar", 2)
    levels = {n: a for n, a in harness.query(select(T.MstPriceLevel.name, T.MstPriceLevel.tally_alter_id))}
    assert levels == {"Wholesale": 12, "Retail": 13}                      # the nameless one is ignored


def test_repeating_the_export_makes_no_duplicates(harness, company):
    load(harness, company)
    count = len(harness.query(select(P.Currency).where(P.Currency.company_id == company.company_id)))
    load(harness, company)
    assert len(harness.query(select(T.MstPriceLevel))) == 2
    assert len(harness.query(select(P.Currency).where(P.Currency.company_id == company.company_id))) == count


def test_a_vouchers_own_pricelevel_text_is_not_a_price_level(harness, company):
    xml = ("<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER VCHTYPE='Sales'><DATE>20260301</DATE><GUID>g-pl</GUID>"
           "<PRICELEVEL>Retail</PRICELEVEL><VOUCHERNUMBER>1</VOUCHERNUMBER></VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>")
    load(harness, company, xml)
    assert harness.query(select(T.MstPriceLevel)) == []


def test_an_export_without_either_imports_unchanged(harness, company):
    res = load(harness, company, "<ENVELOPE><BODY><DATA><COLLECTION></COLLECTION></DATA></BODY></ENVELOPE>")
    assert res.get("status") != "error" and harness.query(select(T.MstPriceLevel)) == []
