"""
Vouchers and Tally: the number comes from Tally, a refused change is undone, a change made while Tally is away
is kept and queued, and no send, however often repeated, makes a second voucher.

Tally is replaced by FakeTally, which behaves the way the live audit found TallyPrime to behave.
"""
import re
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.portal_core import SyncQueue
from app.models.tally_core import MstGroup, MstLedger, MstVoucherConfiguration, MstVoucherType, TrnBill, TrnVoucher
from app.routers import auth, sync, vouchers
from tests.conftest import bearer, login


class FakeTally:
    def __init__(self):
        self.vouchers = {}          # master id -> {"remote_id", "guid", "number", "date", "vtype", "cancelled", "xml"}
        self.next_master = 300
        self.last_number = {}       # voucher type -> last number given
        self.down = False
        self.refuse = None          # reason to refuse every import with
        self.lose_next_reply = False
        self.imports = []

    # -- what a user working in Tally itself does --
    def enter_in_tally(self, vtype, vdate):
        return self._create(None, vtype, vdate, "")

    def _create(self, remote_id, vtype, vdate, xml):
        self.next_master += 1
        self.last_number[vtype] = self.last_number.get(vtype, 0) + 1
        self.vouchers[self.next_master] = {"remote_id": remote_id, "guid": f"tally-guid-{self.next_master:08x}",
                                           "number": str(self.last_number[vtype]), "date": vdate, "vtype": vtype,
                                           "cancelled": False, "xml": xml}
        return self.next_master

    def of_type(self, vtype):
        return [v for v in self.vouchers.values() if v["vtype"] == vtype]

    # -- the HTTP endpoint --
    def __call__(self, url, xml, timeout=5):
        if self.down:
            return ""
        if "<TALLYREQUEST>Export</TALLYREQUEST>" in xml:
            return self._find(xml)
        self.imports.append(xml)
        reply = self._import(xml)
        if self.lose_next_reply:
            self.lose_next_reply = False
            return ""
        return reply

    def _find(self, xml):
        by_master = re.search(r"\$MasterID = (\d+)", xml)
        by_guid = re.search(r'\$GUID = "([^"]*)"', xml)
        found = None
        if by_master and int(by_master.group(1)) in self.vouchers:
            found = int(by_master.group(1))
        elif by_guid:
            found = next((m for m, v in self.vouchers.items() if v["guid"] == by_guid.group(1)), None)
        if found is None:
            return "<ENVELOPE><BODY><DATA><COLLECTION></COLLECTION></DATA></BODY></ENVELOPE>"
        v = self.vouchers[found]
        return (f'<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER REMOTEID="{v["guid"]}" VCHTYPE="{v["vtype"]}">'
                f'<DATE TYPE="Date">{v["date"]}</DATE><GUID>{v["guid"]}</GUID><MASTERID> {found}</MASTERID><ALTERID> 9</ALTERID>'
                f'<VOUCHERNUMBER>{v["number"]}</VOUCHERNUMBER><ISCANCELLED>{"Yes" if v["cancelled"] else "No"}</ISCANCELLED>'
                f'</VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>')

    @staticmethod
    def _reply(created=0, altered=0, deleted=0, last=0, error=None):
        line = f"<LINEERROR>{error}</LINEERROR>" if error else ""
        return (f"<ENVELOPE><HEADER><STATUS>1</STATUS></HEADER><BODY><DATA><IMPORTRESULT>{line}<CREATED>{created}</CREATED>"
                f"<ALTERED>{altered}</ALTERED><DELETED>{deleted}</DELETED><LASTVCHID>{last}</LASTVCHID>"
                f"<ERRORS>{1 if error else 0}</ERRORS><EXCEPTIONS>0</EXCEPTIONS></IMPORTRESULT></DATA></BODY></ENVELOPE>")

    def _import(self, xml):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r"<VOUCHER ([^>]*)>", xml).group(1)))
        action, vtype = attrs["ACTION"], attrs["VCHTYPE"]
        body_date = re.search(r"<DATE>(\d{8})</DATE>", xml).group(1)
        master = None
        if attrs.get("TAGNAME") == "MASTERID":
            # Tally looks for the master id under the date given with it
            candidate = int(attrs["TAGVALUE"])
            if candidate in self.vouchers and self.vouchers[candidate]["date"] == attrs.get("DATE"):
                master = candidate
        elif attrs.get("REMOTEID"):
            master = next((m for m, v in self.vouchers.items() if v["remote_id"] == attrs["REMOTEID"]), None)

        if action == "Delete":
            if master is None or self.refuse:
                return self._reply(error=self.refuse or "Cannot be deleted!")
            del self.vouchers[master]
            return self._reply(deleted=1, last=master)
        if self.refuse:
            return self._reply(error=self.refuse)
        if action == "Cancel":
            if master is None:
                return self._reply(error="Voucher does not exist!")
            self.vouchers[master]["cancelled"] = True
            return self._reply(altered=1, last=master)
        if master is None:
            # Create, and also an Alter that matches nothing: Tally makes a new voucher
            master = self._create(attrs.get("REMOTEID"), vtype, body_date, xml)
            self.vouchers[master]["cancelled"] = "<ISCANCELLED>Yes</ISCANCELLED>" in xml
            return self._reply(created=1, last=master)
        self.vouchers[master].update(date=body_date, xml=xml)
        return self._reply(altered=1, last=master)


