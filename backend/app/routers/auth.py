from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from sqlalchemy.future import select
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List, Dict, Any
import hashlib

from app.core.datetime_utils import get_ist_now
from app.core.database import get_db
from app.core.config import settings
from app.core.security import verify_password, get_password_hash
from app.core.permissions import (
    get_current_user, get_optional_current_user, is_admin_user, oauth2_scheme,
    get_all_user_permissions, get_user_permission_toggles, invalidate_auth_cache
)
from app.core.sessions import (
    create_user_session, revoke_sessions, forget_tokens, current_token_hash, session_to_dict,
    live_session_conditions
)
from app.core.rate_limiter import limiter
from app.core.agent_auth import needs_tally_setup
from app.models.portal_core import Company
from app.core.permissions import same_account_as_user
from app.models.portal_core import User, Role, UserSession, UserCompanyAccess
from app.schemas.user import UserLogin, Token, UserResponse
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["Authentication"])

GONE_SIGN_UP = "Create your account in the MyTally app with your mobile number. To join a business that already has one, ask its admin for an invitation."


@router.get("/bootstrap-status")
async def get_bootstrap_status():
    """Kept for app versions that still ask: nothing is ever set up from the login page any more."""
    return {"need_bootstrap": False}


@router.post("/register", status_code=status.HTTP_410_GONE)
@router.post("/register-company", status_code=status.HTTP_410_GONE)
async def register_company():
    """Registration from the web was the way in before accounts existed. An account is now created with a mobile
    number (POST /auth/phone/register), and people join one by invitation."""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=GONE_SIGN_UP)


@router.post("/login", response_model=Token)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    response: Response,
    req: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    user_query = await db.execute(select(User).where(User.email == req.email, User.is_active == True))
    user = user_query.scalars().first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
        
    # Session with device details; refuses blocked devices, applies device limits (commits)
    access_token = await create_user_session(db, user, request)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/swagger-login", response_model=Token)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def swagger_login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user_query = await db.execute(select(User).where(User.email == form_data.username, User.is_active == True))
    user = user_query.scalars().first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
        
    # Session with device details; refuses blocked devices, applies device limits (commits)
    access_token = await create_user_session(db, user, request)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session_query = await db.execute(
        select(UserSession).where(
            UserSession.user_id == user.user_id,
            UserSession.token_hash == token_hash,
            UserSession.revoked_at == None
        )
    )
    session = session_query.scalars().first()
    if session:
        revoked = await revoke_sessions(db, reason="logout", session_ids=[session.session_id])
        await db.commit()
        forget_tokens(revoked)
        return {"detail": "Successfully logged out"}
        
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Active session not found"
    )

class UserMeResponse(BaseModel):
    user_id: int
    company_id: int
    username: str
    email: str
    role: str
    is_active: bool
    showLedger: bool
    showSalesLedgers: bool
    showPurchaseLedgers: bool
    showVouchers: bool = False
    showReceipts: bool
    showPayments: bool
    showExpenses: bool
    showStocks: bool
    showReports: bool
    showOrders: bool
    showCheckIn: bool
    showAttendance: bool = True
    showGst: bool
    showCustomers: bool
    capabilities: Optional[dict] = None
    ledgerScope: str
    stockScope: str
    allowedStockGroups: Optional[str] = None
    allowedLedgerGroups: Optional[str] = None
    allowedReportCategories: Optional[str] = None
    voucherActionScope: str = "full"
    allowedVoucherTypeIds: Optional[List[int]] = None
    # The business has no Tally PC yet and this person can connect one: the app holds them at Connect Tally
    needs_tally_setup: bool = False

