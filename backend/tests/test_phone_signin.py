"""Sign-in and sign-up with a mobile number, and signing a PC in with a code from the app."""
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import func, select

import app.models.portal_core as P
from app.core.config import settings
from app.routers import agent, auth, phone_auth, sync, team
from app.services import messaging
from app.services import firebase_auth
from tests.conftest import bearer, login, run

ASHA = "+919900000001"
RAVI = "+919900000002"
DETAILS = {"full_name": "Asha", "business_name": "ABC Group", "pincode": "110001", "accept_terms": True}
PC_ONE = {"machine_id": "machine-one-0001", "device_name": "Office PC"}
ALPHA = {"tally_guid": "guid-alpha", "name": "ABC Corp", "books_from": "20250401"}


@pytest.fixture
def client(harness, monkeypatch):
    """The token is the number it proves: "otp:+9199..." stands for an OTP confirmed with Firebase."""
    async def fake_verify(id_token):
        if not id_token.startswith("otp:"):
            raise firebase_auth.PhoneTokenError("The mobile number could not be confirmed. Ask for a new code.")
        return firebase_auth.VerifiedPhone(phone=id_token[4:], uid="uid-" + id_token[4:])

    monkeypatch.setattr(firebase_auth, "verify_phone_token", fake_verify)
    return harness.app(auth.router, phone_auth.router, agent.router, sync.router, team.router, team.public_router)


def register(client, phone=ASHA, **over):
    return client.post("/auth/phone/register", json={"id_token": otp(phone), **DETAILS, **over})


@pytest.fixture(autouse=True)
def long_enough_tokens(monkeypatch):
    # The request model wants a token of real length; the made-up ones are padded with zeros and trimmed here
    original = phone_auth._confirmed

    async def confirmed(id_token):
        return await original(id_token.rstrip("0") if id_token.startswith("otp:") else id_token)

    monkeypatch.setattr(phone_auth, "_confirmed", confirmed)


def otp(phone):
    return "otp:" + phone + "0" * 8


def test_a_new_number_is_asked_to_register_and_then_gets_its_own_account(harness, client):
    first = client.post("/auth/phone/login", json={"id_token": otp(ASHA)}).json()
    assert first == {"registered": False, "phone": ASHA, "invite": None}
    assert harness.scalar(select(func.count()).select_from(P.User)) == 0

    signed = register(client).json()
    assert signed["registered"] and signed["needs_tally_setup"] is True and signed["phone"] == ASHA
    me = client.get("/auth/me", headers=bearer(signed["access_token"])).json()
    assert me["role"] == "Admin" and me["email"] == "" and me["needs_tally_setup"] is True
    company = harness.query(select(P.Company))[0][0]
    assert (company.name, company.awaiting_tally, company.tally_guid, company.pincode) == ("ABC Group", True, None, "110001")
    assert harness.scalar(select(P.UserPhone.phone)) == ASHA

    again = client.post("/auth/phone/login", json={"id_token": otp(ASHA)}).json()
    assert again["registered"] and again["access_token"]


def test_registering_twice_makes_one_account(harness, client):
    one, two = register(client).json(), register(client, full_name="Someone else").json()
    assert one["registered"] and two["registered"]
    assert harness.scalar(select(func.count()).select_from(P.Account)) == 1
    assert harness.scalar(select(func.count()).select_from(P.User)) == 1
    assert harness.scalar(select(P.User.username)) == "Asha"


def test_two_numbers_are_two_accounts(harness, client):
    asha, ravi = register(client).json(), register(client, phone=RAVI, business_name="Ravi & Co").json()
    assert harness.scalar(select(func.count()).select_from(P.Account)) == 2
    names = lambda signed: [c["name"] for c in client.get("/auth/me/companies", headers=bearer(signed["access_token"])).json()]  # noqa: E731
    assert names(asha) == ["ABC Group"] and names(ravi) == ["Ravi & Co"]


def test_what_is_refused(harness, client):
    assert client.post("/auth/phone/login", json={"id_token": "not-a-token-from-firebase-at-all"}).status_code == 400
    assert register(client, accept_terms=False).status_code == 400
    assert register(client, pincode="12").status_code == 400
    assert register(client, email="not an email").status_code == 400
    assert harness.scalar(select(func.count()).select_from(P.Account)) == 0


