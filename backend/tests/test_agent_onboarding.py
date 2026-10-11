"""Accounts are created from the sync agent, a PC signs in as a device, and a device reaches only the companies
linked to it."""
import re

import pytest
from sqlalchemy import func, select

import app.models.portal_core as P
from app.core.agent_auth import grant_sync_agent
from app.routers import agent, auth, sync, team
from app.services import messaging
from tests.conftest import PASSWORD, bearer, login, run

PC_ONE = {"machine_id": "machine-one-0001", "device_name": "Office PC"}
PC_TWO = {"machine_id": "machine-two-0002", "device_name": "Godown PC"}
ALPHA = {"tally_guid": "guid-alpha", "name": "ABC Corp", "books_from": "20250401"}
SIGNUP = {"full_name": "Asha", "email": "Asha@Example.com", "phone": "9900000001", "password": PASSWORD,
          "business_name": "ABC Group", "accept_terms": True}


@pytest.fixture
def mail(monkeypatch):
    sent = []

    async def fake_send(to, subject, text, *args, **kwargs):
        sent.append((to, subject, text))
        return messaging.SendResult(True)

    monkeypatch.setattr(messaging, "send_email", fake_send)
    return sent


@pytest.fixture
def client(harness):
    return harness.app(auth.router, agent.router, sync.router, team.router, team.public_router)


def code_from(mail):
    return re.search(r"\b(\d{6})\b", mail[-1][2]).group(1)


def sign_up(client, mail, signup=SIGNUP, device=PC_ONE, company=ALPHA):
    assert client.post("/agent/signup", json=signup).status_code == 200
    res = client.post("/agent/signup/verify", json={"email": signup["email"], "code": code_from(mail), "company": company, **device})
    assert res.status_code == 200, res.text
    return res.json()


def device_headers(token, guid=None):
    return {**bearer(token), **({"X-Tally-Company-GUID": guid} if guid else {})}


def test_sign_up_creates_account_admin_device_and_first_company(harness, client, mail):
    assert client.post("/agent/signup", json=SIGNUP).json()["status"] == "code_sent"
    assert harness.scalar(select(func.count()).select_from(P.User)) == 0   # nothing exists before the code
    wrong = client.post("/agent/signup/verify", json={"email": SIGNUP["email"], "code": "000000", "company": ALPHA, **PC_ONE})
    assert wrong.status_code == 400

    signed = client.post("/agent/signup/verify", json={"email": SIGNUP["email"], "code": code_from(mail), "company": ALPHA, **PC_ONE}).json()

    account_id = signed["account"]["account_id"]
    assert harness.query(select(P.Account.name, P.Account.created_by_user_id)) == [("ABC Group", signed["user"]["user_id"])]
    assert harness.query(select(P.User.email, P.User.account_id, P.User.phone)) == [("asha@example.com", account_id, "9900000001")]
    assert harness.query(select(P.Company.name, P.Company.account_id, P.Company.tally_guid)) == [("ABC Corp", account_id, "guid-alpha")]
    assert signed["device_token"].startswith("mta_")
    # The stored hash is not the token
    assert harness.scalar(select(P.AgentDevice.token_hash)) != signed["device_token"]
    # The new admin can sign in to the app with the same email and password
    assert login(client, "asha@example.com")


def test_verifying_twice_gives_the_same_account(harness, client, mail):
    first = sign_up(client, mail)

    again = client.post("/agent/signup/verify", json={"email": SIGNUP["email"], "code": code_from(mail), "company": ALPHA, **PC_ONE}).json()

    assert again["account"] == first["account"] and again["device"]["device_id"] == first["device"]["device_id"]
    for model in (P.Account, P.User, P.Company, P.AgentDevice, P.AgentCompanyLink):
        assert harness.scalar(select(func.count()).select_from(model)) == 1


def test_an_existing_email_cannot_sign_up_again(client, mail):
    sign_up(client, mail)
    assert client.post("/agent/signup", json=SIGNUP).status_code == 409


def test_device_token_syncs_its_company_and_nothing_else(client, mail):
    token = sign_up(client, mail)["device_token"]

    assert client.get("/sync/last-alter-id", headers=device_headers(token, "guid-alpha")).status_code == 200
    assert client.get("/sync/last-alter-id", headers=device_headers(token)).status_code == 400          # must name a company
    assert client.get("/sync/last-alter-id", headers=device_headers(token, "guid-other")).status_code == 409
    assert client.get("/auth/me", headers=device_headers(token)).status_code == 403                    # not a login for the app
    assert client.get("/sync/health", headers=device_headers(token)).status_code == 403


