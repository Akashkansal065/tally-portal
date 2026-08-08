from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date

from app.core.database import get_db
from app.core.security import decode_access_token, get_password_hash
from app.core.permissions import get_current_user
from app.models.portal_core import Company, FinancialYear
from app.models.portal_core import User, Role, UserCompanyAccess
from app.schemas.user import UserResponse

router = APIRouter(prefix="/companies", tags=["Companies"])

class CompanyFeaturesUpdate(BaseModel):
    features: dict

class CompanyCreate(BaseModel):
    name: str
    mailing_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    pincode: Optional[str] = None
    telephone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    financial_year_start: str  # YYYY-MM-DD
    books_begin_date: str # YYYY-MM-DD
    base_currency: Optional[str] = "INR"
    
    # User creation fields (Optional, required only if no auth token is provided)
    username: Optional[str] = None
    user_email: Optional[str] = None
    password: Optional[str] = None

class CompanyResponse(BaseModel):
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
    base_currency: Optional[str] = "INR"
    features: Optional[dict] = None
    is_active: bool

    class Config:
        from_attributes = True

@router.post("", response_model=CompanyResponse)
async def create_company(
    req: CompanyCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Determine if a user is currently logged in
    current_user_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = decode_access_token(token)
            if payload and payload.get("sub"):
                current_user_id = int(payload.get("sub"))
        except Exception:
            pass

    # If not logged in, ensure user fields are provided
    if not current_user_id:
        if not req.username or not req.user_email or not req.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide username, user_email, and password for initial registration."
            )
        # Check if email already exists
        user_exists_query = await db.execute(select(User).where(User.email == req.user_email))
        if user_exists_query.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists."
            )

    try:
        fy_start = datetime.strptime(req.financial_year_start, "%Y-%m-%d").date()
        books_begin = datetime.strptime(req.books_begin_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD."
        )

    # 1. Create Company
    company = Company(
        name=req.name,
        address_line1=req.address_line1,
        address_line2=req.address_line2,
        state=req.state,
        country=req.country,
        pincode=req.pincode,
        telephone=req.telephone,
        mobile=req.mobile,
        email=req.email,
        website=req.website,
        financial_year_start=fy_start,
        books_begin_date=books_begin,
        base_currency=req.base_currency,
        features={"maintain_accounts": True, "maintain_inventory": True, "enable_gst": False},
        is_active=True
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)

    # Seed defaults (Voucher types, groups)
    from app.services.seed import seed_company_defaults
    def run_seeding(sync_session):
        seed_company_defaults(sync_session, company.company_id)
    await db.run_sync(run_seeding)

    # 2. Create or link user
    if not current_user_id:
        role_query = await db.execute(select(Role).where(Role.name == "Admin"))
        admin_role = role_query.scalars().first()
        if not admin_role:
            admin_role = Role(name="Admin", description="Full access")
            db.add(admin_role)
            await db.commit()
            await db.refresh(admin_role)
            
        password_hash = get_password_hash(req.password)
        user = User(
            company_id=company.company_id, # Default company
            username=req.username,
            email=req.user_email,
            password_hash=password_hash,
            role_id=admin_role.role_id,
            is_active=True,
            ledger_scope='full',
            stock_scope='full'
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        current_user_id = user.user_id

    # 3. Grant access
    access = UserCompanyAccess(
        user_id=current_user_id,
        company_id=company.company_id
    )
    db.add(access)
    await db.commit()

    return company


@router.get("", response_model=List[CompanyResponse])
async def list_companies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all companies the current user has access to."""
    stmt = (
        select(Company)
        .join(UserCompanyAccess, UserCompanyAccess.company_id == Company.company_id)
        .where(UserCompanyAccess.user_id == user.user_id)
        .order_by(Company.name)
    )
    res = await db.execute(stmt)
    return res.scalars().all()


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    mailing_name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    telephone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    financial_year_start: Optional[str] = None
    books_begin_date: Optional[str] = None

@router.put("/{company_id}/features", response_model=CompanyResponse)
async def update_company_features(
    company_id: int,
    req: CompanyFeaturesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update features for a specific company."""
    # Check access
    access_query = await db.execute(
        select(UserCompanyAccess)
        .where(UserCompanyAccess.user_id == user.user_id, UserCompanyAccess.company_id == company_id)
    )
    if not access_query.scalars().first():
        raise HTTPException(status_code=403, detail="Not authorized to access this company.")
        
    company_query = await db.execute(select(Company).where(Company.company_id == company_id))
    company = company_query.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
        
    # Merge existing features with new features
    current_features = company.features or {}
    current_features.update(req.features)
    
    company.features = current_features
    await db.commit()
    await db.refresh(company)
    
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    req: CompanyUpdate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update company profile details. Restricted to Admin users only."""
    # 1. Admin Role Restriction
    if not user.role or user.role.name.lower() not in ("admin", "owner", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin users are permitted to edit company details."
        )

    # 2. Access Authorization
    access_query = await db.execute(
        select(UserCompanyAccess).where(
            UserCompanyAccess.user_id == user.user_id,
            UserCompanyAccess.company_id == company_id
        )
    )
    if not access_query.scalars().first():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this company.")

    company_query = await db.execute(select(Company).where(Company.company_id == company_id))
    company = company_query.scalars().first()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    # 3. Update Fields
    if req.name is not None: company.name = req.name
    if req.address_line1 is not None: company.address_line1 = req.address_line1
    if req.address_line2 is not None: company.address_line2 = req.address_line2
    if req.state is not None: company.state = req.state
    if req.country is not None: company.country = req.country
    if req.pincode is not None: company.pincode = req.pincode
    if req.telephone is not None: company.telephone = req.telephone
    if req.mobile is not None: company.mobile = req.mobile
    if req.email is not None: company.email = req.email
    if req.website is not None: company.website = req.website
    if req.gstin is not None: company.gstin = req.gstin
    if req.pan is not None: company.pan = req.pan

    if req.financial_year_start:
        try:
            company.financial_year_start = datetime.strptime(req.financial_year_start, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid financial_year_start format. Use YYYY-MM-DD.")

    if req.books_begin_date:
        try:
            company.books_begin_date = datetime.strptime(req.books_begin_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid books_begin_date format. Use YYYY-MM-DD.")

    # 4. Queue Outbound Sync Item for Tally Prime
    from app.models.portal_core import SyncQueue
    sync_item = SyncQueue(
        company_id=company_id,
        record_type="Company",
        record_id=company_id,
        action="Update",
        is_processed=False
    )
    db.add(sync_item)

    await db.commit()
    await db.refresh(company)

    # 5. Evict Cache & trigger background sync to Tally Prime immediately
    from app.core.cache import clear_company_cache
    clear_company_cache(company_id)

    from app.routers.sync import run_once_sync_background
    background_tasks.add_task(run_once_sync_background, user.user_id)

    return company
