from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta, timezone, date
from typing import Optional
import hashlib

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.core.permissions import get_current_user, oauth2_scheme, get_user_permission_toggles
from app.core.seed import seed_company_defaults
from app.models.portal_core import Company
from app.models.portal_core import User, Role, UserSession
from app.schemas.user import UserLogin, Token, UserResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/auth", tags=["Authentication"])

_SYSTEM_BOOTSTRAPPED = None

@router.get("/bootstrap-status")
async def get_bootstrap_status(db: AsyncSession = Depends(get_db)):
    global _SYSTEM_BOOTSTRAPPED
    if _SYSTEM_BOOTSTRAPPED is True:
        return {"need_bootstrap": False}

    admin_role_query = await db.execute(select(Role.role_id).where(Role.name == "Admin"))
    admin_role_id = admin_role_query.scalars().first()
    if admin_role_id:
        admin_users_exist = await db.execute(select(User.user_id).where(User.role_id == admin_role_id).limit(1))
        has_admin = admin_users_exist.scalars().first() is not None
    else:
        has_admin = False

    if has_admin:
        _SYSTEM_BOOTSTRAPPED = True

    return {"need_bootstrap": not has_admin}

class RegisterCompanyRequest(BaseModel):
    company_name: str
    mailing_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    pincode: Optional[str] = None
    telephone: Optional[str] = None
    mobile: Optional[str] = None
    website: Optional[str] = None
    financial_year_start: Optional[str] = None # YYYY-MM-DD
    books_begin_date: str  # YYYY-MM-DD
    base_currency: Optional[str] = "INR"
    username: str
    email: str
    password: str

@router.post("/register-company", response_model=UserResponse)
async def register_company(
    req: RegisterCompanyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Security check: Determine if caller is an authorized Admin or if database is empty of Admins (bootstrap mode)
    is_admin_calling = False
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = decode_access_token(token)
            user_id_str = payload.get("sub")
            if user_id_str:
                user_id = int(user_id_str)
                user_query = await db.execute(select(User).where(User.user_id == user_id, User.is_active == True))
                user = user_query.scalars().first()
                if user:
                    role_query = await db.execute(select(Role).where(Role.role_id == user.role_id))
                    role = role_query.scalars().first()
                    if role and role.name == "Admin":
                        is_admin_calling = True
        except Exception:
            pass

    if not is_admin_calling:
        # If not called by a verified admin, registration is only allowed if no Admin users exist in the database
        admin_role_query = await db.execute(select(Role.role_id).where(Role.name == "Admin"))
        admin_role_id = admin_role_query.scalars().first()
        if admin_role_id:
            admin_users_exist = await db.execute(select(User.user_id).where(User.role_id == admin_role_id).limit(1))
            has_admin = admin_users_exist.scalars().first() is not None
        else:
            has_admin = False

        if has_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration is disabled. Only existing administrators can register new companies."
            )

    # Check if user already exists
    user_exists_query = await db.execute(select(User).where(User.email == req.email))
    if user_exists_query.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )
        
    try:
        begin_date = datetime.strptime(req.books_begin_date, "%Y-%m-%d").date()
        fy_start = datetime.strptime(req.financial_year_start, "%Y-%m-%d").date() if req.financial_year_start else begin_date
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD."
        )
        
    # 1. Create Company with full Tally Prime fields
    company = Company(
        name=req.company_name,
        address_line1=req.address_line1,
        address_line2=req.address_line2,
        state=req.state,
        country=req.country or "India",
        pincode=req.pincode,
        telephone=req.telephone,
        mobile=req.mobile,
        email=req.email,
        website=req.website,
        financial_year_start=fy_start,
        books_begin_date=begin_date,
        base_currency=req.base_currency or "INR",
        features={"maintain_accounts": True, "maintain_inventory": True, "enable_gst": False},
        is_active=True
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    
    # 2. Seed defaults for this company (Groups, Voucher Types)
    # We do this synchronously or we run the helper
    # Since SQLAlchemy connection is async, we can run seed defaults synchronously on the raw connection,
    # or write a simple async loop. In seed.py, we have seed_company_defaults which runs sync.
    # To run it in async, we can use db.run_sync
    def run_seeding(sync_session):
        seed_company_defaults(sync_session, company.company_id)
        
    await db.run_sync(run_seeding)
    
    # 3. Create Admin User
    role_query = await db.execute(select(Role).where(Role.name == "Admin"))
    admin_role = role_query.scalars().first()
    if not admin_role:
        # Fallback if roles weren't seeded
        admin_role = Role(name="Admin", description="Full access")
        db.add(admin_role)
        await db.commit()
        await db.refresh(admin_role)
        
    password_hash = get_password_hash(req.password)
    user = User(
        company_id=company.company_id,
        username=req.username,
        email=req.email,
        password_hash=password_hash,
        role_id=admin_role.role_id,
        is_active=True,
        ledger_scope='full',
        stock_scope='full'
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # 4. Grant user access to the newly registered company
    access = UserCompanyAccess(
        user_id=user.user_id,
        company_id=company.company_id
    )
    db.add(access)
    await db.commit()
    
    global _SYSTEM_BOOTSTRAPPED
    _SYSTEM_BOOTSTRAPPED = True
    
    return user

@router.post("/login", response_model=Token)
async def login(
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
        
    # Generate Token
    access_token = create_access_token(subject=user.user_id)
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    
    # Save session
    session = UserSession(
        user_id=user.user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1440)
    )
    db.add(session)
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/swagger-login", response_model=Token)
async def swagger_login(
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
        
    # Generate Token
    access_token = create_access_token(subject=user.user_id)
    token_hash = hashlib.sha256(access_token.encode()).hexdigest()
    
    # Save session
    session = UserSession(
        user_id=user.user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1440)
    )
    db.add(session)
    
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    
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
        session.revoked_at = datetime.now(timezone.utc)
        await db.commit()
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
    showReceipts: bool
    showPayments: bool
    showExpenses: bool
    showStocks: bool
    showReports: bool
    showOrders: bool
    showCheckIn: bool
    showGst: bool
    ledgerScope: str
    stockScope: str
    allowedStockGroups: Optional[str] = None
    allowedLedgerGroups: Optional[str] = None
    allowedReportCategories: Optional[str] = None

@router.get("/me", response_model=UserMeResponse)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Eagerly load role
    await db.refresh(user, ["role"])
    r_name = user.role.name if user.role else "User"
    toggles = await get_user_permission_toggles(user.user_id, user.role_id, r_name, db)
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
        "showReceipts": toggles["showReceipts"],
        "showPayments": toggles["showPayments"],
        "showExpenses": toggles["showExpenses"],
        "showStocks": toggles["showStocks"],
        "showReports": toggles["showReports"],
        "showOrders": toggles["showOrders"],
        "showCheckIn": toggles["showCheckIn"],
        "showGst": toggles["showGst"],
        "ledgerScope": user.ledger_scope,
        "stockScope": user.stock_scope,
        "allowedStockGroups": user.allowed_stock_groups,
        "allowedLedgerGroups": user.allowed_ledger_groups,
        "allowedReportCategories": user.allowed_report_categories,
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
        # Admins have global access to all registered companies
        if user.role and user.role.name.lower() == "admin":
            comp_check = await db.execute(select(Company).where(Company.company_id == payload.company_id))
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
        
    user.company_id = payload.company_id
    await db.commit()
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
    # Admin role can view and switch between all active companies
    if user.role and user.role.name.lower() == "admin":
        query = await db.execute(select(Company).where(Company.is_active == True))
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
