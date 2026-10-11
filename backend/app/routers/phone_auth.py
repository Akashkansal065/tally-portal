"""Sign in, and create an account, with a mobile number.

The app sends the OTP and confirms it with Firebase Authentication, then gives the server the ID token Firebase
handed back (app/services/firebase_auth.py checks it). A number that is already someone's signs that person in.
A number an admin has invited joins that admin's business (routers/team.py). Any other new number creates an
account: its first admin and a company that waits for its Tally company, which the Desktop Sync Agent links
later (see /agent/pair and _link_company in routers/agent.py).
"""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.account_roles import create_default_roles
from app.core.agent_auth import grant_sync_agent, needs_tally_setup
from app.core.config import settings
from app.core.database import get_db
from app.core.datetime_utils import get_ist_now
from app.core.permissions import get_current_user
from app.core.rate_limiter import limiter
from app.core.security import NO_PASSWORD
from app.core.sessions import create_user_session
from app.models.portal_core import Account, Company, User, UserCompanyAccess, UserPhone
from app.routers import team
from app.services import firebase_auth, messaging

logger = logging.getLogger("app.routers.phone_auth")
router = APIRouter(prefix="/auth/phone", tags=["Authentication"])


class PhoneTokenRequest(BaseModel):
    id_token: str = Field(min_length=20, max_length=4096)


class PhoneJoinRequest(PhoneTokenRequest):
    full_name: str = Field(min_length=1, max_length=50)
    token: Optional[str] = Field(default=None, max_length=200)   # the invitation link's, when joining from one


class PhoneRegisterRequest(PhoneTokenRequest):
    full_name: str = Field(min_length=1, max_length=50)
    business_name: str = Field(min_length=1, max_length=150)
    pincode: Optional[str] = Field(default=None, max_length=10)
    email: Optional[str] = Field(default=None, max_length=120)
    accept_terms: bool


async def _confirmed(id_token: str) -> firebase_auth.VerifiedPhone:
    try:
        return await firebase_auth.verify_phone_token(id_token)
    except firebase_auth.PhoneSignInOff:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Sign-in with a mobile number is not set up on this server.")
    except firebase_auth.PhoneTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def _user_of(db: AsyncSession, phone: str) -> Optional[User]:
    return (await db.execute(
        select(User).options(selectinload(User.role)).join(UserPhone, UserPhone.user_id == User.user_id)
        .where(UserPhone.phone == phone))).scalars().first()


async def _signed_in(db: AsyncSession, user: User, request: Request, phone: str) -> dict:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account has been deactivated. Contact your administrator.")
    if user.account_id is not None:
        account_status = (await db.execute(select(Account.status).where(Account.account_id == user.account_id))).scalar()
        if account_status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is closed.")
    setup = await needs_tally_setup(db, user)
    # Session with device details; refuses blocked devices, applies device limits (commits)
    access_token = await create_user_session(db, user, request)
    return {"registered": True, "access_token": access_token, "token_type": "bearer", "phone": phone,
            "needs_tally_setup": setup}


@router.get("/status")
async def phone_sign_in_status():
    """Whether this server takes mobile number sign-in, so the app can offer it or not."""
    return {"enabled": firebase_auth.enabled()}


@router.post("/login")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def phone_login(request: Request, response: Response, req: PhoneTokenRequest, db: AsyncSession = Depends(get_db)):
    """Sign in with a confirmed mobile number. A number nobody has signed up with answers registered: false,
    and the app then asks for the details /auth/phone/register needs."""
    confirmed = await _confirmed(req.id_token)
    user = await _user_of(db, confirmed.phone)
    if user is None:
        invite = await team.open_phone_invite(db, confirmed.phone)
        invited_to = None
        if invite is not None:
            invited_to = (await db.execute(select(Account.name).where(Account.account_id == invite.account_id))).scalar()
        # invite: the business this number has been invited to, which /auth/phone/join joins
        return {"registered": False, "phone": confirmed.phone, "invite": {"account_name": invited_to} if invited_to else None}
    return await _signed_in(db, user, request, confirmed.phone)


