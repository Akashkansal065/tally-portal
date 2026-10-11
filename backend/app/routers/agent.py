"""Desktop Sync Agent onboarding: where a PC is signed in and companies are linked to it.

A PC is signed in with an admin's email and password (/agent/signin), or with a code the agent shows and
someone signed in to the app types there (/agent/pair), which is how a person with no password signs it in.

Accounts are created in the app with a mobile number (routers/phone_auth.py). Sign-up from the agent
(/agent/signup) is no longer offered by the agent and stays here for the versions still installed. It always
makes a new account with its first admin and first company and never joins an existing one: everyone else is
invited from the app.
"""
import hashlib
import logging
import secrets
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.agent_auth import (
    agent_device, can_manage_sync_agent, copy_mismatch_error, different_copy, grant_sync_agent, new_device_token, )
from app.core.account_roles import create_default_roles
from app.core.config import settings
from app.core.database import get_db
from app.core.datetime_utils import get_ist_now
from app.core.permissions import get_current_user, invalidate_auth_cache
from app.core.rate_limiter import limiter
from app.core.security import get_password_hash, verify_password
from app.models.portal_core import (
    Account, AgentCompanyLink, AgentDevice, AgentPairing, Company, SignupVerification, User, UserCompanyAccess,
)
from app.services import alerts, messaging

logger = logging.getLogger("app.routers.agent")
router = APIRouter(prefix="/agent", tags=["Desktop Sync Agent"])

CODE_TTL_MINUTES = 10
MAX_CODE_ATTEMPTS = 5
PAIRING_TTL_MINUTES = 10
# Letters and digits that are not mistaken for one another when read off a screen and typed on a phone
PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PAIRING_CODE_LENGTH = 8


# ─── Schemas ─────────────────────────────────────────────────────────────────

class TallyCompanyIn(BaseModel):
    tally_guid: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)
    books_from: Optional[str] = None      # YYYYMMDD or YYYY-MM-DD, as Tally reports it
    fingerprint: Optional[str] = Field(default=None, max_length=200)
    tally_url: Optional[str] = Field(default=None, max_length=255)


class DeviceIn(BaseModel):
    machine_id: str = Field(min_length=8, max_length=128)
    device_name: Optional[str] = Field(default=None, max_length=150)


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=50)
    email: str = Field(max_length=120)
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    business_name: str = Field(min_length=1, max_length=150)
    accept_terms: bool


class SignupVerifyRequest(DeviceIn):
    email: str
    code: str = Field(min_length=4, max_length=10)
    company: TallyCompanyIn


class SigninRequest(DeviceIn):
    email: str
    password: str


class PairingCodeRequest(BaseModel):
    code: str = Field(min_length=4, max_length=20)


class PairingClaimRequest(DeviceIn):
    poll_token: str = Field(min_length=20, max_length=200)


class LinkRequest(TallyCompanyIn):
    take_over: bool = False


class UnlinkRequest(BaseModel):
    tally_guid: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _code_hash(email: str, code: str) -> str:
    return hashlib.sha256(f"{email.lower()}:{code.strip()}".encode()).hexdigest()


def _books_from(value: Optional[str]) -> date:
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime((value or "").strip(), fmt).date()
        except ValueError:
            continue
    return date.today()


async def _register_device(db: AsyncSession, account: Account, user: User, device_in: DeviceIn) -> tuple:
    """Find or make this PC's device row in the account and give it a fresh token. Returns (device, token)."""
    device = (await db.execute(select(AgentDevice).where(
        AgentDevice.account_id == account.account_id, AgentDevice.machine_id == device_in.machine_id))).scalars().first()
    if device is None:
        if account.max_devices is not None:
            active = (await db.execute(select(func.count()).select_from(AgentDevice).where(
                AgentDevice.account_id == account.account_id, AgentDevice.revoked_at.is_(None)))).scalar() or 0
            if active >= account.max_devices:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail=f"Your plan allows {account.max_devices} synced PC(s). Remove one in the app first.")
        device = AgentDevice(account_id=account.account_id, machine_id=device_in.machine_id)
        db.add(device)
    token, token_hash = new_device_token()
    device.token_hash = token_hash
    device.name = device_in.device_name or device.name
    device.registered_by_user_id = user.user_id
    device.revoked_at = None
    device.last_seen_at = get_ist_now()
    await db.flush()
    return device, token