@pytest.fixture
def setup(harness, monkeypatch):
    tally = FakeTally()
    monkeypatch.setattr(settings, "TALLY_URL", "http://tally.test:9000")
    monkeypatch.setattr(sync, "_post_to_tally_sync", tally)
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    cid = company.company_id
    debtors = harness.add(MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    cash_group = harness.add(MstGroup(company_id=cid, name="Cash-in-Hand", nature="Asset"))
    sales_group = harness.add(MstGroup(company_id=cid, name="Sales Accounts", nature="Income"))
    party = harness.add(MstLedger(company_id=cid, name="Customer", group_id=debtors.group_id))
    cash = harness.add(MstLedger(company_id=cid, name="Cash", group_id=cash_group.group_id))
    sales = harness.add(MstLedger(company_id=cid, name="Sales", group_id=sales_group.group_id))
    receipt = harness.add(MstVoucherType(company_id=cid, name="Receipt", parent_type="Receipt", numbering_method="Automatic", next_number=1))
    sale = harness.add(MstVoucherType(company_id=cid, name="Sales", parent_type="Sales", numbering_method="Automatic", next_number=1))
    client = harness.app(auth.router, vouchers.router, sync.router)
    headers = bearer(login(client, admin.email))

    class Setup:
        pass
    s = Setup()
    s.harness, s.tally, s.client, s.headers, s.company_id = harness, tally, client, headers, cid
    s.receipt_body = lambda amount=100, day="2026-03-01": {
        "voucher_type_id": receipt.voucher_type_id, "voucher_date": day, "narration": "test", "party_ledger_id": party.ledger_id,
        "entries": [{"ledger_id": party.ledger_id, "credit_amount": amount}, {"ledger_id": cash.ledger_id, "debit_amount": amount}]}
    s.sales_body = lambda amount=200: {
        "voucher_type_id": sale.voucher_type_id, "voucher_date": "2026-03-01", "party_ledger_id": party.ledger_id,
        "entries": [{"ledger_id": party.ledger_id, "debit_amount": amount}, {"ledger_id": sales.ledger_id, "credit_amount": amount}]}
    s.receipt_type_id = receipt.voucher_type_id
    s.voucher = lambda vid: harness.query(select(TrnVoucher).where(TrnVoucher.voucher_id == vid))[0][0]
    s.pending = lambda: [(r.record_id, r.action) for (r,) in harness.query(select(SyncQueue).where(SyncQueue.is_processed == False))]  # noqa: E712
    return s


def test_tally_numbers_the_voucher_and_the_app_takes_that_number(setup):
    setup.tally.last_number["Receipt"] = 53  # Tally is far ahead of the app's own counter

    reply = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body())

    assert reply.status_code == 201, reply.text
    body = reply.json()
    assert (body["voucher_number"], body["number_is_provisional"], body["tally_status"]) == ("54", False, "SUCCESS")
    assert body["tally_master_id"] == 301 and body["tally_guid"] == "tally-guid-0000012d"
    assert "provisionally 1" in body["tally_message"]
    # The app's counter follows Tally's, so the next provisional number is a likely one
    assert setup.harness.scalar(select(MstVoucherType.next_number).where(MstVoucherType.voucher_type_id == setup.receipt_type_id)) == 55
    assert setup.pending() == []


def test_a_bill_named_after_the_provisional_number_follows_tallys_number(setup):
    setup.tally.last_number["Sales"] = 74

    body = setup.client.post("/vouchers", headers=setup.headers, json=setup.sales_body()).json()

    assert body["voucher_number"] == "75"
    assert setup.harness.scalar(select(TrnBill.bill_reference)) == "75"
    assert len(setup.tally.of_type("Sales")) == 1
    assert "<NAME>75</NAME>" in setup.tally.of_type("Sales")[0]["xml"]


