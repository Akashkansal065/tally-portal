"""The Desktop Sync Agent names its Tally company by GUID on every call; the server uses that company, not
the one the agent's account has active in the app."""
from sqlalchemy import select

import app.models.portal_core as P
from app.routers import auth, sync
from app.services.tally_xml_importer import import_tally_xml
from tests.conftest import bearer, login, run

GUID_A = "guid-aaaa"
GUID_B = "guid-bbbb"


def seed(harness):
    alpha = harness.company("Alpha")
    beta = harness.company("Beta")
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == alpha.company_id).values(tally_guid=GUID_A))
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == beta.company_id).values(tally_guid=GUID_B))
    admin = harness.user(alpha, harness.role("Admin"), "owner")  # active company: Alpha
    harness.add(P.UserCompanyAccess(user_id=admin.user_id, company_id=alpha.company_id),
                P.UserCompanyAccess(user_id=admin.user_id, company_id=beta.company_id))
    harness.add(
        P.SyncQueue(sync_id=1, company_id=alpha.company_id, record_type="Voucher", record_id=1, action="Create", is_processed=False),
        P.SyncQueue(sync_id=2, company_id=beta.company_id, record_type="Voucher", record_id=2, action="Create", is_processed=False),
    )
    client = harness.app(auth.router, sync.router)
    return client, bearer(login(client, admin.email)), admin, alpha, beta


def processed(harness):
    return dict(harness.query(select(P.SyncQueue.sync_id, P.SyncQueue.is_processed)))


def test_named_company_is_used_instead_of_the_active_one(harness):
    client, headers, *_ = seed(harness)

    res = client.post("/sync/acknowledge", json=[1, 2], headers={**headers, "X-Tally-Company-GUID": GUID_B})

    assert res.status_code == 200
    assert processed(harness) == {1: False, 2: True}


def test_naming_a_company_does_not_change_the_active_one(harness):
    client, headers, admin, alpha, _ = seed(harness)

    client.get("/sync/last-alter-id", headers={**headers, "X-Tally-Company-GUID": GUID_B})

    assert harness.scalar(select(P.User.company_id).where(P.User.user_id == admin.user_id)) == alpha.company_id


def test_unlinked_guid_is_refused(harness):
    client, headers, *_ = seed(harness)

    for method, path, body in (("get", "/sync/outbound-queue", None), ("get", "/sync/last-alter-id", None),
                               ("post", "/sync/acknowledge", [1, 2]), ("post", "/sync/voucher-identities", [])):
        kwargs = {"headers": {**headers, "X-Tally-Company-GUID": "guid-unknown"}}
        if body is not None:
            kwargs["json"] = body
        res = getattr(client, method)(path, **kwargs)
        assert res.status_code == 409, path
        assert res.headers["X-Sync-Reason"] == "company_not_linked"
    assert processed(harness) == {1: False, 2: False}


def test_agent_without_the_header_still_gets_the_active_company(harness):
    client, headers, *_ = seed(harness)

    assert client.post("/sync/acknowledge", json=[1, 2], headers=headers).status_code == 200

    assert processed(harness) == {1: True, 2: False}


COMPANY_EXPORT = f"""<ENVELOPE><BODY><DATA><COLLECTION>
  <COMPANY NAME="Alpha"><GUID>{GUID_A}</GUID><STATENAME>Delhi</STATENAME></COMPANY>
  <COMPANY NAME="Beta Renamed"><GUID>{GUID_B}</GUID><STATENAME>Kerala</STATENAME></COMPANY>
</COLLECTION></DATA></BODY></ENVELOPE>"""


def import_xml(harness, user_id, xml, **kwargs):
    async def go():
        async with harness.Session() as db:
            return await import_tally_xml(xml, db, user_id, **kwargs)
    return run(go())


def test_import_takes_the_named_company_from_an_export_listing_several(harness):
    _, _, admin, alpha, beta = seed(harness)

    result = import_xml(harness, admin.user_id, COMPANY_EXPORT, override_company_name="Beta", company_guid=GUID_B)

    assert result["company_id"] == beta.company_id
    rows = {cid: (name, state) for cid, name, state in harness.query(select(P.Company.company_id, P.Company.name, P.Company.state))}
    assert rows[beta.company_id] == ("Beta Renamed", "Kerala")
    assert rows[alpha.company_id] == ("Alpha", None)


def test_import_refuses_a_same_name_company_linked_to_another_guid(harness):
    _, _, admin, alpha, _ = seed(harness)

    result = import_xml(harness, admin.user_id, "<ENVELOPE><BODY><DATA><COLLECTION/></DATA></BODY></ENVELOPE>",
                        override_company_name="Alpha", company_guid="guid-other-alpha")

    assert result["status"] == "error"
    assert "different Tally company" in result["message"]
    assert harness.scalar(select(P.Company.tally_guid).where(P.Company.company_id == alpha.company_id)) == GUID_A