def test_an_email_that_signs_someone_else_in_is_not_taken(harness, client):
    company = harness.company()
    harness.user(company, harness.role("Admin"), "amit")
    assert register(client, email="Amit@example.com").status_code == 409
    assert register(client, email="asha@example.com").status_code == 200
    # The person with that email still signs in with it, and nobody signs in with the phone account's password
    assert login(client, "amit@example.com")
    assert client.post("/auth/login", json={"email": "asha@example.com", "password": "!"}).status_code == 400
    assert client.post("/auth/login", json={"email": "", "password": "!"}).status_code == 400


def test_off_unless_the_flag_is_on(harness, monkeypatch):
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "demo-project")
    monkeypatch.setattr(settings, "PHONE_SIGNIN_ENABLED", False)
    client = harness.app(phone_auth.router)
    assert client.get("/auth/phone/status").json() == {"enabled": False}
    assert client.post("/auth/phone/login", json={"id_token": "x" * 40}).status_code == 503
    assert client.post("/auth/phone/register", json={"id_token": "x" * 40, **DETAILS}).status_code == 503
    monkeypatch.setattr(settings, "PHONE_SIGNIN_ENABLED", True)
    assert client.get("/auth/phone/status").json() == {"enabled": True}


def test_someone_with_a_password_can_add_their_number(harness, client):
    company = harness.company()
    harness.user(company, harness.role("Admin"), "amit")
    token = login(client, "amit@example.com")
    assert client.post("/auth/phone/link", json={"id_token": otp(RAVI)}, headers=bearer(token)).json() == {"phone": RAVI}
    assert client.post("/auth/phone/link", json={"id_token": otp(RAVI)}, headers=bearer(token)).status_code == 200
    signed = client.post("/auth/phone/login", json={"id_token": otp(RAVI)}).json()
    assert client.get("/auth/me", headers=bearer(signed["access_token"])).json()["email"] == "amit@example.com"
    # A number that signs someone in cannot be taken by another person
    asha = register(client).json()
    assert client.post("/auth/phone/link", json={"id_token": otp(RAVI)}, headers=bearer(asha["access_token"])).status_code == 409


# ── signing a PC in with a code ──

def pair(client, signed, device=PC_ONE):
    started = client.post("/agent/pair/start", json=device).json()
    claim = {"poll_token": started["poll_token"], **device}
    assert client.post("/agent/pair/claim", json=claim).json() == {"status": "pending"}
    seen = client.post("/agent/pair/lookup", json={"code": started["code"]}, headers=bearer(signed["access_token"]))
    assert seen.status_code == 200 and seen.json()["device_name"] == device["device_name"]
    approved = client.post("/agent/pair/approve", json={"code": started["code"].lower().replace("-", " ")},
                           headers=bearer(signed["access_token"]))
    assert approved.status_code == 200, approved.text
    return started, claim


def test_a_pc_is_signed_in_with_a_code_and_the_first_company_takes_the_waiting_one(harness, client):
    signed = register(client).json()
    started, claim = pair(client, signed)
    me = lambda: client.get("/auth/me", headers=bearer(signed["access_token"])).json()  # noqa: E731
    assert me()["needs_tally_setup"] is True   # a code approved is not a PC signed in yet
    device = client.post("/agent/pair/claim", json=claim).json()
    assert device["status"] == "approved" and device["device_token"].startswith("mta_")
    assert device["account"]["name"] == "ABC Group"
    assert me()["needs_tally_setup"] is False   # the PC is in: the app opens, and its company follows

    linked = client.post("/agent/companies/link", json=ALPHA, headers=bearer(device["device_token"])).json()
    companies = harness.query(select(P.Company))
    assert len(companies) == 1   # the waiting company became the Tally company
    company = companies[0][0]
    assert (company.company_id, company.name, company.tally_guid, company.awaiting_tally) == (linked["company_id"], "ABC Corp", "guid-alpha", None)
    assert client.post("/auth/phone/login", json={"id_token": otp(ASHA)}).json()["needs_tally_setup"] is False

    # A second Tally company is a second company
    client.post("/agent/companies/link", json={"tally_guid": "guid-beta", "name": "Beta"}, headers=bearer(device["device_token"]))
    assert harness.scalar(select(func.count()).select_from(P.Company)) == 2

    # Asked again, the same PC in the same account; approving again changes nothing
    again = client.post("/agent/pair/claim", json=claim).json()
    assert again["device"]["device_id"] == device["device"]["device_id"]
    assert harness.scalar(select(func.count()).select_from(P.AgentDevice)) == 1
    assert client.post("/agent/pair/approve", json={"code": started["code"]}, headers=bearer(signed["access_token"])).status_code == 200