def test_same_company_name_and_guid_in_two_accounts_stay_apart(harness, client, mail):
    one = sign_up(client, mail)
    two = sign_up(client, mail, signup={**SIGNUP, "email": "ravi@example.com", "business_name": "Ravi & Co"}, device=PC_TWO)

    assert one["company"]["company_id"] != two["company"]["company_id"]
    assert one["account"]["account_id"] != two["account"]["account_id"]
    names = {c["name"] for c in client.get("/agent/companies", headers=device_headers(two["device_token"])).json()}
    assert names == {"ABC Corp"}
    assert harness.scalar(select(func.count()).select_from(P.Company)) == 2


def test_linking_is_repeat_safe_and_one_pc_syncs_a_company_at_a_time(harness, client, mail):
    first = sign_up(client, mail)
    token_one = first["device_token"]
    beta = {"tally_guid": "guid-beta", "name": "Beta Traders"}
    linked = client.post("/agent/companies/link", json=beta, headers=device_headers(token_one)).json()
    again = client.post("/agent/companies/link", json=beta, headers=device_headers(token_one)).json()
    assert linked["company_id"] == again["company_id"]
    assert harness.scalar(select(func.count()).select_from(P.Company)) == 2

    token_two = client.post("/agent/signin", json={"email": "asha@example.com", "password": PASSWORD, **PC_TWO}).json()["device_token"]
    refused = client.post("/agent/companies/link", json=beta, headers=device_headers(token_two))
    assert refused.status_code == 409 and refused.headers["X-Sync-Reason"] == "linked_to_another_device"
    moved = client.post("/agent/companies/link", json={**beta, "take_over": True}, headers=device_headers(token_two))
    assert moved.status_code == 200

    # The first PC no longer syncs Beta; the second does
    assert client.get("/sync/last-alter-id", headers=device_headers(token_one, "guid-beta")).status_code == 403
    assert client.get("/sync/last-alter-id", headers=device_headers(token_two, "guid-beta")).status_code == 200
    assert harness.scalar(select(func.count()).select_from(P.AgentCompanyLink).where(
        P.AgentCompanyLink.company_id == linked["company_id"], P.AgentCompanyLink.is_active == True)) == 1  # noqa: E712


def test_only_holders_of_manage_sync_agent_can_sign_a_pc_in(harness, client, mail):
    signed = sign_up(client, mail)
    admin_role_id = harness.scalar(select(P.Role.role_id).where(P.Role.name == "Admin"))
    company_id = signed["company"]["company_id"]
    partner = harness.user(type("C", (), {"company_id": company_id})(), type("R", (), {"role_id": admin_role_id})(), "partner")
    harness.execute(P.User.__table__.update().where(P.User.user_id == partner.user_id).values(account_id=signed["account"]["account_id"]))

    refused = client.post("/agent/signin", json={"email": partner.email, "password": PASSWORD, **PC_TWO})
    assert refused.status_code == 403   # an admin, but without the permission

    owner = bearer(login(client, "asha@example.com"))
    assert client.put(f"/admin/users/{partner.user_id}/sync-agent", json={"allowed": True}, headers=owner).status_code == 200
    assert client.post("/agent/signin", json={"email": partner.email, "password": PASSWORD, **PC_TWO}).status_code == 200

    # The partner may now take it away from the owner, but the last holder cannot be removed
    partner_headers = bearer(login(client, partner.email))
    assert client.put(f"/admin/users/{signed['user']['user_id']}/sync-agent", json={"allowed": False}, headers=partner_headers).status_code == 200
    last = client.put(f"/admin/users/{partner.user_id}/sync-agent", json={"allowed": False}, headers=partner_headers)
    assert last.status_code == 409


def test_revoking_a_pc_signs_it_out_and_frees_its_companies(harness, client, mail):
    signed = sign_up(client, mail)
    token = signed["device_token"]
    owner = bearer(login(client, "asha@example.com"))
    devices = client.get("/admin/agent-devices", headers=owner).json()
    assert [(d["name"], d["signed_in"], [c["name"] for c in d["companies"]]) for d in devices] == [("Office PC", True, ["ABC Corp"])]

    assert client.post(f"/admin/agent-devices/{signed['device']['device_id']}/revoke", headers=owner).status_code == 200

    out = client.get("/sync/last-alter-id", headers=device_headers(token, "guid-alpha"))
    assert out.status_code == 401 and out.headers["X-Auth-Reason"] == "admin_revoke"
    assert harness.scalar(select(func.count()).select_from(P.AgentCompanyLink).where(P.AgentCompanyLink.is_active == True)) == 0  # noqa: E712


