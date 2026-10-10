"""Companies and users belong to a customer account. An admin reaches every company of their own account and
none of another's, whichever way they ask for it."""
from sqlalchemy import select

import app.models.portal_core as P
from app.routers import auth, sync
from tests.conftest import bearer, login


def in_account(harness, account, company=None, user=None):
    if company is not None:
        harness.execute(P.Company.__table__.update().where(P.Company.company_id == company.company_id)
                        .values(account_id=account.account_id))
    if user is not None:
        harness.execute(P.User.__table__.update().where(P.User.user_id == user.user_id)
                        .values(account_id=account.account_id))


def seed(harness):
    """Two customers, each with an admin; customer one has two companies. One company from before accounts."""
    one, two = harness.add(P.Account(name="One"), P.Account(name="Two"))
    role = harness.role("Admin")
    a1, a2, b1, legacy = (harness.company(n) for n in ("A1", "A2", "B1", "Legacy"))
    admin_one = harness.user(a1, role, "one")
    admin_two = harness.user(b1, role, "two")
    admin_legacy = harness.user(legacy, role, "legacy")
    for company in (a1, a2):
        in_account(harness, one, company=company)
    in_account(harness, one, user=admin_one)
    in_account(harness, two, company=b1, user=admin_two)
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == b1.company_id).values(tally_guid="guid-b1"))
    client = harness.app(auth.router, sync.router)
    return client, {"one": admin_one, "two": admin_two, "legacy": admin_legacy}, {"a1": a1, "a2": a2, "b1": b1, "legacy": legacy}


def companies_of(client, user):
    headers = bearer(login(client, user.email))
    return {c["name"] for c in client.get("/auth/me/companies", headers=headers).json()}


def test_admin_lists_only_their_own_accounts_companies(harness):
    client, admins, _ = seed(harness)

    assert companies_of(client, admins["one"]) == {"A1", "A2"}
    assert companies_of(client, admins["two"]) == {"B1"}
    assert companies_of(client, admins["legacy"]) == {"Legacy"}


def test_admin_cannot_switch_to_another_accounts_company(harness):
    client, admins, companies = seed(harness)
    headers = bearer(login(client, admins["one"].email))

    refused = client.put("/auth/me/active-company", json={"company_id": companies["b1"].company_id}, headers=headers)
    allowed = client.put("/auth/me/active-company", json={"company_id": companies["a2"].company_id}, headers=headers)

    assert refused.status_code == 404
    assert allowed.status_code == 200
    assert harness.scalar(select(P.User.company_id).where(P.User.user_id == admins["one"].user_id)) == companies["a2"].company_id


def test_company_header_for_another_account_is_ignored(harness):
    client, admins, companies = seed(harness)
    headers = bearer(login(client, admins["one"].email))

    other = client.get("/auth/me", headers={**headers, "X-Company-ID": str(companies["b1"].company_id)}).json()
    own = client.get("/auth/me", headers={**headers, "X-Company-ID": str(companies["a2"].company_id)}).json()

    assert other["company_id"] == companies["a1"].company_id
    assert own["company_id"] == companies["a2"].company_id


def test_sync_agent_cannot_name_another_accounts_tally_company(harness):
    client, admins, _ = seed(harness)
    headers = bearer(login(client, admins["one"].email))

    res = client.get("/sync/last-alter-id", headers={**headers, "X-Tally-Company-GUID": "guid-b1"})

    assert res.status_code == 409 and res.headers["X-Sync-Reason"] == "company_not_linked"


def test_registering_a_customer_creates_its_own_account(harness, monkeypatch):
    # The default groups and voucher types are seeded with MySQL-only SQL
    monkeypatch.setattr(auth, "seed_company_defaults", lambda session, company_id, commit=True: None)
    client, admins, _ = seed(harness)
    headers = bearer(login(client, admins["legacy"].email))

    res = client.post("/auth/register", headers=headers, json={
        "company_name": "Gamma", "username": "gamma", "email": "gamma@example.com", "password": "pw-1234567",
        "financial_year_start": "2026-04-01", "books_begin_date": "2026-04-01"})
    assert res.status_code in (200, 201), res.text

    account_id = harness.scalar(select(P.Company.account_id).where(P.Company.name == "Gamma"))
    assert account_id is not None
    assert harness.scalar(select(P.User.account_id).where(P.User.email == "gamma@example.com")) == account_id
    assert companies_of(client, admins["legacy"]) == {"Legacy"}
