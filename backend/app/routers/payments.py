import uuid
import urllib.parse
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.portal_core import User, Company
from app.models.tally_core import TrnVoucher, TrnPaymentLink, TrnAccounting, TrnBankAllocation

router = APIRouter(prefix="/payments", tags=["Payments & Connected Banking"])

class GeneratePaylinkRequest(BaseModel):
    voucher_id: int
    upi_vpa: Optional[str] = None
    merchant_name: Optional[str] = None
    amount: Optional[float] = None
    note: Optional[str] = None

class PaylinkResponse(BaseModel):
    paylink_id: int
    voucher_id: int
    link_id: str
    payment_url: str
    upi_uri: str
    amount: float
    payment_mode: str
    status: str
    bank_operation_ref: Optional[str] = None
    bank_portal_ref: Optional[str] = None
    created_at: datetime
    settled_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.post("/generate-link", response_model=PaylinkResponse)
async def generate_payment_link(
    req: GeneratePaylinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate dynamic UPI payment link and Tally Prime 7.0 Paylink for an invoice.
    """
    v_stmt = select(TrnVoucher).options(
        selectinload(TrnVoucher.payment_links),
        selectinload(TrnVoucher.voucher_type)
    ).where(
        TrnVoucher.voucher_id == req.voucher_id,
        TrnVoucher.company_id == user.company_id
    )
    voucher = (await db.execute(v_stmt)).scalars().first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Voucher not found.")

    comp_stmt = select(Company).where(Company.company_id == user.company_id)
    company = (await db.execute(comp_stmt)).scalars().first()
    company_name = req.merchant_name or (company.name if company else "Merchant")
    
    # UPI VPA fallback: Request -> Company features -> Settings -> Default
    company_upi = None
    if company and company.features and isinstance(company.features, dict):
        company_upi = company.features.get("upi_id") or company.features.get("upi_vpa")
        
    vpa = req.upi_vpa or company_upi or settings.DEFAULT_UPI_VPA or ""
    amount_to_pay = Decimal(str(req.amount)) if req.amount else voucher.total_amount
    note = req.note or f"Invoice {voucher.voucher_number}"
    
    # Build standard NPCI UPI URI
    params = {
        "pa": vpa,
        "pn": company_name,
        "am": f"{float(amount_to_pay):.2f}",
        "cu": "INR",
        "tn": note
    }
    upi_uri = f"upi://pay?{urllib.parse.urlencode(params)}"
    
    link_id = f"PL-{voucher.voucher_id}-{uuid.uuid4().hex[:8].upper()}"
    portal_payment_url = f"https://pay.mytally.in/{link_id}"

    # Check if existing pending link
    existing_link = next((pl for pl in voucher.payment_links if pl.status == "PENDING"), None)
    if existing_link:
        existing_link.upi_uri = upi_uri
        existing_link.amount = amount_to_pay
        existing_link.payment_url = portal_payment_url
        await db.commit()
        await db.refresh(existing_link)
        return existing_link

    paylink = TrnPaymentLink(
        voucher_id=voucher.voucher_id,
        company_id=user.company_id,
        link_id=link_id,
        payment_url=portal_payment_url,
        upi_uri=upi_uri,
        amount=amount_to_pay,
        payment_mode="UPI / NetBanking",
        status="PENDING"
    )
    db.add(paylink)
    await db.commit()
    await db.refresh(paylink)
    return paylink

@router.get("/{voucher_id}/paylink", response_model=Optional[PaylinkResponse])
async def get_voucher_paylink(
    voucher_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get active payment link and e-banking reconciliation status for a voucher.
    """
    pl_stmt = select(TrnPaymentLink).where(
        TrnPaymentLink.voucher_id == voucher_id,
        TrnPaymentLink.company_id == user.company_id
    ).order_by(TrnPaymentLink.created_at.desc())
    
    link = (await db.execute(pl_stmt)).scalars().first()
    return link