def test_invited_user_joins_the_inviters_account_and_cannot_use_the_agent(harness, client, mail):
    signed = sign_up(client, mail)
    owner = bearer(login(client, "asha@example.com"))
    account_id = signed["account"]["account_id"]
    sales_role_id = harness.scalar(select(P.Role.role_id).where(P.Role.name == "Sales", P.Role.account_id == account_id))
    shared_role = harness.role("Salesman")   # from before roles belonged to accounts: not this account's
    other = sign_up(client, mail, signup={**SIGNUP, "email": "ravi@example.com"}, device=PC_TWO)

    # Another account's company is "not found", never "not yours"
    foreign = client.post("/admin/invites", headers=owner, json={
        "email": "rep@example.com", "role_id": sales_role_id, "company_ids": [other["company"]["company_id"]]})
    assert foreign.status_code == 404
    not_ours = client.post("/admin/invites", headers=owner, json={
        "email": "rep@example.com", "role_id": shared_role.role_id, "company_ids": [signed["company"]["company_id"]]})
    assert not_ours.status_code == 400

    invite = client.post("/admin/invites", headers=owner, json={
        "email": "Rep@Example.com", "role_id": sales_role_id, "company_ids": [signed["company"]["company_id"]]}).json()
    assert client.get(f"/auth/invites/{invite['invite_token']}").json() == {"email": "rep@example.com", "account_name": "ABC Group", "phone": None}
    accepted = client.post("/auth/invites/accept", json={"token": invite["invite_token"], "username": "Rep", "password": "pw-7654321"})
    assert accepted.status_code == 200

    assert harness.query(select(P.User.account_id, P.User.company_id).where(P.User.email == "rep@example.com")) == [
        (signed["account"]["account_id"], signed["company"]["company_id"])]
    # Used once
    assert client.post("/auth/invites/accept", json={"token": invite["invite_token"], "username": "Rep", "password": "pw-7654321"}).status_code == 404
    assert client.post("/agent/signin", json={"email": "rep@example.com", "password": "pw-7654321", **PC_TWO}).status_code == 403


def test_first_link_takes_over_the_company_from_before_accounts(harness, client, mail):
    """A company made before accounts has no Tally GUID. Signing the PC in must link that company, not make a
    second one of the same name beside it."""
    signed = sign_up(client, mail)
    account_id = signed["account"]["account_id"]
    token = signed["device_token"]
    harness.execute(P.Company.__table__.insert().values(
        account_id=account_id, name="Old Books ", books_begin_date=signed_date(), is_active=True))
    old_id = harness.scalar(select(P.Company.company_id).where(P.Company.name == "Old Books "))

    linked = client.post("/agent/companies/link", json={"tally_guid": "guid-old", "name": "old books"},
                         headers=device_headers(token)).json()
    assert linked["company_id"] == old_id
    assert harness.scalar(select(P.Company.tally_guid).where(P.Company.company_id == old_id)) == "guid-old"
    again = client.post("/agent/companies/link", json={"tally_guid": "guid-old", "name": "old books"},
                        headers=device_headers(token)).json()
    assert again["company_id"] == old_id

    # A different GUID under the same name is another Tally company: the linked one is not touched
    other = client.post("/agent/companies/link", json={"tally_guid": "guid-new", "name": "Old Books"},
                        headers=device_headers(token)).json()
    assert other["company_id"] != old_id
    assert harness.scalar(select(func.count()).select_from(P.Company).where(P.Company.account_id == account_id)) == 3


def test_a_company_without_a_guid_is_not_taken_over_by_another_name_or_account(harness, client, mail):
    signed = sign_up(client, mail)
    harness.execute(P.Company.__table__.insert().values(
        account_id=signed["account"]["account_id"], name="Old Books", books_begin_date=signed_date(), is_active=True))
    other_account = sign_up(client, mail, signup={**SIGNUP, "email": "ravi@example.com", "business_name": "Ravi Traders"},
                            device=PC_TWO, company={"tally_guid": "guid-ravi", "name": "Ravi Traders"})

    # Another customer linking a company of the same name gets their own
    theirs = client.post("/agent/companies/link", json={"tally_guid": "guid-x", "name": "Old Books"},
                         headers=device_headers(other_account["device_token"])).json()
    old_id = harness.scalar(select(P.Company.company_id).where(P.Company.tally_guid.is_(None)))
    assert theirs["company_id"] != old_id
    # A different name in the same account is a new company too
    renamed = client.post("/agent/companies/link", json={"tally_guid": "guid-y", "name": "New Books"},
                          headers=device_headers(signed["device_token"])).json()
    assert renamed["company_id"] != old_id
    assert harness.scalar(select(P.Company.tally_guid).where(P.Company.company_id == old_id)) is None


