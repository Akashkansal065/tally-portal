"""WS-10 family 2: ledger fields the agent now asks Tally for are read and stored."""
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.models.tally_core as T
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import run

LEDGER = """<LEDGER NAME="Sample Customer"><GUID>led-guid-1</GUID><MASTERID> 41</MASTERID><ALTERID> {alter}</ALTERID>
<PARENT>Sundry Debtors</PARENT><OPENINGBALANCE>-1500.00</OPENINGBALANCE>{extra}</LEDGER>"""

EXTRA = """<CREDITLIMIT>50000.00</CREDITLIMIT><BILLCREDITPERIOD>30 Days</BILLCREDITPERIOD>
<LEDGERCONTACT>Asha Rao</LEDGERCONTACT><LEDGERMOBILE>9876500000</LEDGERMOBILE><EMAIL>accounts@sample.example</EMAIL>
<EMAILCC>cc@sample.example</EMAILCC><WEBSITE>sample.example</WEBSITE><LEDGERFAX>0801234567</LEDGERFAX>
<COUNTRYNAME>India</COUNTRYNAME><TAXCLASSIFICATIONNAME>GST 18%</TAXCLASSIFICATIONNAME>
<MSMEREGISTRATIONDETAILS.LIST><ENTERPRISETYPE>Small</ENTERPRISETYPE><UDYAMREGNO>UDYAM-KA-01-0000001</UDYAMREGNO></MSMEREGISTRATIONDETAILS.LIST>
<LOWERDEDUCTION.LIST><SECTIONNUMBER>194C</SECTIONNUMBER><CERTIFICATENO>CERT-77</CERTIFICATENO><RATEOFDEDUCTION>1</RATEOFDEDUCTION></LOWERDEDUCTION.LIST>
<LANGUAGENAME.LIST><NAME.LIST><NAME>Sample Customer</NAME><NAME>SC Traders</NAME></NAME.LIST></LANGUAGENAME.LIST>"""


@pytest.fixture
def company(harness):
    c = harness.company("Alpha")
    harness.user(c, harness.role("Admin"), "owner")
    harness.add(T.MstGroup(company_id=c.company_id, name="Sundry Debtors", nature="Asset"))
    return c


def load(harness, company, extra, alter=1):
    xml = f"<ENVELOPE><BODY><DATA><COLLECTION>{LEDGER.format(extra=extra, alter=alter)}</COLLECTION></DATA></BODY></ENVELOPE>"

    async def go():
        async with harness.Session() as db:
            res = await import_tally_xml(xml, db, 1, target_company_id=company.company_id)
            await db.commit()
            return res
    return run(go())


def ledger(harness):
    return harness.query(select(T.MstLedger).where(T.MstLedger.name == "Sample Customer"))[0][0]


def test_credit_contact_and_tax_fields_are_stored(harness, company):
    load(harness, company, EXTRA)
    l = ledger(harness)
    assert (l.credit_limit, l.credit_period_days) == (Decimal("50000.00"), 30)
    assert (l.contact_person, l.mobile, l.email, l.email_cc, l.website, l.fax) == \
           ("Asha Rao", "9876500000", "accounts@sample.example", "cc@sample.example", "sample.example", "0801234567")
    assert (l.country, l.tax_classification_name, l.alias_name) == ("India", "GST 18%", "SC Traders")
    assert (l.opening_balance, l.opening_balance_type) == (Decimal("1500.00"), "Dr")


def test_msme_and_lower_deduction_children_are_stored_once(harness, company):
    load(harness, company, EXTRA, alter=1)
    load(harness, company, EXTRA, alter=2)               # altered and exported again: no duplicate children
    (m,) = [r[0] for r in harness.query(select(T.MstLedgerMsmeDetail))]
    assert (m.enterprise_type, m.udyam_reg_no) == ("Small", "UDYAM-KA-01-0000001")
    (d,) = [r[0] for r in harness.query(select(T.MstLedgerTdsLowerDeduction))]
    assert (d.section_number, d.certificate_no, d.rate_of_deduction) == ("194C", "CERT-77", Decimal("1.00"))


def test_a_ledger_without_the_new_tags_imports_unchanged(harness, company):
    load(harness, company, "")
    l = ledger(harness)
    assert (l.credit_limit, l.credit_period_days, l.contact_person, l.email) == (None, None, None, None)
    assert harness.query(select(T.MstLedgerMsmeDetail)) == []


def test_malformed_numbers_do_not_fail_the_import(harness, company):
    res = load(harness, company, "<CREDITLIMIT>lots</CREDITLIMIT><BILLCREDITPERIOD>soon</BILLCREDITPERIOD>")
    assert res.get("status") != "error"
    l = ledger(harness)
    assert l.credit_limit is None and l.credit_period_days is None
