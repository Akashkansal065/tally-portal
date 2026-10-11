"""Companies and users belong to a customer account. An admin reaches every company of their own account and
none of another's, whichever way they ask for it."""
from sqlalchemy import func, select

import app.models.portal_core as P
from app.routers import admin, auth, sync
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


def test_registration_and_company_creation_from_the_web_are_gone(harness):
    from app.routers import companies as companies_router
    client, admins, _ = seed(harness)
    client = harness.app(auth.router, companies_router.router)
    headers = bearer(login(client, admins["one"].email))

    for path in ("/auth/register", "/auth/register-company", "/companies"):
        res = client.post(path, headers=headers, json={"company_name": "Gamma", "name": "Gamma"})
        assert res.status_code == 410, path
        assert ("Desktop Sync Agent" if path == "/companies" else "mobile number") in res.json()["detail"]
    assert client.get("/auth/bootstrap-status").json() == {"need_bootstrap": False}
    assert harness.scalar(select(func.count()).select_from(P.Company)) == 4


# ── Roles belong to an account ──

def test_each_account_sees_and_changes_only_its_own_roles(harness):
    from app.core.account_roles import create_default_roles
    from app.routers import admin as admin_router
    from tests.conftest import run
    client, admins, _ = seed(harness)
    client = harness.app(auth.router, admin_router.router)
    accounts = {name: harness.scalar(select(P.User.account_id).where(P.User.user_id == admins[name].user_id)) for name in ("one", "two")}
    harness.add(P.Module(code="orders", name="Orders"), P.Module(code="ledgers", name="Ledgers"))

    async def make():
        async with harness.Session() as db:
            for account_id in accounts.values():
                await create_default_roles(db, account_id)
                await create_default_roles(db, account_id)      # again: nothing is duplicated
            await db.commit()
    run(make())
    one, two = (bearer(login(client, admins[name].email)) for name in ("one", "two"))

    names = lambda headers: sorted(r["name"] for r in client.get("/admin/roles", headers=headers).json())  # noqa: E731
    assert names(one) == ["Admin", "Sales"] and names(two) == ["Admin", "Sales"]
    their_sales = harness.scalar(select(P.Role.role_id).where(P.Role.name == "Sales", P.Role.account_id == accounts["two"]))

    # Both accounts can have a role with the same name; neither can touch the other's
    assert client.post("/admin/roles", headers=one, json={"name": "Accountant"}).status_code == 200
    assert client.post("/admin/roles", headers=two, json={"name": "Accountant"}).status_code == 200
    assert client.put(f"/admin/roles/{their_sales}", headers=one, json={"name": "Renamed"}).status_code == 404
    assert client.delete(f"/admin/roles/{their_sales}", headers=one).status_code == 404
    assert harness.scalar(select(P.Role.name).where(P.Role.role_id == their_sales)) == "Sales"
    # A new account's Admin can do everything, its Sales only the field work
    perms = {(role, module): can_create for role, module, can_create in harness.query(
        select(P.Role.name, P.Module.code, P.Permission.can_create)
        .join(P.Permission, P.Permission.role_id == P.Role.role_id).join(P.Module, P.Module.module_id == P.Permission.module_id)
        .where(P.Role.account_id == accounts["one"], P.Role.name.in_(["Admin", "Sales"])))}
    assert perms == {("Admin", "orders"): True, ("Admin", "ledgers"): True, ("Sales", "orders"): True}


# ── After enforcement ──

def test_with_accounts_enforced_a_user_without_an_account_reaches_only_their_own_company(harness, monkeypatch):
    from app.core.config import settings
    client, admins, companies = seed(harness)
    stray = harness.company("Stray")           # another company that was never given an account
    headers = bearer(login(client, admins["legacy"].email))
    ask = lambda: client.get("/auth/me", headers={**headers, "X-Company-ID": str(stray.company_id)}).json()["company_id"]  # noqa: E731

    assert ask() == stray.company_id           # before: account-less rows are one shared group

    monkeypatch.setattr(settings, "ACCOUNTS_ENFORCED", True)
    from app.core import permissions
    permissions._auth_cache.clear()
    assert ask() == companies["legacy"].company_id


