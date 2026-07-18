from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta, timezone
import hashlib

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.core.permissions import get_current_user, oauth2_scheme
from app.core.seed import seed_company_defaults
from app.models.company import Company
from app.models.user import User, Role, UserSession
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
    books_begin_date: str  # YYYY-MM-DD
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
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format for books_begin_date. Use YYYY-MM-DD."
        )
        
    # 1. Create Company
    company = Company(
        name=req.company_name,
        books_begin_date=begin_date,
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
        show_ledger=True,
        show_stocks=True,
        show_reports=True,
        show_orders=True,
        show_check_in=True,
        show_sales_ledgers=True,
        show_purchase_ledgers=True,
        show_receipts=True,
        show_payments=True,
        show_expenses=True,
        show_attendance=True,
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
    return {
        "user_id": user.user_id,
        "company_id": user.company_id,
        "username": user.username,
        "email": user.email,
        "role": user.role.name if user.role else "sales",
        "is_active": user.is_active,
        "showLedger": user.show_ledger,
        "showSalesLedgers": user.show_sales_ledgers,
        "showPurchaseLedgers": user.show_purchase_ledgers,
        "showReceipts": user.show_receipts,
        "showPayments": user.show_payments,
        "showExpenses": user.show_expenses,
        "showStocks": user.show_stocks,
        "showReports": user.show_reports,
        "showOrders": user.show_orders,
        "showCheckIn": user.show_check_in,
        "ledgerScope": user.ledger_scope,
        "stockScope": user.stock_scope,
        "allowedStockGroups": user.allowed_stock_groups,
        "allowedLedgerGroups": user.allowed_ledger_groups,
        "allowedReportCategories": user.allowed_report_categories,
    }


from app.models.user import UserCompanyAccess
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

@router.get("/me/companies", response_model=list[MyCompanyResponse])
async def get_my_companies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = await db.execute(
        select(Company).join(UserCompanyAccess, Company.company_id == UserCompanyAccess.company_id)
        .where(UserCompanyAccess.user_id == user.user_id)
    )
    companies = list(query.scalars().all())
    
    primary_company_ids = {c.company_id for c in companies}
    if user.company_id not in primary_company_ids:
        comp_query = await db.execute(select(Company).where(Company.company_id == user.company_id))
        primary_comp = comp_query.scalars().first()
        if primary_comp:
            companies.append(primary_comp)
            
            # Heal database by creating the missing link
            access = UserCompanyAccess(user_id=user.user_id, company_id=user.company_id)
            db.add(access)
            await db.commit()
            
    return companies