def test_created_while_tally_is_away_then_tally_user_takes_the_same_number(setup):
    setup.tally.down = True
    reply = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body(700))
    assert reply.status_code == 201, reply.text
    offline = reply.json()
    assert (offline["voucher_number"], offline["number_is_provisional"], offline["tally_status"]) == ("1", True, "NO_RESPONSE")
    vid = offline["voucher_id"]
    assert setup.pending() == [(vid, "Create")]

    # Meanwhile someone enters a receipt in Tally itself; it gets number 1 there
    setup.tally.down = False
    theirs = setup.tally.enter_in_tally("Receipt", "20260301")
    assert setup.tally.vouchers[theirs]["number"] == "1"

    retry = setup.client.post(f"/vouchers/{vid}/retry-sync", headers=setup.headers).json()

    assert retry["tally_status"] == "SUCCESS"
    mine = setup.voucher(vid)
    assert (mine.voucher_number, mine.number_is_provisional) == ("2", False)
    assert setup.tally.vouchers[theirs]["number"] == "1"       # theirs is untouched
    assert len(setup.tally.of_type("Receipt")) == 2
    assert setup.pending() == []


def test_sending_again_never_makes_a_second_voucher(setup):
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()["voucher_id"]

    for _ in range(3):
        assert setup.client.post(f"/vouchers/{vid}/retry-sync", headers=setup.headers).json()["tally_status"] == "SUCCESS"

    assert len(setup.tally.of_type("Receipt")) == 1


def test_a_lost_reply_is_recovered_by_the_next_send(setup):
    setup.tally.lose_next_reply = True       # Tally saves the voucher but the answer never arrives
    first = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()
    assert (first["tally_status"], first["number_is_provisional"]) == ("NO_RESPONSE", True)
    assert len(setup.tally.of_type("Receipt")) == 1

    setup.client.post(f"/vouchers/{first['voucher_id']}/retry-sync", headers=setup.headers)

    assert len(setup.tally.of_type("Receipt")) == 1
    mine = setup.voucher(first["voucher_id"])
    assert (mine.tally_master_id, mine.number_is_provisional) == (301, False)


def test_a_create_tally_refuses_is_not_kept(setup):
    setup.tally.refuse = "Ledger 'Customer' does not exist!"

    reply = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body())

    assert reply.status_code == 400
    assert "Ledger 'Customer' does not exist!" in reply.json()["detail"]
    assert setup.harness.query(select(TrnVoucher)) == []
    assert setup.harness.scalar(select(MstVoucherType.next_number).where(MstVoucherType.voucher_type_id == setup.receipt_type_id)) == 1
    assert setup.pending() == []
    # ... and the leftover a refused create leaves in Tally is asked to be removed, by this voucher's own id
    assert 'ACTION="Delete"' in setup.tally.imports[-1] and 'REMOTEID="MYTALLY-' in setup.tally.imports[-1]


def test_an_edit_tally_refuses_is_undone(setup):
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body(100)).json()["voucher_id"]
    setup.tally.refuse = "Voucher date is beyond the allowed period"

    reply = setup.client.put(f"/vouchers/{vid}", headers=setup.headers, json=setup.receipt_body(999))

    assert reply.status_code == 400
    assert float(setup.voucher(vid).total_amount) == 100.0


def test_an_edit_that_moves_the_date_alters_the_same_voucher(setup):
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body(100, "2026-03-01")).json()["voucher_id"]

    reply = setup.client.put(f"/vouchers/{vid}", headers=setup.headers, json=setup.receipt_body(150, "2026-03-02"))

    assert reply.status_code == 200, reply.text
    assert len(setup.tally.of_type("Receipt")) == 1
    assert setup.tally.of_type("Receipt")[0]["date"] == "20260302"
    # Addressed to the date Tally held, with the new date inside
    assert 'DATE="20260301" TAGNAME="MASTERID" TAGVALUE="301"' in setup.tally.imports[-1]
    assert setup.voucher(vid).tally_date == date(2026, 3, 2)


def test_a_voucher_entered_in_tally_is_edited_in_place_by_its_master_id(setup):
    theirs = setup.tally.enter_in_tally("Receipt", "20260301")
    imported = setup.harness.add(TrnVoucher(
        company_id=setup.company_id, voucher_type_id=setup.receipt_type_id, voucher_number="1", voucher_date=date(2026, 3, 1),
        total_amount=300, status="confirmed", tally_guid=setup.tally.vouchers[theirs]["guid"], created_by=1))

    reply = setup.client.put(f"/vouchers/{imported.voucher_id}", headers=setup.headers, json=setup.receipt_body(350))

    assert reply.status_code == 200, reply.text
    assert len(setup.tally.of_type("Receipt")) == 1
    # Never under Tally's GUID as a REMOTEID: Tally would make a second voucher
    assert "REMOTEID" not in setup.tally.imports[-1] and f'TAGVALUE="{theirs}"' in setup.tally.imports[-1]
    assert setup.voucher(imported.voucher_id).tally_master_id == theirs


def test_a_delete_tally_refuses_keeps_the_voucher(setup):
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()["voucher_id"]
    setup.tally.refuse = "Cannot be deleted!"

    reply = setup.client.delete(f"/vouchers/{vid}", headers=setup.headers)

    assert reply.status_code == 409
    assert setup.voucher(vid).voucher_id == vid
    assert len(setup.tally.of_type("Receipt")) == 1
    assert setup.pending() == []