def test_a_code_cannot_be_collected_by_another_pc_or_reused_by_another_account(harness, client):
    asha, ravi = register(client).json(), register(client, phone=RAVI, business_name="Ravi & Co").json()
    started, claim = pair(client, asha)
    assert client.post("/agent/pair/claim", json={**claim, "machine_id": "machine-two-0002"}).status_code == 410
    assert client.post("/agent/pair/claim", json={**claim, "poll_token": "x" * 43}).status_code == 410
    assert client.post("/agent/pair/approve", json={"code": started["code"]}, headers=bearer(ravi["access_token"])).status_code == 409
    assert client.post("/agent/pair/approve", json={"code": "ZZZZ-ZZZZ"}, headers=bearer(ravi["access_token"])).status_code == 404
    assert client.post("/agent/pair/approve", json={"code": started["code"]}).status_code == 401


def test_a_code_expires_and_a_pc_cannot_approve_a_code(harness, client):
    signed = register(client).json()
    started, claim = pair(client, signed)
    device = client.post("/agent/pair/claim", json=claim).json()
    # A PC's own token is not a person: it cannot sign another PC in
    other = client.post("/agent/pair/start", json={"machine_id": "machine-two-0002", "device_name": "Godown PC"}).json()
    assert client.post("/agent/pair/approve", json={"code": other["code"]}, headers=bearer(device["device_token"])).status_code == 403

    from sqlalchemy import update
    from app.core.datetime_utils import get_ist_now
    harness.execute(update(P.AgentPairing).values(expires_at=get_ist_now() - timedelta(minutes=1)))
    assert client.post("/agent/pair/approve", json={"code": other["code"]}, headers=bearer(signed["access_token"])).status_code == 404
    assert client.post("/agent/pair/claim", json=claim).status_code == 410


def test_only_someone_who_may_manage_the_sync_agent_approves_a_code(harness, client):
    company = harness.company()
    account = harness.add(P.Account(name="Old & Co"))
    user = harness.user(company, harness.role("Sales"), "sam")
    from sqlalchemy import update
    harness.execute(update(P.User).where(P.User.user_id == user.user_id).values(account_id=account.account_id))
    started = client.post("/agent/pair/start", json=PC_ONE).json()
    token = login(client, "sam@example.com")
    assert client.post("/agent/pair/approve", json={"code": started["code"]}, headers=bearer(token)).status_code == 403


# ── the Firebase token itself ──