def signed_date():
    from datetime import date
    return date(2025, 4, 1)


def test_an_admin_already_signed_in_can_open_a_company_the_moment_it_is_linked(harness, client, mail):
    signed = sign_up(client, mail)
    owner = bearer(login(client, "asha@example.com"))
    first = client.get("/auth/me", headers=owner).json()["company_id"]   # the sign-in now remembers one company

    beta = client.post("/agent/companies/link", json={"tally_guid": "guid-beta", "name": "Beta Corp"},
                       headers=device_headers(signed["device_token"])).json()

    opened = client.get("/auth/me", headers={**owner, "X-Company-ID": str(beta["company_id"])}).json()
    assert opened["company_id"] == beta["company_id"] != first


def test_another_copy_of_the_same_books_is_refused_until_it_is_linked_on_purpose(harness, client, mail):
    """A copied or restored company keeps its Tally GUID. Its company number or books-from date differs, and
    that is what stops it from being synced into the original."""
    original = {**ALPHA, "fingerprint": "100004|20250401"}
    signed = sign_up(client, mail, company=original)
    token = signed["device_token"]
    same = {"X-Tally-Company-Fingerprint": "100004|20250401"}
    copy = {"X-Tally-Company-Fingerprint": "100009|20250401"}

    assert client.get("/sync/last-alter-id", headers={**device_headers(token, "guid-alpha"), **same}).status_code == 200
    assert client.get("/sync/last-alter-id", headers=device_headers(token, "guid-alpha")).status_code == 200   # an older agent sends none
    refused = client.get("/sync/last-alter-id", headers={**device_headers(token, "guid-alpha"), **copy})
    assert refused.status_code == 409 and refused.headers["X-Sync-Reason"] == "company_copy_mismatch"
    assert client.post("/agent/companies/link", json={**ALPHA, "fingerprint": "100009|20250401"},
                       headers=device_headers(token)).status_code == 409

    # The state report says why, where the app shows it, and does not count as a sync
    client.post("/sync/state", headers=device_headers(token), json=[{"tally_guid": "guid-alpha", "state": "live", "ok": True,
                                                                     "fingerprint": "100009|20250401"}])
    state = harness.query(select(P.CompanySyncState.state, P.CompanySyncState.last_error, P.CompanySyncState.last_success_at))[0]
    assert state[0] == "error" and "different copy" in state[1] and state[2] is None

    # Unlinking and linking again is the deliberate way to say "this is the copy to sync now"
    client.post("/agent/companies/unlink", json={"tally_guid": "guid-alpha"}, headers=device_headers(token))
    assert client.post("/agent/companies/link", json={**ALPHA, "fingerprint": "100009|20250401"},
                       headers=device_headers(token)).status_code == 200
    assert client.get("/sync/last-alter-id", headers={**device_headers(token, "guid-alpha"), **copy}).status_code == 200


def test_the_first_report_records_which_copy_is_synced_and_the_progress_of_a_full_sync(harness, client, mail):
    signed = sign_up(client, mail)                                           # linked by an agent that sent no fingerprint
    token = signed["device_token"]
    client.post("/sync/state", headers=device_headers(token), json=[{"tally_guid": "guid-alpha", "state": "live", "ok": True,
                "fingerprint": "100004|20250401", "progress": "Full sync 3 of 12", "master_alter_id": 40, "voucher_alter_id": 90}])

    assert harness.scalar(select(P.Company.tally_fingerprint)) == "100004|20250401"
    row = harness.query(select(P.CompanySyncState.progress, P.CompanySyncState.master_alter_id, P.CompanySyncState.voucher_alter_id))[0]
    assert tuple(row) == ("Full sync 3 of 12", 40, 90)
    client.post("/sync/state", headers=device_headers(token), json=[{"tally_guid": "guid-alpha", "state": "live", "ok": True}])
    assert harness.scalar(select(P.CompanySyncState.progress)) is None        # finished: the note goes away