def test_deleted_while_tally_is_away_is_deleted_in_tally_later_by_master_id(setup):
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()["voucher_id"]
    setup.tally.down = True

    reply = setup.client.delete(f"/vouchers/{vid}", headers=setup.headers)

    assert reply.status_code == 200 and reply.json()["tally_status"] == "NO_RESPONSE"
    assert setup.harness.query(select(TrnVoucher)) == []
    assert setup.pending() == [(vid, "Delete")]

    setup.tally.down = False
    sync_id = setup.harness.scalar(select(SyncQueue.sync_id).where(SyncQueue.is_processed == False))  # noqa: E712
    first = setup.client.post(f"/sync/queue/{sync_id}/retry", headers=setup.headers).json()
    again = setup.client.post(f"/sync/queue/{sync_id}/retry", headers=setup.headers).json()

    assert (first["status_code"], again["status_code"]) == ("SUCCESS", "ALREADY_ABSENT")
    assert setup.tally.of_type("Receipt") == []
    assert 'TAGNAME="MASTERID" TAGVALUE="301"' in setup.tally.imports[-1] and "Voucher Number" not in "".join(setup.tally.imports)


def test_created_and_deleted_while_tally_is_away_settles_without_touching_tally(setup):
    setup.tally.down = True
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()["voucher_id"]
    setup.client.delete(f"/vouchers/{vid}", headers=setup.headers)
    assert setup.pending() == [(vid, "Delete")]      # the unsent create is closed by the delete

    setup.tally.down = False
    theirs = setup.tally.enter_in_tally("Receipt", "20260301")
    sync_id = setup.harness.scalar(select(SyncQueue.sync_id).where(SyncQueue.is_processed == False))  # noqa: E712
    result = setup.client.post(f"/sync/queue/{sync_id}/retry", headers=setup.headers).json()

    assert result["status_code"] == "ALREADY_ABSENT"
    assert list(setup.tally.vouchers) == [theirs]


def test_cancel_reaches_tally_and_a_refused_cancel_is_undone(setup):
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()["voucher_id"]

    setup.tally.refuse = "Voucher is locked"
    assert setup.client.post(f"/vouchers/{vid}/cancel", headers=setup.headers).status_code == 400
    assert setup.voucher(vid).status == "confirmed"

    setup.tally.refuse = None
    assert setup.client.post(f"/vouchers/{vid}/cancel", headers=setup.headers).json()["tally_status"] == "SUCCESS"
    assert setup.voucher(vid).status == "cancelled"
    assert setup.tally.of_type("Receipt")[0]["cancelled"] is True


def test_the_sync_agent_reports_tallys_number_back(setup):
    setup.tally.down = True                  # the backend cannot reach Tally itself; the agent pushes for it
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()["voucher_id"]
    report = [{"voucher_id": vid, "master_id": 512, "guid": "tally-guid-00000200", "number": "88", "date": "20260301"}]

    for _ in range(2):
        reply = setup.client.post("/sync/voucher-identities", headers=setup.headers, json=report)
        assert reply.status_code == 200 and reply.json()["updated"] == 1

    mine = setup.voucher(vid)
    assert (mine.voucher_number, mine.number_is_provisional, mine.tally_master_id, mine.tally_guid) == ("88", False, 512, "tally-guid-00000200")
    # The queued payload for the agent now addresses the voucher Tally holds, under the date it has there
    queue = setup.client.get("/sync/outbound-queue", headers=setup.headers).json()
    assert 'DATE="20260301" TAGNAME="MASTERID" TAGVALUE="512"' in queue[0]["xml_payload"] and 'ACTION="Alter"' in queue[0]["xml_payload"]


def test_a_reused_row_id_never_reaches_another_voucher_in_tally(setup):
    # Tally holds a voucher that was once pushed by an app voucher whose row id has since been reused
    theirs = setup.tally._create("MYTALLY-VCH-1", "Receipt", "20260301", "")
    setup.tally.down = True
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()["voucher_id"]
    assert vid == 1
    setup.tally.down = False

    # Never sent, so deleting it has nothing to remove in Tally
    assert setup.client.delete(f"/vouchers/{vid}", headers=setup.headers).json()["tally_status"] == "ALREADY_ABSENT"
    assert list(setup.tally.vouchers) == [theirs]

    # ... and a new voucher on that row id is created beside it, not written over it
    setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body())
    assert len(setup.tally.vouchers) == 2 and setup.tally.vouchers[theirs]["xml"] == ""