async def _company_from_before_accounts(db: AsyncSession, account: Account, name: str) -> Optional[Company]:
    """The account's company that has no Tally GUID yet and carries this name, when there is exactly one.

    Companies made before accounts existed were never given a GUID. The first link has to take such a company
    over, or its ledgers, vouchers, orders and waiting pushes are left behind under a second company of the
    same name. This is the only place a name decides anything, and only for a company with no GUID."""
    wanted = name.strip().lower()
    rows = (await db.execute(select(Company).where(
        Company.account_id == account.account_id,
        (Company.tally_guid.is_(None)) | (Company.tally_guid == "")))).scalars().all()
    matches = [c for c in rows if (c.name or "").strip().lower() == wanted]
    return matches[0] if len(matches) == 1 else None


async def _company_awaiting_tally(db: AsyncSession, account: Account) -> Optional[Company]:
    """The company an account signed up from the app was given to start with, while it still has no Tally
    company. The first company linked takes its place, so the people already in it are in the real one."""
    rows = (await db.execute(select(Company).where(
        Company.account_id == account.account_id, Company.awaiting_tally == True,  # noqa: E712
        (Company.tally_guid.is_(None)) | (Company.tally_guid == "")))).scalars().all()
    return rows[0] if len(rows) == 1 else None


async def _link_company(db: AsyncSession, account: Account, device: AgentDevice, user: User,
                        info: TallyCompanyIn, take_over: bool = False) -> Company:
    """Make the Tally company a company of the account (found by GUID; by name only for a company from
    before accounts that has no GUID yet) and make this PC the one syncing it. Doing it again changes nothing."""
    guid = info.tally_guid.strip()
    company = (await db.execute(select(Company).where(
        Company.account_id == account.account_id, Company.tally_guid == guid))).scalars().first()
    if company is None:
        company = await _company_from_before_accounts(db, account, info.name)
        if company is not None:
            company.tally_guid = guid
            company.tally_fingerprint = info.fingerprint or company.tally_fingerprint
    if company is None:
        company = await _company_awaiting_tally(db, account)
        if company is not None:
            company.tally_guid = guid
            company.tally_fingerprint = info.fingerprint
            company.books_begin_date = _books_from(info.books_from)
            company.awaiting_tally = None
    if company is None:
        if account.max_companies is not None:
            held = (await db.execute(select(func.count()).select_from(Company).where(
                Company.account_id == account.account_id))).scalar() or 0
            if held >= account.max_companies:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail=f"Your plan allows {account.max_companies} company(ies).")
        company = Company(account_id=account.account_id, name=info.name.strip(), tally_guid=guid,
                          tally_fingerprint=info.fingerprint, books_begin_date=_books_from(info.books_from), is_active=True)
        db.add(company)
        await db.flush()
    elif info.name.strip() and company.name != info.name.strip():
        company.name = info.name.strip()   # renamed in Tally: same GUID, same company

    current = (await db.execute(select(AgentCompanyLink).where(
        AgentCompanyLink.company_id == company.company_id, AgentCompanyLink.is_active == True))).scalars().first()  # noqa: E712
    if info.fingerprint:
        if current is None or not company.tally_fingerprint:
            # Linking a company that no PC holds is a deliberate choice of which copy of the books to sync.
            # While a PC holds it, another copy is refused, also when moving it to this PC.
            company.tally_fingerprint = info.fingerprint.strip()
        elif different_copy(company, info.fingerprint):
            raise copy_mismatch_error(company)
    if current is not None and current.device_id != device.device_id:
        if not take_over:
            other = (await db.execute(select(AgentDevice.name).where(AgentDevice.device_id == current.device_id))).scalar()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, headers={"X-Sync-Reason": "linked_to_another_device"},
                detail=f"'{company.name}' is already synced from another PC ({other or 'unnamed'}). Move it to this PC?")
        current.is_active = None
        current.unlinked_at = get_ist_now()
        await db.flush()
        current = None
    if current is None:
        db.add(AgentCompanyLink(device_id=device.device_id, company_id=company.company_id, is_active=True,
                                tally_url=info.tally_url))
    elif info.tally_url:
        current.tally_url = info.tally_url

    has_access = (await db.execute(select(UserCompanyAccess.access_id).where(
        UserCompanyAccess.user_id == user.user_id, UserCompanyAccess.company_id == company.company_id))).scalars().first()
    if has_access is None:
        db.add(UserCompanyAccess(user_id=user.user_id, company_id=company.company_id))
    await db.flush()
    return company