def test_a_sync_agent_on_a_persons_login_can_be_refused(harness, monkeypatch):
    from app.core.config import settings
    client, admins, _ = seed(harness)
    agent_headers = {**bearer(login(client, admins["two"].email)), "X-Client-Type": "sync-agent", "X-Tally-Company-GUID": "guid-b1"}
    assert client.get("/sync/last-alter-id", headers=agent_headers).status_code == 200

    monkeypatch.setattr(settings, "REQUIRE_AGENT_DEVICE_SIGNIN", True)

    refused = client.get("/sync/last-alter-id", headers=agent_headers)
    assert refused.status_code == 426 and refused.headers["X-Sync-Reason"] == "device_signin_required"
    # A person in the browser is not a sync agent and is unaffected
    assert client.get("/sync/last-alter-id", headers=bearer(login(client, admins["two"].email))).status_code == 200


def test_each_account_has_its_own_settings(harness):
    from app.routers import admin as admin_router, report_insights
    client, admins, _ = seed(harness)
    client = harness.app(auth.router, admin_router.router, report_insights.router)
    one, two = (bearer(login(client, admins[name].email)) for name in ("one", "two"))
    path = next(r.path for r in report_insights.router.routes if r.path.endswith("/settings") and "PUT" in r.methods)

    assert client.put(path, headers=one, json={"default_credit_days": 45}).status_code == 200

    assert client.get(path, headers=one).json()["default_credit_days"] == 45
    assert client.get(path, headers=two).json()["default_credit_days"] == 30      # the default, untouched


def test_the_servers_own_tally_is_used_for_one_company_only(harness, monkeypatch):
    """The server's own Tally belongs to one customer. Anyone can sign up, so a later account must never be sent
    to it: not by default, and not by giving a company of theirs the same Tally GUID."""
    from app.core import tally_target
    from app.core.config import settings
    from tests.conftest import run
    _, _, companies = seed(harness)       # account One: A1, A2 (first account); account Two: B1 (guid-b1); Legacy
    url = "http://tally.test:9000"
    monkeypatch.setattr(settings, "TALLY_URL", url)
    monkeypatch.setattr(settings, "TALLY_URL_COMPANY_ID", None)

    def url_for(company):
        async def go():
            async with harness.Session() as db:
                await tally_target.note_request_company(db, company.company_id)
                return tally_target.current_tally_url()
        tally_target.forget_direct_companies()
        return run(go())

    # Not pinned: the server's first customer and its companies from before accounts; a later account never
    assert [url_for(companies[c]) for c in ("a1", "a2", "legacy")] == [url, url, url]
    assert url_for(companies["b1"]) is None
    monkeypatch.setattr(settings, "ACCOUNTS_ENFORCED", True)
    assert url_for(companies["legacy"]) is None          # once enforced, a company of no account belongs to nobody
    monkeypatch.setattr(settings, "ACCOUNTS_ENFORCED", False)

    # Pinned by GUID
    monkeypatch.setattr(settings, "TALLY_URL_COMPANY_GUID", "guid-b1")
    assert url_for(companies["b1"]) == url
    assert url_for(companies["a1"]) is None              # another customer's company waits for its own agent

    # Someone signs up and gives a company of theirs the same GUID: the company that had it first keeps the Tally
    copycat = harness.add(P.Account(name="Copycat"))
    copy = harness.company("Copy")
    in_account(harness, copycat, company=copy)
    harness.execute(P.Company.__table__.update().where(P.Company.company_id == copy.company_id).values(tally_guid="guid-b1"))
    assert url_for(copy) is None
    assert url_for(companies["b1"]) == url

    # Pinned by id: wins over the GUID, and cannot be copied
    monkeypatch.setattr(settings, "TALLY_URL_COMPANY_ID", companies["a2"].company_id)
    assert url_for(companies["a2"]) == url
    assert url_for(companies["b1"]) is None


