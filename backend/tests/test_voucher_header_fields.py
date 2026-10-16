"""WS-10 family 1: voucher header fields the agent now asks Tally for are read and stored; an export without
them (an older agent) leaves what is stored alone."""
from datetime import date

import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import run

HEADER = """<VOUCHER VCHTYPE="Sales"><DATE>20260310</DATE><GUID>g-hdr-1</GUID><MASTERID> 71</MASTERID><ALTERID> {alter}</ALTERID>
<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME><VOUCHERNUMBER>S-17</VOUCHERNUMBER>{extra}
<ALLLEDGERENTRIES.LIST><LEDGERNAME>Party</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-118.00</AMOUNT></ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST><LEDGERNAME>Sales</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>118.00</AMOUNT></ALLLEDGERENTRIES.LIST>
</VOUCHER>"""

FULL = """<ISPOSTDATED>Yes</ISPOSTDATED><ISINVOICE>Yes</ISINVOICE><PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
<EFFECTIVEDATE>20260315</EFFECTIVEDATE><REFERENCE>SUP/2026/445</REFERENCE><REFERENCEDATE>20260309</REFERENCEDATE>
<PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY><BASICBUYERNAME>Sample Traders</BASICBUYERNAME>
<BASICBUYERADDRESS.LIST><BASICBUYERADDRESS>12 Sample Road</BASICBUYERADDRESS><BASICBUYERADDRESS>Bengaluru</BASICBUYERADDRESS></BASICBUYERADDRESS.LIST>
<CONSIGNEEMAILINGNAME>Sample Godown</CONSIGNEEMAILINGNAME>
<CONSIGNEEADDRESS.LIST><CONSIGNEEADDRESS>Plot 4</CONSIGNEEADDRESS></CONSIGNEEADDRESS.LIST>
<BASICORDERREF>PO-991</BASICORDERREF><BASICSHIPDELIVERYNOTE>DN-12</BASICSHIPDELIVERYNOTE>
<IRN>a1b2c3d4e5f6</IRN><IRNACKNO>112010000123456</IRNACKNO><IRNACKDATE>2026-03-10 11:30:00</IRNACKDATE>
<IRNQRCODE>eyJhbGciOi.sample.qr</IRNQRCODE><IRNCANCELLED>No</IRNCANCELLED>
<EWAYBILLDETAILS.LIST><BILLNUMBER>351001234567</BILLNUMBER><VEHICLENUMBER>KA01AB1234</VEHICLENUMBER><TRANSPORTERNAME>Sample Carriers</TRANSPORTERNAME></EWAYBILLDETAILS.LIST>"""


@pytest.fixture
def company(harness):
    c = harness.company("Alpha")
    harness.user(c, harness.role("Admin"), "owner")
    cid = c.company_id
    g = harness.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    harness.add(T.MstLedger(company_id=cid, name="Party", group_id=g.group_id),
                T.MstLedger(company_id=cid, name="Sales", group_id=g.group_id),
                T.MstVoucherType(company_id=cid, name="Sales", parent_type="Sales", numbering_method="Automatic", next_number=1))
    return c


def load(harness, company, extra="", alter=1, force=False):
    xml = f"<ENVELOPE><BODY><DATA><COLLECTION>{HEADER.format(extra=extra, alter=alter)}</COLLECTION></DATA></BODY></ENVELOPE>"

    async def go():
        async with harness.Session() as db:
            res = await import_tally_xml(xml, db, 1, target_company_id=company.company_id, force_overwrite=force)
            await db.commit()
            return res
    return run(go())


def voucher(harness):
    return harness.query(select(T.TrnVoucher))[0][0]


def test_every_header_field_is_stored(harness, company):
    load(harness, company, FULL)
    v = voucher(harness)
    assert (v.is_post_dated, v.is_invoice, v.persisted_view) == (True, True, "Invoice Voucher View")
    assert (v.effective_date, v.reference_number, v.reference_date) == (date(2026, 3, 15), "SUP/2026/445", date(2026, 3, 9))
    assert (v.place_of_supply, v.buyer_name, v.buyer_address) == ("Karnataka", "Sample Traders", "12 Sample Road, Bengaluru")
    assert (v.consignee_name, v.consignee_address) == ("Sample Godown", "Plot 4")
    assert (v.order_reference, v.despatch_doc_no) == ("PO-991", "DN-12")
    assert (v.irn, v.irn_ack_no, v.irn_qr_code, v.irn_cancelled) == ("a1b2c3d4e5f6", "112010000123456", "eyJhbGciOi.sample.qr", False)
    assert v.irn_ack_date is not None
    (eb,) = [r[0] for r in harness.query(select(T.TrnEwayBill))]
    assert (eb.bill_number, eb.vehicle_number, eb.transporter_name) == ("351001234567", "KA01AB1234", "Sample Carriers")


def test_a_header_without_the_new_tags_imports_unchanged(harness, company):
    load(harness, company, "")
    v = voucher(harness)
    assert v.reference_number is None and v.reference_date is None and v.place_of_supply is None
    assert v.irn is None and v.is_post_dated is False and v.effective_date == date(2026, 3, 10)
    assert harness.query(select(T.TrnEwayBill)) == []


def test_an_older_agents_export_does_not_wipe_stored_header_values(harness, company):
    load(harness, company, FULL, alter=1)
    load(harness, company, "", alter=2)                      # altered in Tally, exported without the new tags
    v = voucher(harness)
    assert (v.reference_number, v.is_invoice, v.persisted_view, v.irn, v.place_of_supply) == \
           ("SUP/2026/445", True, "Invoice Voucher View", "a1b2c3d4e5f6", "Karnataka")


def test_malformed_values_do_not_fail_the_import(harness, company):
    res = load(harness, company, "<EFFECTIVEDATE>31-31-31</EFFECTIVEDATE><REFERENCEDATE>soon</REFERENCEDATE>"
                                 "<ISINVOICE>maybe</ISINVOICE><IRNACKDATE>not a date</IRNACKDATE>")
    assert res.get("status") != "error"
    v = voucher(harness)
    assert v.reference_date is None and v.is_invoice in (False, None) and v.irn_ack_date is None