@router.post("/join")
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def phone_join(request: Request, response: Response, req: PhoneJoinRequest, db: AsyncSession = Depends(get_db)):
    """Join the business that invited this confirmed mobile number: the invitation that names the number,
    or with token, the one an emailed link is for. Whoever joins has proved the number is theirs, and it is
    what they sign in with from then on. Sent again once joined, it signs that person in."""
    confirmed = await _confirmed(req.id_token)
    existing = await _user_of(db, confirmed.phone)
    if existing is not None:
        if req.token:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This mobile number already has an account. Sign in with it.")
        return await _signed_in(db, existing, request, confirmed.phone)
    if not req.full_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter your name.")
    if req.token:
        invite = await team._open_invite(db, req.token)
        named = team.invite_phone(invite)
        if named and named != confirmed.phone:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="This invitation is for another mobile number. Confirm the number your admin invited.")
    else:
        invite = await team.open_phone_invite(db, confirmed.phone)
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="There is no invitation for this mobile number. Ask your admin to invite it.")
    try:
        # An emailed link shows the email is theirs; an email an admin typed beside a number does not
        await team.join_from_invite(db, invite, req.full_name, NO_PASSWORD, confirmed=confirmed, email_confirmed=bool(req.token))
        await db.commit()
    except IntegrityError:
        # The same request arrived twice at once and the other one won the number
        await db.rollback()
        existing = await _user_of(db, confirmed.phone)
        if existing is None:
            raise
        return await _signed_in(db, existing, request, confirmed.phone)
    return await _signed_in(db, await _user_of(db, confirmed.phone), request, confirmed.phone)


@router.post("/register")
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def phone_register(request: Request, response: Response, req: PhoneRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create an account for a confirmed mobile number: the account, its first admin and a company waiting for
    its Tally company, all or nothing. Sent again for a number that has an account, it signs that person in
    and creates nothing."""
    confirmed = await _confirmed(req.id_token)
    existing = await _user_of(db, confirmed.phone)
    if existing is not None:
        return await _signed_in(db, existing, request, confirmed.phone)

    full_name, business_name = req.full_name.strip(), req.business_name.strip()
    if not full_name or not business_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter your name and your business name.")
    if not req.accept_terms:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Accept the terms to create an account.")
    pincode = (req.pincode or "").strip() or None
    if pincode and not (pincode.isdigit() and len(pincode) == 6):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a 6-digit pin code.")
    # No email is kept as an empty one: the column takes no NULL, and nobody signs in with an empty email
    email = ""
    if (req.email or "").strip():
        email = (messaging.clean_email(req.email) or "").lower()
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email address, or leave it empty.")
        # Email sign-in finds a person by email, so two people can never share one
        if (await db.execute(select(User.user_id).where(func.lower(User.email) == email))).scalars().first() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="That email already has an account. Leave it empty, or sign in with email and password.")

    try:
        account = Account(name=business_name, status="active")
        db.add(account)
        await db.flush()
        admin_role = await create_default_roles(db, account.account_id)   # the account's own Admin and Sales roles
        # A user always has a company to be in. This one stands in until the first Tally company is linked.
        company = Company(account_id=account.account_id, name=business_name, pincode=pincode, awaiting_tally=True,
                          books_begin_date=date.today(), is_active=True)
        db.add(company)
        await db.flush()
        user = User(account_id=account.account_id, company_id=company.company_id, username=full_name, email=email,
                    phone=confirmed.phone, password_hash=NO_PASSWORD, role_id=admin_role.role_id, is_active=True,
                    ledger_scope="full", stock_scope="full")
        db.add(user)
        await db.flush()
        db.add(UserPhone(phone=confirmed.phone, user_id=user.user_id, firebase_uid=confirmed.uid, verified_at=get_ist_now()))
        db.add(UserCompanyAccess(user_id=user.user_id, company_id=company.company_id))
        account.created_by_user_id = user.user_id
        await grant_sync_agent(db, user.user_id, user.user_id, "Created the account with a mobile number")
        await db.commit()
    except IntegrityError:
        # The same sign-up arrived twice at once and the other one won the number
        await db.rollback()
        existing = await _user_of(db, confirmed.phone)
        if existing is None:
            raise
        return await _signed_in(db, existing, request, confirmed.phone)
    logger.info(f"Account #{account.account_id} '{account.name}' created with a mobile number.")
    user = await _user_of(db, confirmed.phone)
    return await _signed_in(db, user, request, confirmed.phone)


@router.post("/link")
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def link_phone(request: Request, response: Response, req: PhoneTokenRequest,
                     user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Let the signed-in person sign in with this confirmed mobile number from now on. It replaces a number
    they signed in with before."""
    confirmed = await _confirmed(req.id_token)
    owner = (await db.execute(select(UserPhone).where(UserPhone.phone == confirmed.phone))).scalars().first()
    if owner is not None and owner.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That mobile number already signs in someone else.")
    if owner is None:
        mine = (await db.execute(select(UserPhone).where(UserPhone.user_id == user.user_id))).scalars().first()
        if mine is None:
            db.add(UserPhone(phone=confirmed.phone, user_id=user.user_id, firebase_uid=confirmed.uid, verified_at=get_ist_now()))
        else:
            mine.phone, mine.firebase_uid, mine.verified_at = confirmed.phone, confirmed.uid, get_ist_now()
    target = await db.get(User, user.user_id)
    target.phone = confirmed.phone
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That mobile number already signs in someone else.")
    return {"phone": confirmed.phone}