def test_no_company_recorded_means_no_direct_tally(monkeypatch):
    """A background job that names no company is never sent to the server's Tally."""
    from app.core import tally_target
    from app.core.config import settings
    monkeypatch.setattr(settings, "TALLY_URL", "http://tally.test:9000")
    assert tally_target.current_tally_url() is None


def roles_world(harness):
    """Two accounts, each with its own Admin role and admin, and one permission row on each role."""
    one, two = harness.add(P.Account(name="One"), P.Account(name="Two"))
    module = harness.add(P.Module(code="vouchers", name="Vouchers"))
    role_one = harness.add(P.Role(name="Admin", account_id=one.account_id))
    role_two = harness.add(P.Role(name="Admin", account_id=two.account_id))
    harness.add(P.Permission(role_id=role_one.role_id, module_id=module.module_id, can_read=True, can_delete=True),
                P.Permission(role_id=role_two.role_id, module_id=module.module_id, can_read=True, can_delete=True))
    a1, b1 = harness.company("A1"), harness.company("B1")
    admin_one, admin_two = harness.user(a1, role_one, "one"), harness.user(b1, role_two, "two")
    in_account(harness, one, company=a1, user=admin_one)
    in_account(harness, two, company=b1, user=admin_two)
    client = harness.app(auth.router, admin.router)
    return client, module, {"one": role_one, "two": role_two}, {"one": admin_one, "two": admin_two}


def permission_row(harness, role):
    return harness.scalar(select(P.Permission).where(P.Permission.role_id == role.role_id))


def lock_out(role, module):
    return [{"role_id": role.role_id, "module_id": module.module_id,
             "can_create": False, "can_read": False, "can_update": False, "can_delete": False}]


def test_admin_cannot_change_another_accounts_roles(harness):
    """Anyone who signs up is an Admin; that must not let them rewrite what another business's roles may do."""
    client, module, roles, admins = roles_world(harness)
    headers = bearer(login(client, admins["two"].email))

    refused = client.post("/admin/permissions", json=lock_out(roles["one"], module), headers=headers)
    # One foreign role in an otherwise valid request: nothing at all is written
    mixed = client.post("/admin/permissions", json=lock_out(roles["two"], module) + lock_out(roles["one"], module),
                        headers=headers)

    assert refused.status_code == 404 and mixed.status_code == 404
    untouched = permission_row(harness, roles["one"]), permission_row(harness, roles["two"])
    assert all(p.can_read and p.can_delete for p in untouched)


def test_admin_still_changes_their_own_roles(harness):
    client, module, roles, admins = roles_world(harness)
    headers = bearer(login(client, admins["one"].email))

    assert client.post("/admin/permissions", json=lock_out(roles["one"], module), headers=headers).status_code == 200
    assert not permission_row(harness, roles["one"]).can_read
    assert permission_row(harness, roles["two"]).can_read


def test_permission_without_a_role_is_refused(harness):
    client, module, _, admins = roles_world(harness)
    item = {"role_id": None, "module_id": module.module_id,
            "can_create": True, "can_read": True, "can_update": True, "can_delete": True}

    response = client.post("/admin/permissions", json=[item], headers=bearer(login(client, admins["one"].email)))

    assert response.status_code == 400


def test_admin_sees_only_their_own_accounts_permissions_and_users(harness):
    client, _, roles, admins = roles_world(harness)
    headers = bearer(login(client, admins["one"].email))

    listed = client.get("/admin/permissions", headers=headers).json()
    other_user = client.get(f"/admin/users/{admins['two'].user_id}/permissions", headers=headers)
    own_user = client.get(f"/admin/users/{admins['one'].user_id}/permissions", headers=headers)

    assert {p["role_id"] for p in listed} == {roles["one"].role_id}
    assert other_user.status_code == 404 and own_user.status_code == 200