@router.get("/me", response_model=UserMeResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not user.role:
        await db.refresh(user, ["role"])
    r_name = user.role.name if user.role else "User"
    user_perms = await get_all_user_permissions(user.user_id, user.role_id, r_name, db)
    toggles = user_perms["toggles"]
    capabilities = user_perms["capabilities"]
    voucher_action_scope = user_perms["voucher_action_scope"]
    allowed_vt_ids = user_perms["allowed_voucher_type_ids"]

    return {
        "user_id": user.user_id,
        "company_id": user.company_id,
        "username": user.username,
        "email": user.email,
        "role": r_name,
        "is_active": user.is_active,
        "showLedger": toggles["showLedger"],
        "showSalesLedgers": toggles["showSalesLedgers"],
        "showPurchaseLedgers": toggles["showPurchaseLedgers"],
        "showVouchers": toggles.get("showVouchers", toggles["showReceipts"]),
        "showReceipts": toggles["showReceipts"],
        "showPayments": toggles["showPayments"],
        "showExpenses": toggles["showExpenses"],
        "showAttendance": toggles.get("showAttendance", True),
        "showStocks": toggles["showStocks"],
        "showReports": toggles["showReports"],
        "showOrders": toggles["showOrders"],
        "showCheckIn": toggles["showCheckIn"],
        "showGst": toggles["showGst"],
        "showCustomers": toggles.get("showCustomers", True),
        "capabilities": capabilities,
        "ledgerScope": user.ledger_scope,
        "stockScope": user.stock_scope,
        "allowedStockGroups": user.allowed_stock_groups,
        "allowedLedgerGroups": user.allowed_ledger_groups,
        "allowedReportCategories": user.allowed_report_categories,
        "voucherActionScope": voucher_action_scope,
        "allowedVoucherTypeIds": allowed_vt_ids,
        "needs_tally_setup": await needs_tally_setup(db, user),
    }


from app.models.portal_core import UserCompanyAccess
from pydantic import BaseModel

class SwitchCompanyRequest(BaseModel):
    company_id: int

@router.put("/me/active-company")
async def switch_active_company(
    payload: SwitchCompanyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify the user has access to this company
    query = await db.execute(
        select(UserCompanyAccess).where(
            UserCompanyAccess.user_id == user.user_id,
            UserCompanyAccess.company_id == payload.company_id
        )
    )
    access = query.scalars().first()
    
    if not access:
        from app.models.portal_core import Role
        # Admins have access to every company of their own account; another account's company does not exist to them
        if user.role and user.role.name.lower() == "admin":
            comp_check = await db.execute(select(Company).where(
                Company.company_id == payload.company_id, same_account_as_user(user.user_id)))
            if not comp_check.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target company does not exist."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this company."
            )
        
    # Explicit UPDATE: the request's user object may carry an X-Company-ID override as its loaded value,
    # in which case assigning the same id would not register as a change.
    await db.execute(update(User).where(User.user_id == user.user_id).values(company_id=payload.company_id))
    await db.commit()
    invalidate_auth_cache(user_id=user.user_id)
    return {"detail": "Active company switched successfully."}

class MyCompanyResponse(BaseModel):
    company_id: int
    name: str
    gstin: Optional[str] = None
    pan: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = None
    telephone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    financial_year_start: Optional[date] = None
    books_begin_date: Optional[date] = None

    class Config:
        from_attributes = True

@router.get("/me/companies", response_model=list[MyCompanyResponse])
async def get_my_companies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Admin role can view and switch between all active companies of its own account
    if user.role and user.role.name.lower() == "admin":
        query = await db.execute(select(Company).where(Company.is_active == True, same_account_as_user(user.user_id)))
        return list(query.scalars().all())

    # Non-admin users can view only companies explicitly granted in UserCompanyAccess
    query = await db.execute(
        select(Company).join(UserCompanyAccess, Company.company_id == UserCompanyAccess.company_id)
        .where(UserCompanyAccess.user_id == user.user_id, Company.is_active == True)
    )
    companies = list(query.scalars().all())
    
    if not companies:
        comp_query = await db.execute(select(Company).where(Company.company_id == user.company_id))
        primary_comp = comp_query.scalars().first()
        if primary_comp:
            companies.append(primary_comp)
            
    return companies


# ─── My devices (self-service) ───────────────────────────────────────────────

@router.get("/me/sessions")
async def list_my_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """The caller's signed-in devices, current device first."""
    now = get_ist_now()
    sessions = (await db.execute(
        select(UserSession).where(UserSession.user_id == user.user_id, *live_session_conditions(now))
    )).scalars().all()
    current = current_token_hash(request)
    items = [session_to_dict(s, current_token_hash=current, now=now) for s in sessions]
    items.sort(key=lambda d: (not d["is_current"], d["legacy"], -(datetime.fromisoformat(d["last_active_at"]).timestamp() if d["last_active_at"] else 0)))
    return items


async def _own_live_session(db: AsyncSession, user: User, session_id: int) -> UserSession:
    session = (await db.execute(
        select(UserSession).where(
            UserSession.session_id == session_id,
            UserSession.user_id == user.user_id,
            *live_session_conditions()
        )
    )).scalars().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device session not found.")
    return session


@router.post("/me/sessions/{session_id}/revoke")
async def revoke_my_session(
    session_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Sign out one of the caller's devices. Revoking the current device is the same as logging out."""
    session = await _own_live_session(db, user, session_id)
    is_current = session.token_hash == current_token_hash(request)
    revoked = await revoke_sessions(db, reason="logout" if is_current else "self_revoke", session_ids=[session.session_id])
    await db.commit()
    forget_tokens(revoked)
    return {"revoked": len(revoked), "was_current": is_current}


@router.post("/me/sessions/revoke-others")
async def revoke_my_other_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Sign out every device except the one making this request (for a lost or shared phone)."""
    current = current_token_hash(request)
    current_ids = (await db.execute(
        select(UserSession.session_id).where(UserSession.user_id == user.user_id, UserSession.token_hash == current)
    )).scalars().all()
    revoked = await revoke_sessions(db, reason="self_revoke", user_id=user.user_id, exclude_session_ids=current_ids)
    await db.commit()
    forget_tokens(revoked)
    return {"revoked": len(revoked)}

