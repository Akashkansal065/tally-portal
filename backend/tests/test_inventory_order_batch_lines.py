"""WS-11: order, due date and tracking number on stock lines, and every BATCHALLOCATIONS.LIST row kept as a child."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

import app.models.tally_core as T
from app.services.tally_xml_importer import import_tally_xml, parse_batch_allocations
from tests.conftest import run

import xml.etree.ElementTree as ET


def line(item="Widget", qty="10 Nos", body="", positive="No", amount="1000.00", rate="100.00/Nos"):
    return (f"<ALLINVENTORYENTRIES.LIST><STOCKITEMNAME>{item}</STOCKITEMNAME><ISDEEMEDPOSITIVE>{positive}</ISDEEMEDPOSITIVE>"
            f"<RATE>{rate}</RATE><AMOUNT>{amount}</AMOUNT><ACTUALQTY> {qty}</ACTUALQTY><BILLEDQTY> {qty}</BILLEDQTY>{body}"
            "</ALLINVENTORYENTRIES.LIST>")


def alloc(**f):
    return "<BATCHALLOCATIONS.LIST>" + "".join(f"<{k.upper()}>{v}</{k.upper()}>" for k, v in f.items()) + "</BATCHALLOCATIONS.LIST>"


def voucher(*lines, number="1", alter=1, guid="g-inv-1"):
    return ("<ENVELOPE><BODY><DATA><COLLECTION>"
            f'<VOUCHER VCHTYPE="Delivery Note"><DATE>20260301</DATE><GUID>{guid}</GUID><MASTERID> 81</MASTERID><ALTERID> {alter}</ALTERID>'
            f"<VOUCHERTYPENAME>Delivery Note</VOUCHERTYPENAME><VOUCHERNUMBER>{number}</VOUCHERNUMBER>"
            + "".join(lines) + "</VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>")


@pytest.fixture
def company(harness):
    c = harness.company("Alpha")
    harness.user(c, harness.role("Admin"), "owner")
    cid = c.company_id
    harness.add(T.MstVoucherType(company_id=cid, name="Delivery Note", parent_type="Delivery Note",
                                 numbering_method="Automatic", next_number=1))
    return c


def load(harness, company, xml):
    async def go():
        async with harness.Session() as db:
            res = await import_tally_xml(xml, db, 1, target_company_id=company.company_id)
            await db.commit()
            return res
    return run(go())


def entries(harness):
    return [r[0] for r in harness.query(select(T.TrnInventory).order_by(T.TrnInventory.stock_entry_id))]


def allocs(harness):
    return [r[0] for r in harness.query(select(T.StockEntryBatchAllocation).order_by(T.StockEntryBatchAllocation.id))]


def godowns(harness):
    return {gid: name for gid, name in harness.query(select(T.MstGodown.godown_id, T.MstGodown.name))}


def test_multiple_batches_become_child_rows_with_order_references(harness, company):
    body = (alloc(batchname="B-001", godownname="Main", actualqty="6 Nos", billedqty="6 Nos", amount="600.00", rate="100.00/Nos",
                  orderno="SO-77", orderduedate="15-Mar-2026", trackingnumber="TRK-1")
            + alloc(batchname="B-002", godownname="Annexe", destinationgodownname="Showroom", actualqty="4 Nos",
                    billedqty="4 Nos", amount="400.00", orderno="SO-77", orderduedate="15-Mar-2026", trackingnumber="TRK-1"))
    load(harness, company, voucher(line(body=body)))
    (e,) = entries(harness)
    assert (e.order_number, e.order_due_date, e.tracking_number) == ("SO-77", date(2026, 3, 15), "TRK-1")
    a1, a2 = allocs(harness)
    g = godowns(harness)
    assert (a1.line_no, a1.batch_name, g[a1.godown_id], a1.quantity, a1.rate, a1.amount) == (1, "B-001", "Main", Decimal("6"), Decimal("100.00"), Decimal("600.00"))
    assert (a2.line_no, a2.batch_name, g[a2.godown_id], g[a2.destination_godown_id], a2.quantity) == (2, "B-002", "Annexe", "Showroom", Decimal("4"))
    assert a1.stock_entry_id == a2.stock_entry_id == e.stock_entry_id


def test_partial_fulfilment_keeps_the_quantities_as_given(harness, company):
    # ordered 10, this delivery covers 4: the allocation says 4 and the line says 4; nothing is topped up
    load(harness, company, voucher(line(qty="4 Nos", amount="400.00",
                                        body=alloc(batchname="B-9", actualqty="4 Nos", orderno="SO-80", orderduedate="20260331"))))
    (e,) = entries(harness)
    (a,) = allocs(harness)
    assert (e.quantity, a.quantity, a.order_due_date) == (Decimal("4"), Decimal("4"), date(2026, 3, 31))


def test_absent_tags_leave_everything_empty_and_the_import_unchanged(harness, company):
    load(harness, company, voucher(line()))
    (e,) = entries(harness)
    assert (e.order_number, e.order_due_date, e.tracking_number) == (None, None, None)
    assert e.quantity == Decimal("10") and e.amount == Decimal("1000.00")
    assert allocs(harness) == []


def test_signed_quantities_are_kept_with_their_sign(harness, company):
    body = alloc(batchname="B-1", godownname="Main", actualqty="-3 Nos", billedqty="-3 Nos", amount="-300.00")
    load(harness, company, voucher(line(qty="3 Nos", body=body)))
    (a,) = allocs(harness)
    assert (a.quantity, a.amount) == (Decimal("-3"), Decimal("-300.00"))


def test_bad_rows_are_checked_one_at_a_time(harness, company):
    body = (alloc(batchname="B-OK", actualqty="2 Nos")
            + alloc(actualqty="lots", amount="x", orderduedate="whenever")        # nothing usable but a bad number: dropped
            + alloc(batchname="B-BAD-NUM", actualqty="many", orderduedate="soon")  # kept, bad values left empty
            + "<BATCHALLOCATIONS.LIST></BATCHALLOCATIONS.LIST>"
            + alloc(batchname="Primary Batch", godownname="Main", actualqty="1 Nos"))
    res = load(harness, company, voucher(line(qty="3 Nos", body=body)))
    assert res.get("status") != "error"
    names = [(a.batch_name, a.quantity, a.order_due_date) for a in allocs(harness)]
    assert names == [("B-OK", Decimal("2"), None), ("B-BAD-NUM", None, None), (None, Decimal("1"), None)]


def test_tracking_numbers_are_not_deduplicated(harness, company):
    body = alloc(batchname="B-1", trackingnumber="TRK-DUP", actualqty="1 Nos")
    load(harness, company, voucher(line(item="A", body=body), line(item="B", body=body)))
    load(harness, company, voucher(line(item="A", body=body), number="2", guid="g-inv-2"))
    rows = entries(harness)
    assert [e.tracking_number for e in rows] == ["TRK-DUP"] * 3
    assert [a.tracking_number for a in allocs(harness)] == ["TRK-DUP"] * 3


def test_an_altered_voucher_replaces_its_children_without_duplicates(harness, company):
    first = alloc(batchname="B-1", actualqty="6 Nos") + alloc(batchname="B-2", actualqty="4 Nos")
    load(harness, company, voucher(line(body=first), alter=1))
    load(harness, company, voucher(line(body=alloc(batchname="B-3", actualqty="10 Nos")), alter=2))
    load(harness, company, voucher(line(body=alloc(batchname="B-3", actualqty="10 Nos")), alter=2))     # same again
    assert [a.batch_name for a in allocs(harness)] == ["B-3"]
    assert len(entries(harness)) == 1


def test_the_parser_alone_reads_the_tally_shape():
    node = ET.fromstring(f"<X>{alloc(batchname='B', actualqty='5 Nos', trackingnumber='T')}</X>")
    (row,) = parse_batch_allocations(node)
    assert (row["batch_name"], row["quantity"], row["tracking_number"]) == ("B", Decimal("5"), "T")


def test_books_parity_and_ledger_entries_are_not_touched_by_batch_rows(harness, company):
    """Batch rows live beside the stock line; voucher_entries (what balances and the parity check sum) are the
    same with or without them."""
    from app.services.books_parity import build_parity_report
    cid = company.company_id
    g = harness.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    harness.add(T.MstLedger(company_id=cid, name="Party", group_id=g.group_id, tally_guid="lg-p", tally_master_id=5),
                T.MstVoucherType(company_id=cid, name="Sales", parent_type="Sales", numbering_method="Automatic", next_number=1))
    body = alloc(batchname="B-1", godownname="Main", actualqty="10 Nos", amount="1000.00")
    xml = ("<ENVELOPE><BODY><DATA><COLLECTION>"
           '<VOUCHER VCHTYPE="Sales"><DATE>20260301</DATE><GUID>g-s-1</GUID><MASTERID> 90</MASTERID><ALTERID> 1</ALTERID>'
           "<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME><VOUCHERNUMBER>1</VOUCHERNUMBER>"
           "<ALLLEDGERENTRIES.LIST><LEDGERNAME>Party</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-1000.00</AMOUNT></ALLLEDGERENTRIES.LIST>"
           + line(body=body) + "</VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>")
    load(harness, company, xml)
    assert len(allocs(harness)) == 1
    assert len(harness.query(select(T.TrnAccounting))) == 1       # only the ledger line; batch rows add none

    async def go():
        async with harness.Session() as db:
            result = await build_parity_report(db, cid, "list-0001", [{"master_id": 90, "guid": "g-s-1", "date": "20260301", "voucher_type": "Sales"}],
                                               [{"guid": "lg-p", "master_id": 5, "closing_balance": "-1000.00"}])
            await db.commit()
            return result
    result = run(go())
    assert result["ledgers_drifting"] == 0 and result["voucher_count_drift"] == 0