def _signed_in(account: Account, user: User, device: AgentDevice, token: str, company: Optional[Company] = None) -> dict:
    return {
        "device_token": token, "token_type": "bearer",
        "account": {"account_id": account.account_id, "name": account.name},
        "user": {"user_id": user.user_id, "email": user.email, "username": user.username},
        "device": {"device_id": device.device_id, "name": device.name},
        "company": {"company_id": company.company_id, "name": company.name, "tally_guid": company.tally_guid} if company else None,
    }


async def _device_context(request: Request, user: User, db: AsyncSession) -> tuple:
    device = agent_device(request)
    if device is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sign in to the sync agent on this PC first.")
    account = (await db.execute(select(Account).where(Account.account_id == device.account_id))).scalars().first()
    return device, account


# ─── Sign-up ─────────────────────────────────────────────────────────────────

@router.post("/signup")
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def signup(request: Request, response: Response, req: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Step one of creating an account: take the details and email a code. Nothing is created yet."""
    email = messaging.clean_email(req.email)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address.")
    email = email.lower()
    if not req.accept_terms:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accept the terms to create an account.")
    taken = (await db.execute(select(User.user_id).where(func.lower(User.email) == email))).scalars().first()
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have an account. Sign in.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    pending = (await db.execute(select(SignupVerification).where(SignupVerification.email == email))).scalars().first()
    if pending is None:
        pending = SignupVerification(email=email, code_hash="", payload={}, expires_at=get_ist_now())
        db.add(pending)
    pending.code_hash = _code_hash(email, code)
    pending.attempts = 0
    pending.expires_at = get_ist_now() + timedelta(minutes=CODE_TTL_MINUTES)
    pending.payload = {
        "full_name": req.full_name.strip(), "phone": req.phone.strip(), "business_name": req.business_name.strip(),
        "password_hash": get_password_hash(req.password), "terms_accepted_at": get_ist_now().isoformat(),
    }
    sent = await messaging.send_email(
        email, f"{code} is your MyTally verification code",
        f"Your MyTally verification code is {code}.\n\nIt expires in {CODE_TTL_MINUTES} minutes. "
        "If you did not ask for it, ignore this email.")
    if not sent.ok:
        await db.rollback()
        logger.error(f"Sign-up code could not be emailed to {email}: {sent.error}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="The verification email could not be sent. Try again in a few minutes.")
    await db.commit()
    return {"status": "code_sent", "email": email, "expires_in_minutes": CODE_TTL_MINUTES}


@router.post("/signup/verify")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def signup_verify(request: Request, response: Response, req: SignupVerifyRequest, db: AsyncSession = Depends(get_db)):
    """Step two: with the emailed code, create the account, its first admin, this PC's device and the first
    company, all or nothing. Sent again with the same code it answers with the same account."""
    email = (req.email or "").strip().lower()
    pending = (await db.execute(
        select(SignupVerification).where(SignupVerification.email == email).with_for_update())).scalars().first()
    wrong = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That code is wrong or has expired. Ask for a new one.")
    if pending is None or pending.expires_at < get_ist_now() or pending.attempts >= MAX_CODE_ATTEMPTS:
        raise wrong
    if not secrets.compare_digest(pending.code_hash, _code_hash(email, req.code)):
        pending.attempts += 1
        await db.commit()
        raise wrong

    done = (pending.payload or {}).get("completed")
    if done:
        # The first answer was lost on the way back: same account, same device, a fresh token
        account = (await db.execute(select(Account).where(Account.account_id == done["account_id"]))).scalars().first()
        user = (await db.execute(select(User).where(User.user_id == done["user_id"]))).scalars().first()
        device, token = await _register_device(db, account, user, req)
        company = await _link_company(db, account, device, user, req.company)
        await db.commit()
        return _signed_in(account, user, device, token, company)

    if (await db.execute(select(User.user_id).where(func.lower(User.email) == email))).scalars().first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have an account. Sign in.")
    details = pending.payload
    account = Account(name=details["business_name"], status="active")
    db.add(account)
    await db.flush()
    admin_role = await create_default_roles(db, account.account_id)   # the account's own Admin and Sales roles
    # The first company comes with the sign-up: a user always has a company to be in
    company = Company(account_id=account.account_id, name=req.company.name.strip(), tally_guid=req.company.tally_guid.strip(),
                      tally_fingerprint=req.company.fingerprint, books_begin_date=_books_from(req.company.books_from),
                      is_active=True)
    db.add(company)
    await db.flush()
    user = User(account_id=account.account_id, company_id=company.company_id, username=details["full_name"][:50],
                email=email, phone=details["phone"], password_hash=details["password_hash"], role_id=admin_role.role_id,
                is_active=True, email_verified_at=get_ist_now(), ledger_scope="full", stock_scope="full")
    db.add(user)
    await db.flush()
    account.created_by_user_id = user.user_id
    await grant_sync_agent(db, user.user_id, user.user_id, "Created the account from the sync agent")
    device, token = await _register_device(db, account, user, req)
    company = await _link_company(db, account, device, user, req.company)
    pending.payload = {"completed": {"account_id": account.account_id, "user_id": user.user_id}}
    await db.commit()
    logger.info(f"Account #{account.account_id} '{account.name}' created from the sync agent by {email}.")
    return _signed_in(account, user, device, token, company)


# ─── Sign-in ─────────────────────────────────────────────────────────────────

@router.post("/signin")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def signin(request: Request, response: Response, req: SigninRequest, db: AsyncSession = Depends(get_db)):
    """Sign this PC in to an existing account. Only people who hold "Manage sync agent" can."""
    login = (req.email or "").strip().lower()
    user = (await db.execute(select(User).where(
        (func.lower(User.email) == login) | (func.lower(User.username) == login), User.is_active == True  # noqa: E712
    ).order_by(User.user_id))).scalars().first()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect email or password")
    if user.account_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This server's data has not been moved into an account yet. Ask your administrator.")
    if not await can_manage_sync_agent(db, user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You are not allowed to use the sync agent. Ask an admin who can for the 'Manage sync agent' permission.")
    account = (await db.execute(select(Account).where(Account.account_id == user.account_id))).scalars().first()
    if account is None or account.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is closed.")
    device, token = await _register_device(db, account, user, req)
    await db.commit()
    return _signed_in(account, user, device, token)


# ─── Sign-in with a code ─────────────────────────────────────────────────────

def _pairing_code_hash(code: str) -> str:
    """The hash kept for a code, however it was typed: lower case, with the dash, with spaces."""
    cleaned = "".join(ch for ch in (code or "").upper() if ch.isalnum())
    return hashlib.sha256(f"pair:{cleaned}".encode()).hexdigest()


async def _open_pairing(db: AsyncSession, code: str) -> AgentPairing:
    pairing = (await db.execute(select(AgentPairing).where(
        AgentPairing.code_hash == _pairing_code_hash(code)).with_for_update())).scalars().first()
    if pairing is None or pairing.expires_at < get_ist_now():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="That code is wrong or has expired. Check the code shown on the PC.")
    return pairing


async def _pairing_approver(request: Request, user: User, db: AsyncSession) -> Account:
    """Who may sign a PC in with a code: a person signed in to the app (never a PC with its own token) who
    holds "Manage sync agent"."""
    if agent_device(request) is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Enter the code in the MyTally app, signed in as yourself.")
    if user.account_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This server's data has not been moved into an account yet. Ask your administrator.")
    if not await can_manage_sync_agent(db, user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You are not allowed to use the sync agent. Ask an admin who can for the 'Manage sync agent' permission.")
    account = (await db.execute(select(Account).where(Account.account_id == user.account_id))).scalars().first()
    if account is None or account.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is closed.")
    return account


@router.post("/pair/start")
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def pair_start(request: Request, response: Response, req: DeviceIn, db: AsyncSession = Depends(get_db)):
    """A PC asks to be signed in with a code. It shows the code; the secret it also gets is what it later
    collects its sign-in with. Nothing is signed in until someone approves the code in the app."""
    code = "".join(secrets.choice(PAIRING_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))
    poll_token = secrets.token_urlsafe(32)
    db.add(AgentPairing(code_hash=_pairing_code_hash(code), poll_hash=hashlib.sha256(poll_token.encode()).hexdigest(),
                        machine_id=req.machine_id, device_name=req.device_name,
                        expires_at=get_ist_now() + timedelta(minutes=PAIRING_TTL_MINUTES)))
    await db.commit()
    return {"code": f"{code[:4]}-{code[4:]}", "poll_token": poll_token, "expires_in_minutes": PAIRING_TTL_MINUTES}


@router.post("/pair/lookup")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def pair_lookup(request: Request, response: Response, req: PairingCodeRequest,
                      user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Which PC a code belongs to, shown to the person before they approve it."""
    account = await _pairing_approver(request, user, db)
    pairing = await _open_pairing(db, req.code)
    return {"device_name": pairing.device_name or "A PC", "account_name": account.name,
            "approved": pairing.account_id == account.account_id}


@router.post("/pair/approve")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def pair_approve(request: Request, response: Response, req: PairingCodeRequest,
                       user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Sign the PC showing this code in to the caller's account. Approving it again changes nothing."""
    account = await _pairing_approver(request, user, db)
    pairing = await _open_pairing(db, req.code)
    if pairing.account_id is not None and pairing.account_id != account.account_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That code has already been used. Ask the PC for a new one.")
    if pairing.account_id is None:
        pairing.account_id = account.account_id
        pairing.approved_by_user_id = user.user_id
        pairing.approved_at = get_ist_now()
        await db.commit()
        logger.info(f"PC '{pairing.device_name}' approved for account #{account.account_id} by user #{user.user_id}.")
    return {"status": "approved", "device_name": pairing.device_name or "A PC"}


@router.post("/pair/claim")
@limiter.limit("40/minute")
async def pair_claim(request: Request, response: Response, req: PairingClaimRequest, db: AsyncSession = Depends(get_db)):
    """The PC asks whether its code has been approved, and once it has, is signed in. Asked again after
    that, it is the same PC in the same account with a fresh token."""
    pairing = (await db.execute(select(AgentPairing).where(
        AgentPairing.poll_hash == hashlib.sha256(req.poll_token.encode()).hexdigest()).with_for_update())).scalars().first()
    if pairing is None or pairing.machine_id != req.machine_id or pairing.expires_at < get_ist_now():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="That code has expired. Ask for a new one.")
    if pairing.account_id is None:
        return {"status": "pending"}
    account = (await db.execute(select(Account).where(Account.account_id == pairing.account_id))).scalars().first()
    user = (await db.execute(select(User).where(
        User.user_id == pairing.approved_by_user_id, User.is_active == True))).scalars().first()  # noqa: E712
    if account is None or account.status != "active" or user is None or user.account_id != account.account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is closed.")
    device, token = await _register_device(db, account, user, req)
    pairing.device_id = device.device_id
    await db.commit()
    return {"status": "approved", **_signed_in(account, user, device, token)}


@router.post("/token/refresh")
async def refresh_token(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Swap this PC's token for a new one. The old one stops working at once."""
    device, _ = await _device_context(request, user, db)
    token, token_hash = new_device_token()
    device.token_hash = token_hash
    await db.commit()
    return {"device_token": token, "token_type": "bearer"}


# ─── Companies ───────────────────────────────────────────────────────────────

@router.get("/companies")
async def list_companies(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The account's companies and which PC syncs each."""
    device, account = await _device_context(request, user, db)
    rows = (await db.execute(
        select(Company, AgentCompanyLink.device_id, AgentDevice.name)
        .join(AgentCompanyLink, (AgentCompanyLink.company_id == Company.company_id) & (AgentCompanyLink.is_active == True), isouter=True)  # noqa: E712
        .join(AgentDevice, AgentDevice.device_id == AgentCompanyLink.device_id, isouter=True)
        .where(Company.account_id == account.account_id).order_by(Company.name))).all()
    return [
        {"company_id": company.company_id, "name": company.name, "tally_guid": company.tally_guid,
         "linked_device_id": device_id, "linked_device_name": device_name, "linked_here": device_id == device.device_id}
        for company, device_id, device_name in rows
    ]


@router.post("/companies/link")
async def link_company(request: Request, req: LinkRequest, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    device, account = await _device_context(request, user, db)
    company = await _link_company(db, account, device, user, req, take_over=req.take_over)
    await db.commit()
    # People already signed in remember which companies they may open for a few minutes. Forget that now, so
    # an admin can switch to a company the moment it is linked instead of being put back in the old one.
    for user_id in (await db.execute(select(User.user_id).where(User.account_id == account.account_id))).scalars().all():
        invalidate_auth_cache(user_id=user_id)
    return {"company_id": company.company_id, "name": company.name, "tally_guid": company.tally_guid, "linked_here": True}


@router.post("/companies/unlink")
async def unlink_company(request: Request, req: UnlinkRequest, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    """Stop syncing a company from this PC. Its data stays; another PC can link it."""
    device, account = await _device_context(request, user, db)
    link = (await db.execute(
        select(AgentCompanyLink).join(Company, Company.company_id == AgentCompanyLink.company_id)
        .where(Company.account_id == account.account_id, Company.tally_guid == req.tally_guid.strip(),
               AgentCompanyLink.device_id == device.device_id, AgentCompanyLink.is_active == True))).scalars().first()  # noqa: E712
    if link is not None:
        company_id = link.company_id
        link.is_active = None
        link.unlinked_at = get_ist_now()
        await db.commit()
        await alerts.company_unlinked(db, company_id)
    return {"unlinked": link is not None}
