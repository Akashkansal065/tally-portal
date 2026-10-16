"""WS-4: Tally's own bank reconciliation (BANKERSDATE / BANKMANUALSTATUS) is kept and honoured."""
from datetime import date

import pytest
from sqlalchemy import select

from app.models.tally_core import MstGroup, MstLedger, MstVoucherType, TrnBankAllocation
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import run


def bank_line(extra="", instrument="CH100", amount="1000.00"):
    return ("<BANKALLOCATIONS.LIST><DATE>20260301</DATE><INSTRUMENTDATE>20260301</INSTRUMENTDATE>"
            f"<TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE><INSTRUMENTNUMBER>{instrument}</INSTRUMENTNUMBER>"
            f"<AMOUNT>{amount}</AMOUNT>{extra}</BANKALLOCATIONS.LIST>")


def voucher_xml(*bank_lines, guid="guid-brs", master=501):
    return ('<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER VCHTYPE="Receipt"><DATE>20260301</DATE>'
            f'<GUID>{guid}</GUID><MASTERID> {master}</MASTERID><ALTERID> 3</ALTERID>'
            '<VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME><VOUCHERNUMBER>1</VOUCHERNUMBER>'
            '<ALLLEDGERENTRIES.LIST><LEDGERNAME>HDFC Bank</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>'
            f'<AMOUNT>-1000.00</AMOUNT>{"".join(bank_lines)}</ALLLEDGERENTRIES.LIST>'
            '<ALLLEDGERENTRIES.LIST><LEDGERNAME>Customer A</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>'
            '<AMOUNT>1000.00</AMOUNT></ALLLEDGERENTRIES.LIST>'
            '</VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>')


@pytest.fixture(autouse=True)
def company(harness):
    c = harness.company()
    harness.user(c, harness.role("Admin"), "owner")
    cid = c.company_id
    bank = harness.add(MstGroup(company_id=cid, name="Bank Accounts", nature="Asset"))
    debtors = harness.add(MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    harness.add(MstLedger(company_id=cid, name="HDFC Bank", group_id=bank.group_id),
                MstLedger(company_id=cid, name="Customer A", group_id=debtors.group_id),
                MstVoucherType(company_id=cid, name="Receipt", parent_type="Receipt", numbering_method="Automatic", next_number=1))
    return c


def load(harness, xml):
    cid = harness.scalar(select(MstGroup.company_id))
    async def go():
        async with harness.Session() as db:
            result = await import_tally_xml(xml, db, 1, target_company_id=cid)
            await db.commit()
            return result
    return run(go())


def allocations(harness):
    return [r[0] for r in harness.query(select(TrnBankAllocation).order_by(TrnBankAllocation.allocation_id))]


def test_values_are_stored(harness):
    load(harness, voucher_xml(bank_line("<BANKERSDATE>20260305</BANKERSDATE><BANKMANUALSTATUS>Yes</BANKMANUALSTATUS>")))
    (alloc,) = allocations(harness)
    assert alloc.bankers_date == date(2026, 3, 5)
    assert alloc.bank_manual_status == "Yes"


def test_absent_tags_import_unchanged(harness):
    load(harness, voucher_xml(bank_line()))
    (alloc,) = allocations(harness)
    assert (alloc.bankers_date, alloc.bank_manual_status) == (None, None)
    assert alloc.instrument_number == "CH100"


@pytest.mark.parametrize("bad", ["not-a-date", "99999999", "  ", "2026-13-45"])
def test_malformed_date_does_not_fail_the_import(harness, bad):
    result = load(harness, voucher_xml(bank_line(f"<BANKERSDATE>{bad}</BANKERSDATE>")))
    assert result.get("status") != "error"
    (alloc,) = allocations(harness)
    assert alloc.bankers_date is None and alloc.instrument_number == "CH100"


def test_each_allocation_keeps_its_own_values(harness):
    load(harness, voucher_xml(
        bank_line("<BANKERSDATE>20260305</BANKERSDATE>", instrument="CH1", amount="400.00"),
        bank_line(instrument="CH2", amount="600.00"),
        bank_line("<BANKERSDATE>20260310</BANKERSDATE><BANKMANUALSTATUS>No</BANKMANUALSTATUS>", instrument="CH3", amount="0.00")))
    got = {a.instrument_number: (a.bankers_date, a.bank_manual_status) for a in allocations(harness)}
    assert got == {"CH1": (date(2026, 3, 5), None), "CH2": (None, None), "CH3": (date(2026, 3, 10), "No")}


def test_reimport_with_a_cleared_date_updates_without_duplicates(harness):
    load(harness, voucher_xml(bank_line()))
    xml = voucher_xml(bank_line("<BANKERSDATE>20260305</BANKERSDATE>")).replace("<ALTERID> 3<", "<ALTERID> 4<")
    load(harness, xml)
    load(harness, xml)
    (alloc,) = allocations(harness)
    assert alloc.bankers_date == date(2026, 3, 5)


def test_entries_cleared_in_tally_need_no_manual_match(harness):
    import app.models.portal_core as P
    from app.routers import auth, bank_recon
    from tests.conftest import bearer, login

    load(harness, voucher_xml(bank_line("<BANKERSDATE>20260305</BANKERSDATE>"), guid="g-cleared", master=1))
    load(harness, voucher_xml(bank_line(), guid="g-open", master=2).replace("<VOUCHERNUMBER>1<", "<VOUCHERNUMBER>2<"))

    cid = harness.scalar(select(MstGroup.company_id))
    role = harness.role("Clerk")
    module = harness.add(P.Module(code="vouchers", name="Vouchers"))
    harness.add(P.Permission(role_id=role.role_id, module_id=module.module_id, can_read=True))
    company = harness.scalar(select(P.Company).where(P.Company.company_id == cid))
    clerk = harness.user(company, role, "clerk")
    client = harness.app(auth.router, bank_recon.router)
    headers = bearer(login(client, clerk.email))
    bank_id = harness.scalar(select(MstLedger.ledger_id).where(MstLedger.name == "HDFC Bank"))

    url = f"/bank-recon/unmatched-books?bank_ledger_id={bank_id}"
    rows = client.get(url, headers=headers).json()
    assert [r["voucher_number"] for r in rows] == ["2"] and rows[0]["cleared_in_tally"] is False

    everything = {r["voucher_number"]: r for r in client.get(url + "&include_cleared=true", headers=headers).json()}
    assert everything["1"]["cleared_in_tally"] is True and everything["1"]["tally_cleared_date"] == "2026-03-05"
