"""Admin → Invoice design: everything an invoice or statement PDF needs about the current company, in one call.
Company details come from the company profile; logo, signature, bank details and declaration from company_branding."""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.portal_core import AuditLog, Company, CompanyBranding, User
from app.routers.admin import require_admin

router = APIRouter(prefix="/branding", tags=["Invoice design"])

DEFAULT_DECLARATION = ("We declare that this invoice shows the actual price of the goods described and that all particulars "
                       "are true and correct.")
IMAGE_PATTERN = re.compile(r"^data:image/(png|jpeg);base64,[A-Za-z0-9+/=]+$")
MAX_LOGO_CHARS = 420_000  # about 300 KB of image
MAX_SIGNATURE_CHARS = 210_000  # about 150 KB


class BrandingIn(BaseModel):
    # Images: a data URL to set, "" to remove, None to leave as is
    logo: Optional[str] = None
    signature: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_branch: Optional[str] = None
    declaration: Optional[str] = None
    show_upi_qr: Optional[bool] = None


def _image(value: str, limit: int, label: str) -> Optional[str]:
    if value == "":
        return None
    if not IMAGE_PATTERN.match(value):
        raise HTTPException(status_code=422, detail=f"The {label} must be a PNG or JPEG image.")
    if len(value) > limit:
        raise HTTPException(status_code=422, detail=f"The {label} is too large; use a smaller image.")
    return value


def _clean(value: Optional[str], length: int) -> Optional[str]:
    value = (value or "").strip()
    return value[:length] or None


async def branding_for(db: AsyncSession, company_id: int) -> dict:
    company = (await db.execute(select(Company).where(Company.company_id == company_id))).scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    row = (await db.execute(select(CompanyBranding).where(CompanyBranding.company_id == company_id))).scalars().first()
    features = company.features if isinstance(company.features, dict) else {}
    upi = (features.get("upi_id") or features.get("upi_vpa") or "").strip() or None
    return {
        "company": {
            "name": company.name,
            "address_lines": [line for line in (company.address_line1, company.address_line2) if line and line.strip()],
            "state": company.state, "pincode": company.pincode,
            "phone": company.mobile or company.telephone, "email": company.email, "website": company.website,
            "gstin": company.gstin, "pan": company.pan, "upi_id": upi,
        },
        "logo": row.logo if row else None,
        "signature": row.signature if row else None,
        "bank": {
            "account_name": (row.bank_account_name if row else None) or None,
            "bank_name": row.bank_name if row else None,
            "account_no": row.bank_account_no if row else None,
            "ifsc": row.bank_ifsc if row else None,
            "branch": row.bank_branch if row else None,
        },
        "declaration": (row.declaration if row and row.declaration else DEFAULT_DECLARATION),
        "show_upi_qr": row.show_upi_qr if row else True,
    }


@router.get("")
async def get_branding(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await branding_for(db, user.company_id)


@router.put("")
async def update_branding(req: BrandingIn, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(CompanyBranding).where(CompanyBranding.company_id == user.company_id))).scalars().first()
    if not row:
        row = CompanyBranding(company_id=user.company_id, show_upi_qr=True)
        db.add(row)
    if req.logo is not None:
        row.logo = _image(req.logo, MAX_LOGO_CHARS, "logo")
    if req.signature is not None:
        row.signature = _image(req.signature, MAX_SIGNATURE_CHARS, "signature")
    for field, length in (("bank_account_name", 150), ("bank_name", 150), ("bank_account_no", 40), ("bank_ifsc", 20), ("bank_branch", 150)):
        value = getattr(req, field)
        if value is not None:
            setattr(row, field, _clean(value, length))
    if row.bank_ifsc:
        row.bank_ifsc = row.bank_ifsc.upper()
    if req.declaration is not None:
        row.declaration = _clean(req.declaration, 1000)
    if req.show_upi_qr is not None:
        row.show_upi_qr = req.show_upi_qr
    row.updated_by_user_id = user.user_id
    db.add(AuditLog(company_id=user.company_id, user_id=user.user_id, action="UPDATE", entity_type="Branding",
                    entity_id=user.company_id, new_value={"fields": [k for k, v in req.model_dump().items() if v is not None]}))
    await db.commit()
    return await branding_for(db, user.company_id)