@pytest.fixture
def google(monkeypatch):
    """A stand-in for Google's signing key: returns a function that signs ID tokens the way Firebase does."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "securetoken.system.gserviceaccount.com")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=1)).sign(key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()

    async def certs(refresh=False):
        return {"key-1": pem}

    monkeypatch.setattr(firebase_auth, "_signing_certs", certs)
    monkeypatch.setattr(settings, "PHONE_SIGNIN_ENABLED", True)
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "demo-project")

    def sign(signing_key=key, kid="key-1", **over):
        at = int(time.time())
        claims = {"iss": "https://securetoken.google.com/demo-project", "aud": "demo-project", "sub": "uid-1",
                  "iat": at, "exp": at + 3600, "auth_time": at, "phone_number": ASHA,
                  "firebase": {"sign_in_provider": "phone"}, **over}
        return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": kid})
    return sign


def test_a_token_firebase_signed_for_a_confirmed_number_is_taken(google):
    assert run(firebase_auth.verify_phone_token(google())) == firebase_auth.VerifiedPhone(phone=ASHA, uid="uid-1")


@pytest.mark.parametrize("over", [
    {"aud": "another-project"},
    {"iss": "https://securetoken.google.com/another-project"},
    {"exp": int(time.time()) - 10},
    {"auth_time": int(time.time()) - 3 * 3600},
    {"firebase": {"sign_in_provider": "password"}},
    {"phone_number": ""},
    {"phone_number": "9900000001"},
    {"sub": ""},
    {"kid": "unknown-key"},
])
def test_any_other_token_is_refused(google, over):
    kid = over.pop("kid", "key-1")
    with pytest.raises(firebase_auth.PhoneTokenError):
        run(firebase_auth.verify_phone_token(google(kid=kid, **over)))


def test_a_token_signed_by_someone_else_is_refused(google):
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(firebase_auth.PhoneTokenError):
        run(firebase_auth.verify_phone_token(google(signing_key=stranger)))
    unsigned = jwt.encode({"sub": "uid-1", "phone_number": ASHA}, "", algorithm="none", headers={"kid": "key-1"})
    with pytest.raises(firebase_auth.PhoneTokenError):
        run(firebase_auth.verify_phone_token(unsigned))


def test_only_someone_who_can_connect_a_pc_is_held_at_connect_tally(harness, client):
    signed = register(client).json()
    company = harness.query(select(P.Company))[0][0]
    account_id = company.account_id
    sales = harness.scalar(select(P.Role.role_id).where(P.Role.name == "Sales", P.Role.account_id == account_id))
    from tests.conftest import PASSWORD_HASH
    harness.add(P.User(account_id=account_id, company_id=company.company_id, username="sam", email="sam@example.com",
                       password_hash=PASSWORD_HASH, role_id=sales, is_active=True))
    assert client.get("/auth/me", headers=bearer(login(client, "sam@example.com"))).json()["needs_tally_setup"] is False
    # An account from before sign-up in the app has no waiting company and is never held
    old = harness.user(harness.company("Old Co"), harness.role("Admin"), "amit")
    assert client.get("/auth/me", headers=bearer(login(client, old.email))).json()["needs_tally_setup"] is False
    assert signed["needs_tally_setup"] is True


# ── invitations: the person who joins is the one who was invited ──

@pytest.fixture
def mail(monkeypatch):
    sent = []

    async def fake_send(to, subject, text, *args, **kwargs):
        sent.append((to, subject, text))
        return messaging.SendResult(True)

    monkeypatch.setattr(messaging, "send_email", fake_send)
    return sent


def invite(client, harness, signed, **who):
    account_id = harness.scalar(select(P.User.account_id).join(P.UserPhone, P.UserPhone.user_id == P.User.user_id).where(P.UserPhone.phone == signed["phone"]))
    sales = harness.scalar(select(P.Role.role_id).where(P.Role.name == "Sales", P.Role.account_id == account_id))
    company_id = harness.scalar(select(P.Company.company_id).where(P.Company.account_id == account_id))
    return client.post("/admin/invites", headers=bearer(signed["access_token"]), json={"role_id": sales, "company_ids": [company_id], **who})


def test_an_invited_mobile_number_joins_by_signing_in_with_it(harness, client, mail, monkeypatch):
    monkeypatch.setattr(settings, "PHONE_SIGNIN_ENABLED", True)
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "demo-project")
    asha = register(client).json()
    sent = invite(client, harness, asha, phone="99000 00002")
    assert sent.status_code == 200, sent.text
    assert (sent.json()["phone"], sent.json()["email"], sent.json()["invite_token"]) == (RAVI, "", "") and mail == []
    assert invite(client, harness, asha, phone="12").status_code == 400
    assert invite(client, harness, asha).status_code == 400            # neither an email nor a number
    assert invite(client, harness, asha, phone=ASHA).status_code == 409   # already signs someone in

    asked = client.post("/auth/phone/login", json={"id_token": otp(RAVI)}).json()
    assert asked == {"registered": False, "phone": RAVI, "invite": {"account_name": "ABC Group"}}
    joined = client.post("/auth/phone/join", json={"id_token": otp(RAVI), "full_name": "Ravi"}).json()
    me = client.get("/auth/me", headers=bearer(joined["access_token"])).json()
    assert (me["role"], me["username"], me["needs_tally_setup"]) == ("Sales", "Ravi", False)
    assert harness.scalar(select(func.count()).select_from(P.Account)) == 1   # joined, did not start a business

    # Sent again it is the same person; the invitation is used up
    again = client.post("/auth/phone/join", json={"id_token": otp(RAVI), "full_name": "Ravi"}).json()
    assert again["registered"] and harness.scalar(select(func.count()).select_from(P.User)) == 2
    assert harness.scalar(select(P.UserInvite.is_open)) is None


def test_a_number_nobody_invited_cannot_join(harness, client, mail):
    register(client)
    assert client.post("/auth/phone/join", json={"id_token": otp(RAVI), "full_name": "Ravi"}).status_code == 404
    assert harness.scalar(select(func.count()).select_from(P.User)) == 1


def test_an_emailed_invitation_is_accepted_with_a_password_or_a_confirmed_number(harness, client, mail):
    asha = register(client).json()
    token = invite(client, harness, asha, email="rep@example.com").json()["invite_token"]
    assert client.get(f"/auth/invites/{token}").json() == {"email": "rep@example.com", "account_name": "ABC Group", "phone": None}
    joined = client.post("/auth/phone/join", json={"id_token": otp(RAVI), "full_name": "Rep", "token": token})
    assert joined.status_code == 200, joined.text
    me = client.get("/auth/me", headers=bearer(joined.json()["access_token"])).json()
    assert (me["email"], me["role"]) == ("rep@example.com", "Sales")
    # No password was set, so the email alone signs nobody in; the number does
    assert client.post("/auth/login", json={"email": "rep@example.com", "password": "!"}).status_code == 400
    assert client.post("/auth/phone/login", json={"id_token": otp(RAVI)}).json()["registered"]
    assert client.post("/auth/invites/accept", json={"token": token, "username": "Rep", "password": "pw-7654321"}).status_code == 404

    # The other way: a password
    token = invite(client, harness, asha, email="two@example.com").json()["invite_token"]
    assert client.post("/auth/invites/accept", json={"token": token, "username": "Two", "password": "pw-7654321"}).status_code == 200
    assert client.post("/auth/login", json={"email": "two@example.com", "password": "pw-7654321"}).status_code == 200


def test_an_invitation_that_names_a_number_is_only_for_that_number(harness, client, mail, monkeypatch):
    asha = register(client).json()
    token = invite(client, harness, asha, email="rep@example.com", phone=RAVI).json()["invite_token"]
    other = "+919900000003"
    monkeypatch.setattr(settings, "PHONE_SIGNIN_ENABLED", True)
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "demo-project")
    assert client.post("/auth/invites/accept", json={"token": token, "username": "X", "password": "pw-7654321"}).status_code == 400
    assert client.post("/auth/phone/join", json={"id_token": otp(other), "full_name": "X", "token": token}).status_code == 403
    assert client.post("/auth/phone/join", json={"id_token": otp(ASHA), "full_name": "X", "token": token}).status_code == 409
    assert client.post("/auth/phone/join", json={"id_token": otp(RAVI), "full_name": "Rep", "token": token}).status_code == 200


def test_a_mobile_only_invitation_needs_mobile_sign_in_switched_on_and_takes_no_password(harness, client, mail, monkeypatch):
    asha = register(client).json()
    monkeypatch.setattr(settings, "PHONE_SIGNIN_ENABLED", False)
    assert invite(client, harness, asha, phone=RAVI).status_code == 400
    monkeypatch.setattr(settings, "PHONE_SIGNIN_ENABLED", True)
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "demo-project")
    assert invite(client, harness, asha, phone=RAVI).status_code == 200
    assert invite(client, harness, asha, phone=RAVI).status_code == 200   # replaces the open one
    assert harness.scalar(select(func.count()).select_from(P.UserInvite).where(P.UserInvite.is_open == True)) == 1  # noqa: E712
