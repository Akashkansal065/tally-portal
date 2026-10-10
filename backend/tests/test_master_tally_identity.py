"""A master created or renamed here carries Tally's own GUID and master id once it has reached Tally, and a
master renamed in Tally is followed by its GUID instead of arriving as a second record."""
import re

from sqlalchemy import select

from app.core.config import settings
from app.models.tally_core import MstGroup, MstLedger
from app.routers import auth, ledgers, sync
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import bearer, login, run


class FakeTally:
    """Accepts every master import and answers object exports with the identity it gave the master."""

    def __init__(self):
        self.masters = {}

    def __call__(self, url, xml, timeout=5):
        if "<TALLYREQUEST>Export</TALLYREQUEST>" in xml:
            name = re.search(r'<ID TYPE="Name">([^<]*)</ID>', xml).group(1)
            if name not in self.masters:
                return "<ENVELOPE><ERRORMSG>Could not find it</ERRORMSG></ENVELOPE>"
            master_id = self.masters[name]
            return (f'<ENVELOPE><BODY><DATA><LEDGER NAME="{name}"><GUID>tally-guid-{master_id:08x}</GUID>'
                    f"<MASTERID> {master_id}</MASTERID><ALTERID> 7</ALTERID></LEDGER></DATA></BODY></ENVELOPE>")
        old = re.search(r'<LEDGER NAME="([^"]*)"', xml)
        new = re.search(r"<NAME>([^<]*)</NAME>", xml)
        if old and old.group(1) in self.masters and new:
            self.masters[new.group(1)] = self.masters.pop(old.group(1))
        elif new:
            self.masters.setdefault(new.group(1), 500 + len(self.masters))
        return "<ENVELOPE><BODY><DATA><IMPORTRESULT><CREATED>1</CREATED><ERRORS>0</ERRORS></IMPORTRESULT></DATA></BODY></ENVELOPE>"


def test_a_ledger_created_here_takes_tallys_identity_and_keeps_it_through_a_rename(harness, monkeypatch):
    tally = FakeTally()
    monkeypatch.setattr(settings, "TALLY_URL", "http://tally.test:9000")
    monkeypatch.setattr(sync, "_post_to_tally_sync", tally)
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    group = harness.add(MstGroup(company_id=company.company_id, name="Sundry Debtors", nature="Asset"))
    client = harness.app(auth.router, ledgers.router)
    headers = bearer(login(client, admin.email))

    created = client.post("/ledgers", headers=headers, json={"name": "Gupta Stores", "group_id": group.group_id})
    assert created.status_code == 200, created.text
    assert (created.json()["tally_guid"], created.json()["tally_master_id"]) == ("tally-guid-000001f4", 500)

    renamed = client.put(f"/ledgers/{created.json()['ledger_id']}", headers=headers, json={"name": "Gupta Stores Pvt Ltd", "group_id": group.group_id})
    assert renamed.status_code == 200, renamed.text
    assert harness.query(select(MstLedger.name, MstLedger.tally_guid, MstLedger.tally_master_id)) == [("Gupta Stores Pvt Ltd", "tally-guid-000001f4", 500)]


def test_a_ledger_renamed_in_tally_is_followed_by_its_guid(harness):
    company = harness.company("Alpha")
    admin = harness.user(company, harness.role("Admin"), "owner")
    group = harness.add(MstGroup(company_id=company.company_id, name="Sundry Debtors", nature="Asset"))
    ledger = harness.add(MstLedger(company_id=company.company_id, name="Old Name", group_id=group.group_id, tally_guid="guid-1", tally_master_id=11))
    xml = ("<ENVELOPE><BODY><DATA><COLLECTION><LEDGER NAME=\"New Name\"><GUID>guid-1</GUID><MASTERID> 11</MASTERID><ALTERID> 20</ALTERID>"
           "<PARENT>Sundry Debtors</PARENT></LEDGER></COLLECTION></DATA></BODY></ENVELOPE>")

    async def go():
        async with harness.Session() as db:
            await import_tally_xml(xml, db, admin.user_id, override_company_name="Alpha")
            await db.commit()
    run(go())

    assert harness.query(select(MstLedger.ledger_id, MstLedger.name, MstLedger.tally_guid)) == [(ledger.ledger_id, "New Name", "guid-1")]