def test_a_voucher_whose_reply_was_lost_is_recognised_when_tally_is_read(setup):
    from app.services.tally_xml_importer import import_tally_xml
    from tests.conftest import run
    setup.tally.lose_next_reply = True
    vid = setup.client.post("/vouchers", headers=setup.headers, json=setup.receipt_body()).json()["voucher_id"]
    sent_as = setup.voucher(vid).tally_remote_id
    assert sent_as and f"<REMOTEALTGUID>{sent_as}</REMOTEALTGUID>" in setup.tally.imports[-1]
    xml = (f'<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER VCHTYPE="Receipt"><DATE>20260301</DATE><GUID>tally-guid-0000012d</GUID>'
           f'<MASTERID> 301</MASTERID><ALTERID> 9</ALTERID><REMOTEALTGUID>{sent_as}</REMOTEALTGUID><VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>'
           f'<VOUCHERNUMBER>7</VOUCHERNUMBER></VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>')

    async def go():
        async with setup.harness.Session() as db:
            await import_tally_xml(xml, db, 1, override_company_name="Alpha")
            await db.commit()
    run(go())

    rows = setup.harness.query(select(TrnVoucher.voucher_id, TrnVoucher.voucher_number, TrnVoucher.tally_guid, TrnVoucher.tally_master_id))
    assert rows == [(vid, "7", "tally-guid-0000012d", 301)]


def test_a_stock_journal_goes_to_tally_as_items_in_and_items_out(setup):
    from app.models.tally_core import MstStockItem, MstUom, TrnInventory
    cid = setup.company_id
    unit = setup.harness.add(MstUom(company_id=cid, name="nos", symbol="nos"))
    part = setup.harness.add(MstStockItem(company_id=cid, name="Part", unit_id=unit.unit_id))
    made = setup.harness.add(MstStockItem(company_id=cid, name="Made", unit_id=unit.unit_id))
    journal = setup.harness.add(MstVoucherType(company_id=cid, name="Stock Journal", parent_type="Stock Journal", numbering_method="Automatic", next_number=1))

    reply = setup.client.post("/vouchers", headers=setup.headers, json={
        "voucher_type_id": journal.voucher_type_id, "voucher_date": "2026-03-01", "narration": "assembly",
        "inventory_entries": [
            {"stock_item_id": part.stock_item_id, "quantity": 4, "rate": 50, "amount": 200, "flow_type": "source"},
            {"stock_item_id": made.stock_item_id, "quantity": 1, "rate": 200, "amount": 200, "flow_type": "destination"}]})

    assert reply.status_code == 201, reply.text
    assert (reply.json()["tally_status"], reply.json()["total_amount"]) == ("SUCCESS", "200.00")
    sent = setup.tally.imports[-1]
    assert 'OBJVIEW="Consumption Voucher View"' in sent and "LEDGERENTRIES.LIST" not in sent and "PARTYLEDGERNAME" not in sent
    out, into = sent.split("<INVENTORYENTRIESOUT.LIST>")[1], sent.split("<INVENTORYENTRIESIN.LIST>")[1].split("</INVENTORYENTRIESIN.LIST>")[0]
    assert "<STOCKITEMNAME>Part</STOCKITEMNAME>" in out and "<ACTUALQTY> 4 nos</ACTUALQTY>" in out and "<AMOUNT>200.00</AMOUNT>" in out
    assert "<STOCKITEMNAME>Made</STOCKITEMNAME>" in into and "<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>" in into and "<AMOUNT>-200.00</AMOUNT>" in into
    # In the app, what is consumed leaves stock and what is produced arrives
    rows = setup.harness.query(select(TrnInventory.flow_type, TrnInventory.is_inward).order_by(TrnInventory.stock_entry_id))
    assert rows == [("source", False), ("destination", True)]
    assert dict(setup.harness.query(select(MstStockItem.name, MstStockItem.closing_qty))) == {"Part": -4, "Made": 1}


def test_a_stock_journal_read_from_tally_keeps_its_two_sides(setup):
    from app.models.tally_core import MstStockItem, MstUom, TrnInventory
    from app.services.tally_xml_importer import import_tally_xml
    from tests.conftest import run
    cid = setup.company_id
    unit = setup.harness.add(MstUom(company_id=cid, name="nos", symbol="nos"))
    setup.harness.add(MstStockItem(company_id=cid, name="Part", unit_id=unit.unit_id), MstStockItem(company_id=cid, name="Made", unit_id=unit.unit_id))
    line = lambda tag, name, positive, qty: (f"<{tag}><STOCKITEMNAME>{name}</STOCKITEMNAME><ISDEEMEDPOSITIVE>{positive}</ISDEEMEDPOSITIVE>"
                                             f"<RATE>50.00/nos</RATE><AMOUNT>200.00</AMOUNT><ACTUALQTY> {qty} nos</ACTUALQTY><BILLEDQTY> {qty} nos</BILLEDQTY></{tag}>")
    xml = ('<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER VCHTYPE="Stock Journal"><DATE>20260301</DATE><GUID>guid-sj</GUID><MASTERID> 77</MASTERID>'
           '<ALTERID> 9</ALTERID><VOUCHERTYPENAME>Stock Journal</VOUCHERTYPENAME><VOUCHERNUMBER>1</VOUCHERNUMBER>'
           + line("INVENTORYENTRIESIN.LIST", "Made", "Yes", 1) + line("INVENTORYENTRIESOUT.LIST", "Part", "No", 4)
           # Tally can repeat the same lines here; they must not be counted twice
           + line("ALLINVENTORYENTRIES.LIST", "Made", "Yes", 1) + line("ALLINVENTORYENTRIES.LIST", "Part", "No", 4)
           + "</VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>")

    async def go():
        async with setup.harness.Session() as db:
            await import_tally_xml(xml, db, 1, override_company_name="Alpha")
            await db.commit()
    run(go())

    rows = setup.harness.query(select(MstStockItem.name, TrnInventory.flow_type, TrnInventory.is_inward, TrnInventory.quantity)
                               .join(MstStockItem, MstStockItem.stock_item_id == TrnInventory.stock_item_id).order_by(MstStockItem.name))
    assert [(n, f, i, int(q)) for n, f, i, q in rows] == [("Made", "destination", True, 1), ("Part", "source", False, 4)]
    assert float(setup.harness.scalar(select(TrnVoucher.total_amount))) == 200.0


