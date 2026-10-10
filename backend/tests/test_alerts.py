"""Alerts to a business's admins: a company no PC syncs any more, a company that has not synced for a day, and a
request from outside the business that was refused. Each reaches that business's admins only, once a day."""
from datetime import timedelta

import pytest
from sqlalchemy import select

import app.models.portal_core as P
from app.core.datetime_utils import get_ist_now
from app.routers import agent, auth, sync, team
from app.services import alerts
from app.services import notifications as service
from tests.conftest import PASSWORD, bearer, login, run
from tests.test_agent_onboarding import ALPHA, PC_ONE, PC_TWO, SIGNUP, device_headers, mail, sign_up  # noqa: F401


@pytest.fixture(autouse=True)
def pushes(monkeypatch):
    sent = []

    async def fake_deliver(payloads, session_factory=None):
        sent.extend(payloads)
        return len(payloads)

    monkeypatch.setattr(service, "deliver_push", fake_deliver)
    monkeypatch.setattr(service, "schedule", lambda coro: coro.close())
    return sent


@pytest.fixture
def client(harness):
    return harness.app(auth.router, agent.router, sync.router, team.router, team.public_router)


@pytest.fixture
def two_customers(harness, client, mail):  # noqa: F811
    asha = sign_up(client, mail)
    ravi = sign_up(client, mail, signup={**SIGNUP, "email": "ravi@example.com", "business_name": "Ravi Traders"},
                   device=PC_TWO, company={"tally_guid": "guid-ravi", "name": "Ravi Traders"})
    return asha, ravi


def notes(harness, type_=None):
    rows = harness.query(select(P.Notification.user_id, P.Notification.type, P.Notification.company_id, P.Notification.title))
    return [r for r in rows if type_ is None or r[1] == type_]


def call(harness, fn, *args, **kwargs):
    async def go():
        async with harness.Session() as db:
            return await fn(db, *args, **kwargs)
    return run(go())


def test_admin_notifications_stay_inside_the_companys_business(harness, two_customers):
    asha, ravi = two_customers
    call(harness, service.notify_admins, asha["company"]["company_id"], "order_created", "New order", "sales placed order #7",
         auto_commit=True)

    assert [n[0] for n in notes(harness)] == [asha["user"]["user_id"]]      # never the other customer's admin


def test_unlinking_a_company_tells_its_admins_once(harness, client, two_customers):
    asha, ravi = two_customers
    token = asha["device_token"]

    assert client.post("/agent/companies/unlink", json={"tally_guid": ALPHA["tally_guid"]}, headers=device_headers(token)).json()["unlinked"]
    told = notes(harness, "sync_unlinked")
    assert [(n[0], n[2]) for n in told] == [(asha["user"]["user_id"], asha["company"]["company_id"])]
    assert "no longer synced" in told[0][3]

    client.post("/agent/companies/link", json=ALPHA, headers=device_headers(token))
    client.post("/agent/companies/unlink", json={"tally_guid": ALPHA["tally_guid"]}, headers=device_headers(token))
    assert len(notes(harness, "sync_unlinked")) == 1                         # the same day: not again


def test_moving_a_company_to_another_pc_is_not_an_alert(harness, client, two_customers):
    asha, _ = two_customers
    second = client.post("/agent/signin", json={"email": "asha@example.com", "password": PASSWORD,
                                                "machine_id": "machine-three-0003", "device_name": "Shop PC"}).json()
    moved = client.post("/agent/companies/link", json={**ALPHA, "take_over": True}, headers=device_headers(second["device_token"]))
    assert moved.status_code == 200
    assert notes(harness, "sync_unlinked") == []


def test_signing_a_pc_out_tells_the_other_admins_its_companies_stopped(harness, client, two_customers):
    asha, _ = two_customers
    admin_role = harness.scalar(select(P.Role.role_id).where(P.Role.account_id == asha["account"]["account_id"], P.Role.name == "Admin"))
    partner = harness.user(type("C", (), {"company_id": asha["company"]["company_id"]})(), type("R", (), {"role_id": admin_role})(), "partner")
    harness.execute(P.User.__table__.update().where(P.User.user_id == partner.user_id).values(account_id=asha["account"]["account_id"]))
    owner = bearer(login(client, "asha@example.com"))

    assert client.post(f"/admin/agent-devices/{asha['device']['device_id']}/revoke", headers=owner).status_code == 200

    assert [n[0] for n in notes(harness, "sync_unlinked")] == [partner.user_id]   # not the admin who did it


def test_a_company_not_synced_for_a_day_is_reported_once_a_day(harness, client, two_customers):
    asha, ravi = two_customers
    now = get_ist_now()
    harness.add(P.CompanySyncState(company_id=asha["company"]["company_id"], state="closed", last_success_at=now - timedelta(days=2)),
                P.CompanySyncState(company_id=ravi["company"]["company_id"], state="live", last_success_at=now - timedelta(minutes=5)))

    assert call(harness, alerts.alert_stale_companies) == 1
    told = notes(harness, "sync_stale")
    assert [(n[0], n[2]) for n in told] == [(asha["user"]["user_id"], asha["company"]["company_id"])]
    message = harness.scalar(select(P.Notification.message).where(P.Notification.type == "sync_stale"))
    assert "not open in Tally" in message
    assert call(harness, alerts.alert_stale_companies) == 0                  # already said today


def test_reaching_for_another_customers_company_alerts_that_customer_only(harness, client, two_customers):
    asha, ravi = two_customers
    intruder = bearer(login(client, "ravi@example.com"))

    me = client.get("/auth/me", headers={**intruder, "X-Company-ID": str(asha["company"]["company_id"])}).json()
    assert me["company_id"] == ravi["company"]["company_id"]                 # refused: they stay in their own
    told = notes(harness, "account_refused")
    assert [(n[0], n[2]) for n in told] == [(asha["user"]["user_id"], asha["company"]["company_id"])]
    message = harness.scalar(select(P.Notification.message).where(P.Notification.type == "account_refused"))
    assert "ravi" not in message.lower() and "Ravi Traders" not in message   # never says who

    client.get("/auth/me", headers={**intruder, "X-Company-ID": str(asha["company"]["company_id"])})
    refused = client.post(f"/admin/agent-devices/{asha['device']['device_id']}/revoke", headers=intruder)
    assert refused.status_code == 404
    assert len(notes(harness, "account_refused")) == 1                       # one a day, however often they try


def test_a_company_of_your_own_business_you_cannot_open_is_not_an_alert(harness, client, two_customers):
    asha, _ = two_customers
    beta = client.post("/agent/companies/link", json={"tally_guid": "guid-beta", "name": "Beta Corp"},
                       headers=device_headers(asha["device_token"])).json()
    sales_role = harness.scalar(select(P.Role.role_id).where(P.Role.account_id == asha["account"]["account_id"], P.Role.name == "Sales"))
    seller = harness.user(type("C", (), {"company_id": asha["company"]["company_id"]})(), type("R", (), {"role_id": sales_role})(), "seller")
    harness.execute(P.User.__table__.update().where(P.User.user_id == seller.user_id).values(account_id=asha["account"]["account_id"]))

    client.get("/auth/me", headers={**bearer(login(client, seller.email)), "X-Company-ID": str(beta["company_id"])})

    assert notes(harness, "account_refused") == []
