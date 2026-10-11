"""A company profile edited in the app goes to Tally as the values that changed, once, and the next import
says whether Tally took them."""
from datetime import date

import pytest
from sqlalchemy import select

import app.models.portal_core as P
from app.routers import auth, companies, sync
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import bearer, login, run


@pytest.fixture
def alpha(harness):
    client = harness.app(auth.router, companies.router, sync.router)
    company = harness.add(P.Company(name="Alpha", state="Delhi", pincode="110001", tally_guid="guid-alpha",
                                    books_begin_date=date(2025, 4, 1)))
    user = harness.user(company, harness.role("Admin"), "owner")
    return client, company, user, bearer(login(client, user.email))


def company_rows(harness):
    return [r[0] for r in harness.query(select(P.SyncQueue).where(P.SyncQueue.record_type == "Company")
                                        .order_by(P.SyncQueue.sync_id))]


def queued(client, headers):
    return [t for t in client.get("/sync/outbound-queue", headers=headers).json() if t["record_type"] == "Company"]


def import_from_tally(harness, user, company, inner):
    xml = (f'<ENVELOPE><BODY><DATA><COLLECTION><COMPANY NAME="Alpha"><GUID>guid-alpha</GUID>{inner}</COMPANY>'
           "</COLLECTION></DATA></BODY></ENVELOPE>")

    async def go():
        async with harness.Session() as db:
            return await import_tally_xml(xml, db, user.user_id, target_company_id=company.company_id)
    return run(go())


def test_only_the_changed_filled_in_values_are_sent(harness, alpha):
    client, company, _, headers = alpha
    form = {"name": "Alpha", "state": "Delhi", "pincode": "110002", "gstin": "07ABCDE1234F1Z5", "email": "",
            "books_begin_date": "2025-04-01", "upi_id": "alpha@upi"}
    assert client.put(f"/companies/{company.company_id}", json=form, headers=headers).status_code == 200

    (task,) = queued(client, headers)
    xml = task["xml_payload"]
    assert '<COMPANY NAME="Alpha" ACTION="Alter">' in xml and "<SVCURRENTCOMPANY>Alpha</SVCURRENTCOMPANY>" in xml
    assert "<PINCODE>110002</PINCODE>" in xml and "<GSTREGISTRATIONNUMBER>07ABCDE1234F1Z5</GSTREGISTRATIONNUMBER>" in xml
    # Unchanged, blank, app-only and never-sent values stay out
    for absent in ("STATENAME", "EMAIL", "BOOKSFROM", "STARTINGFROM", "<NAME>", "upi"):
        assert absent not in xml
    assert task["company_guid"] == "guid-alpha"


def test_saving_twice_sends_once_and_keeps_both_edits(harness, alpha):
    client, company, _, headers = alpha
    client.put(f"/companies/{company.company_id}", json={"pincode": "110002"}, headers=headers)
    client.put(f"/companies/{company.company_id}", json={"pincode": "110002"}, headers=headers)   # same save again
    client.put(f"/companies/{company.company_id}", json={"name": "Alpha Traders", "email": "a@alpha.in"}, headers=headers)

    (task,) = queued(client, headers)
    assert "<PINCODE>110002</PINCODE>" in task["xml_payload"] and "<EMAIL>a@alpha.in</EMAIL>" in task["xml_payload"]
    # Tally still knows the company by the name it had before it was renamed here
    assert '<COMPANY NAME="Alpha" ACTION="Alter">' in task["xml_payload"]
    assert [bool(r.is_processed) for r in company_rows(harness)] == [True, False]


def test_an_edit_of_app_only_values_queues_nothing(harness, alpha):
    client, company, _, headers = alpha
    client.put(f"/companies/{company.company_id}", json={"state": "Delhi", "upi_id": "alpha@upi"}, headers=headers)
    assert company_rows(harness) == []


def test_address_lines_go_together_and_come_back_the_same(harness, alpha):
    client, company, user, headers = alpha
    client.put(f"/companies/{company.company_id}", json={"address_line1": "12 MG Road", "address_line2": "Indiranagar"}, headers=headers)
    client.put(f"/companies/{company.company_id}", json={"address_line1": "14 MG Road"}, headers=headers)
    (task,) = queued(client, headers)
    assert "<ADDRESS>14 MG Road</ADDRESS><ADDRESS>Indiranagar</ADDRESS>" in task["xml_payload"]

    import_from_tally(harness, user, company, '<ADDRESS.LIST TYPE="String"><ADDRESS>14 MG Road</ADDRESS><ADDRESS>Indiranagar</ADDRESS></ADDRESS.LIST>')
    row = harness.scalar(select(P.Company).where(P.Company.company_id == company.company_id))
    assert (row.address_line1, row.address_line2) == ("14 MG Road", "Indiranagar")


def test_the_next_import_confirms_what_tally_took(harness, alpha):
    client, company, user, headers = alpha
    client.put(f"/companies/{company.company_id}", json={"pincode": "110002", "mobile": "98100 00000"}, headers=headers)
    (task,) = queued(client, headers)
    client.post("/sync/acknowledge", json=[task["sync_id"]], headers=headers)

    import_from_tally(harness, user, company, "<PINCODE>110002</PINCODE><MOBILENUMBERS.LIST><MOBILENUMBERS>9810000000</MOBILENUMBERS></MOBILENUMBERS.LIST>")
    (row,) = company_rows(harness)
    assert (row.status, row.snapshot_data["verified"]) == ("SUCCESS", True)


def test_an_edit_tally_ignored_is_marked_failed_and_tallys_value_comes_back(harness, alpha):
    client, company, user, headers = alpha
    client.put(f"/companies/{company.company_id}", json={"pincode": "110002", "gstin": "07ABCDE1234F1Z5"}, headers=headers)
    (task,) = queued(client, headers)
    client.post("/sync/acknowledge", json=[task["sync_id"]], headers=headers)   # the agent took "ignored" for success

    import_from_tally(harness, user, company, "<PINCODE>110001</PINCODE>")      # may be an export from before the push
    assert company_rows(harness)[0].status == "SUCCESS"
    import_from_tally(harness, user, company, "<PINCODE>110001</PINCODE>")
    (row,) = company_rows(harness)
    assert row.status == "FAILED" and "pincode" in row.error_message and "gstin" in row.error_message
    assert harness.scalar(select(P.Company.pincode).where(P.Company.company_id == company.company_id)) == "110001"
    import_from_tally(harness, user, company, "<PINCODE>110001</PINCODE>")      # judged once
    assert company_rows(harness)[0].status == "FAILED"