def test_a_physical_stock_count_sets_stock_to_the_counted_figure(setup):
    from app.models.tally_core import MstStockItem, MstUom, TrnInventory
    cid = setup.company_id
    unit = setup.harness.add(MstUom(company_id=cid, name="nos", symbol="nos"))
    item = setup.harness.add(MstStockItem(company_id=cid, name="Widget", unit_id=unit.unit_id, closing_qty=4))
    count = setup.harness.add(MstVoucherType(company_id=cid, name="Physical Stock", parent_type="Physical Stock", numbering_method="Automatic", next_number=1))
    closing = lambda: float(setup.harness.scalar(select(MstStockItem.closing_qty)))
    body = lambda qty: {"voucher_type_id": count.voucher_type_id, "voucher_date": "2026-03-01", "narration": "count",
                        "inventory_entries": [{"stock_item_id": item.stock_item_id, "quantity": qty, "rate": 0, "amount": 0}]}

    reply = setup.client.post("/vouchers", headers=setup.headers, json=body(10))

    assert reply.status_code == 201, reply.text
    assert closing() == 10
    assert [(float(q), float(a), i) for q, a, i in setup.harness.query(select(TrnInventory.quantity, TrnInventory.actual_quantity, TrnInventory.is_inward))] == [(6, 10, True)]
    sent = setup.tally.imports[-1]
    assert 'OBJVIEW="Consumption Voucher View"' in sent and "<INVENTORYENTRIESIN.LIST>" in sent and "<ACTUALQTY> 10 nos</ACTUALQTY>" in sent
    assert "<AMOUNT>" not in sent and "<RATE>" not in sent and "INVENTORYENTRIESOUT" not in sent

    # Counting again lower: the earlier adjustment is taken back first, then the new count applies
    vid = reply.json()["voucher_id"]
    assert setup.client.put(f"/vouchers/{vid}", headers=setup.headers, json=body(3)).status_code == 200
    assert closing() == 3 and "<ACTUALQTY> 3 nos</ACTUALQTY>" in setup.tally.imports[-1]

    assert setup.client.delete(f"/vouchers/{vid}", headers=setup.headers).status_code == 200
    assert closing() == 4


def test_an_earlier_count_removed_leaves_a_later_count_in_charge(setup):
    from app.models.tally_core import MstStockItem, MstUom
    cid = setup.company_id
    unit = setup.harness.add(MstUom(company_id=cid, name="nos", symbol="nos"))
    item = setup.harness.add(MstStockItem(company_id=cid, name="Widget", unit_id=unit.unit_id, closing_qty=0))
    count = setup.harness.add(MstVoucherType(company_id=cid, name="Physical Stock", parent_type="Physical Stock", numbering_method="Automatic", next_number=1))
    journal = setup.harness.add(MstVoucherType(company_id=cid, name="Stock Journal", parent_type="Stock Journal", numbering_method="Automatic", next_number=1))
    closing = lambda: float(setup.harness.scalar(select(MstStockItem.closing_qty)))
    counted = lambda day, qty: setup.client.post("/vouchers", headers=setup.headers, json={
        "voucher_type_id": count.voucher_type_id, "voucher_date": day, "inventory_entries": [{"stock_item_id": item.stock_item_id, "quantity": qty, "rate": 0, "amount": 0}]}).json()["voucher_id"]
    moved = lambda day, qty, flow: setup.client.post("/vouchers", headers=setup.headers, json={
        "voucher_type_id": journal.voucher_type_id, "voucher_date": day, "inventory_entries": [{"stock_item_id": item.stock_item_id, "quantity": qty, "rate": 1, "amount": qty, "flow_type": flow}]}).json()["voucher_id"]

    first = counted("2026-03-01", 9)
    counted("2026-03-02", 7)
    assert closing() == 7

    # The earlier count goes: the later one still says 7
    assert setup.client.post(f"/vouchers/{first}/cancel", headers=setup.headers).status_code == 200
    assert closing() == 7
    # Something entered before the count is absorbed by it; something after it moves the stock
    moved("2026-03-01", 100, "destination")
    assert closing() == 7
    late = moved("2026-03-31", 2, "source")
    assert closing() == 5
    assert setup.client.delete(f"/vouchers/{late}", headers=setup.headers).status_code == 200
    assert closing() == 7


def test_attendance_voucher_carries_only_its_employee_lines(setup):
    from app.models.tally_core import TrnAttendance
    att = setup.harness.add(MstVoucherType(company_id=setup.company_id, name="Attendance", parent_type="Attendance", numbering_method="Automatic", next_number=1))
    body = lambda days: {"voucher_type_id": att.voucher_type_id, "voucher_date": "2026-03-01", "narration": "march",
                         "attendance_entries": [{"employee_name": "Ashish", "attendance_type": "Present", "value": days}]}

    reply = setup.client.post("/vouchers", headers=setup.headers, json=body(26))

    assert reply.status_code == 201, reply.text
    sent = setup.tally.imports[-1]
    assert "<ATTENDANCEENTRIES.LIST>" in sent and "<NAME>Ashish</NAME>" in sent and "<ATTENDANCETYPE>Present</ATTENDANCETYPE>" in sent
    assert "<ATTDTYPETIMEVALUE> 26</ATTDTYPETIMEVALUE>" in sent and "LEDGERENTRIES" not in sent and "INVENTORYENTRIES" not in sent
    vid = reply.json()["voucher_id"]
    assert setup.client.get(f"/vouchers/{vid}", headers=setup.headers).json()["attendance_entries"] == [
        {"employee_name": "Ashish", "attendance_type": "Present", "value": 26.0}]

    assert setup.client.put(f"/vouchers/{vid}", headers=setup.headers, json=body(24)).status_code == 200
    assert "<ATTDTYPETIMEVALUE> 24</ATTDTYPETIMEVALUE>" in setup.tally.imports[-1]
    assert [float(v) for (v,) in setup.harness.query(select(TrnAttendance.time_value))] == [24.0]

    assert setup.client.delete(f"/vouchers/{vid}", headers=setup.headers).status_code == 200
    assert setup.harness.query(select(TrnAttendance)) == []


def test_payroll_voucher_posts_pay_heads_against_the_payable_ledger(setup):
    from app.models.tally_core import MstPayHead, TrnAccounting, TrnPayHead
    cid = setup.company_id
    group = setup.harness.scalar(select(MstGroup.group_id))
    basic = setup.harness.add(MstLedger(company_id=cid, name="Basic Salary", group_id=group))
    pf = setup.harness.add(MstLedger(company_id=cid, name="PF Deduction", group_id=group))
    payable = setup.harness.add(MstLedger(company_id=cid, name="Salary Payable", group_id=group))
    setup.harness.add(MstPayHead(company_id=cid, name="Basic Salary", pay_head_type="Earnings for Employees"),
                      MstPayHead(company_id=cid, name="PF Deduction", pay_head_type="Deductions from Employees"))
    payroll = setup.harness.add(MstVoucherType(company_id=cid, name="Payroll", parent_type="Payroll", numbering_method="Automatic", next_number=1))

    reply = setup.client.post("/vouchers", headers=setup.headers, json={
        "voucher_type_id": payroll.voucher_type_id, "voucher_date": "2026-03-31", "narration": "march salary", "party_ledger_id": payable.ledger_id,
        "payroll_entries": [{"employee_name": "Ashish", "pay_head_name": "Basic Salary", "amount": 5000},
                            {"employee_name": "Ashish", "pay_head_name": "PF Deduction", "amount": 600}]})

    assert reply.status_code == 201, reply.text
    assert reply.json()["total_amount"] == "5000.00"
    lines = {name: (float(d), float(c)) for name, d, c in setup.harness.query(
        select(MstLedger.name, TrnAccounting.debit_amount, TrnAccounting.credit_amount).join(MstLedger, MstLedger.ledger_id == TrnAccounting.ledger_id))}
    assert lines == {"Basic Salary": (5000, 0), "PF Deduction": (0, 600), "Salary Payable": (0, 4400)}
    assert sorted(float(a) for (a,) in setup.harness.query(select(TrnPayHead.amount))) == [-5000.0, 600.0]
    sent = setup.tally.imports[-1]
    assert 'OBJVIEW="PaySlip Voucher View"' in sent and "<ASPAYSLIP>Yes</ASPAYSLIP>" in sent and "<PARTYLEDGERNAME>Salary Payable</PARTYLEDGERNAME>" in sent
    employee = sent.split("<EMPLOYEEENTRIES.LIST>")[1].split("</EMPLOYEEENTRIES.LIST>")[0]
    assert "<EMPLOYEENAME>Ashish</EMPLOYEENAME>" in employee and "<AMOUNT>-4400.00</AMOUNT>" in employee
    assert "<PAYHEADNAME>Basic Salary</PAYHEADNAME>" in employee and "<AMOUNT>-5000.00</AMOUNT>" in employee
    assert "<PAYHEADNAME>PF Deduction</PAYHEADNAME>" in employee and "<AMOUNT>600.00</AMOUNT>" in employee
    detail = setup.client.get(f"/vouchers/{reply.json()['voucher_id']}", headers=setup.headers).json()["payroll_entries"]
    assert [(p["pay_head_name"], p["amount"], p["is_deduction"]) for p in detail] == [("Basic Salary", 5000.0, False), ("PF Deduction", 600.0, True)]


def test_cost_centre_allocations_of_an_ordinary_voucher_are_not_read_as_pay_heads(setup):
    from app.models.tally_core import TrnPayHead
    from app.services.tally_xml_importer import import_tally_xml
    from tests.conftest import run
    # Tally writes a cost centre allocation with the same lists a Payroll voucher uses for its pay heads
    xml = ('<ENVELOPE><BODY><DATA><COLLECTION><VOUCHER VCHTYPE="Receipt"><DATE>20260301</DATE><GUID>guid-cc</GUID><MASTERID> 91</MASTERID>'
           '<ALTERID> 9</ALTERID><VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME><VOUCHERNUMBER>9</VOUCHERNUMBER>'
           '<CATEGORYENTRY.LIST><CATEGORY>Primary Cost Category</CATEGORY><EMPLOYEEENTRIES.LIST><EMPLOYEENAME>Branch A</EMPLOYEENAME>'
           '<PAYHEADALLOCATIONS.LIST><PAYHEADNAME>Cash</PAYHEADNAME><AMOUNT>100.00</AMOUNT></PAYHEADALLOCATIONS.LIST>'
           '</EMPLOYEEENTRIES.LIST></CATEGORYENTRY.LIST></VOUCHER></COLLECTION></DATA></BODY></ENVELOPE>')

    async def go():
        async with setup.harness.Session() as db:
            await import_tally_xml(xml, db, 1, override_company_name="Alpha")
            await db.commit()
    run(go())

    assert setup.harness.query(select(TrnVoucher.voucher_number)) == [("9",)]
    assert setup.harness.query(select(TrnPayHead)) == []


def test_a_sales_bill_is_named_after_the_voucher_number_unless_the_setting_is_off(setup):
    body = setup.sales_body()
    body["reference_number"] = "PO-9"

    first = setup.client.post("/vouchers", headers=setup.headers, json=body).json()

    assert setup.harness.scalar(select(TrnBill.bill_reference).where(TrnBill.voucher_id == first["voucher_id"])) == first["voucher_number"]
    assert f"<NAME>{first['voucher_number']}</NAME>" in setup.tally.of_type("Sales")[0]["xml"]

    setup.harness.add(MstVoucherConfiguration(company_id=setup.company_id, voucher_type_id=body["voucher_type_id"], use_vch_no_as_bill_ref=False))
    second = setup.client.post("/vouchers", headers=setup.headers, json=body).json()

    assert setup.harness.scalar(select(TrnBill.bill_reference).where(TrnBill.voucher_id == second["voucher_id"])) == "PO-9"
    assert "<NAME>PO-9</NAME>" in setup.tally.of_type("Sales")[1]["xml"]


def test_an_edit_keeps_the_bill_name_the_voucher_already_has(setup):
    body = setup.sales_body()
    body["reference_number"] = "PO-9"
    by_number = setup.client.post("/vouchers", headers=setup.headers, json=body).json()
    setup.harness.add(MstVoucherConfiguration(company_id=setup.company_id, voucher_type_id=body["voucher_type_id"], use_vch_no_as_bill_ref=False))
    by_reference = setup.client.post("/vouchers", headers=setup.headers, json=body).json()
    body["reference_number"] = "PO-10"

    for made in (by_number, by_reference):
        assert setup.client.put(f"/vouchers/{made['voucher_id']}", headers=setup.headers, json=body).status_code == 200

    bill = lambda made: setup.harness.scalar(select(TrnBill.bill_reference).where(TrnBill.voucher_id == made["voucher_id"]))
    # Named after the voucher number: stays, even though the setting is now off. Named after the reference: follows it.
    assert (bill(by_number), bill(by_reference)) == (by_number["voucher_number"], "PO-10")
    assert f"<NAME>{by_number['voucher_number']}</NAME>" in setup.tally.vouchers[by_number["tally_master_id"]]["xml"]
    assert "<NAME>PO-10</NAME>" in setup.tally.vouchers[by_reference["tally_master_id"]]["xml"]
