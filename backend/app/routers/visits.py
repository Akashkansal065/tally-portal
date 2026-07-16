"""
Visits / Shop Check-In Router
Stores GPS check-in records for sales visits.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, desc
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db, Base
from app.core.permissions import require_permission
from app.models.user import User

# ─── Model ───────────────────────────────────────────────────────────────────

class SalesVisit(Base):
    __tablename__ = "sales_visits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey("ledgers.ledger_id"), nullable=True)
    custom_shop_name = Column(String(256), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    photo_url = Column(String(1024), nullable=True)
    comments = Column(String(1024), nullable=True)
    status = Column(String(32), default="check-in")
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

# ─── Schemas ─────────────────────────────────────────────────────────────────

class CheckInRequest(BaseModel):
    ledger_id: Optional[int] = None
    custom_shop_name: Optional[str] = None
    latitude: float
    longitude: float
    comments: Optional[str] = None
    photo_base64: Optional[str] = None  # Stored as URL if uploaded

class VisitResponse(BaseModel):
    id: int
    custom_shop_name: Optional[str]
    shop_name: Optional[str] = None
    latitude: Optional[float]
    longitude: Optional[float]
    comments: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/visits", tags=["Shop Check-In"])


@router.post("/check-in")
async def check_in(
    req: CheckInRequest,
    user: User = Depends(require_permission("visits", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Record a GPS shop check-in."""
    import base64, hashlib

    # Store photo as base64 hash reference if too large (skip actual upload for now)
    photo_url = None
    if req.photo_base64 and len(req.photo_base64) < 500_000:
        photo_url = f"checkin_{user.user_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    visit = SalesVisit(
        user_id=user.user_id,
        ledger_id=req.ledger_id,
        custom_shop_name=req.custom_shop_name[:256] if req.custom_shop_name else None,
        latitude=req.latitude,
        longitude=req.longitude,
        photo_url=photo_url,
        comments=req.comments[:1024] if req.comments else None,
        status="check-in",
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return {"success": True, "id": visit.id, "message": "Check-in recorded successfully"}


@router.get("/recent")
async def get_recent_visits(
    user: User = Depends(require_permission("visits", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return last 15 visits for current user."""
    from app.models.ledger import Ledger
    result = await db.execute(
        select(SalesVisit)
        .where(SalesVisit.user_id == user.user_id)
        .order_by(desc(SalesVisit.created_at))
        .limit(15)
    )
    visits = result.scalars().all()

    # Enrich with ledger names
    output = []
    for v in visits:
        shop_name = v.custom_shop_name
        if v.ledger_id and not shop_name:
            lr = await db.execute(select(Ledger).where(Ledger.ledger_id == v.ledger_id))
            l = lr.scalars().first()
            if l:
                shop_name = l.name
        output.append({
            "id": v.id,
            "shopName": shop_name,
            "customShopName": v.custom_shop_name,
            "latitude": v.latitude,
            "longitude": v.longitude,
            "comments": v.comments,
            "status": v.status,
            "createdAt": v.created_at.isoformat() if v.created_at else None,
            "photoUrl": v.photo_url,
        })
    return output


@router.get("/logs")
async def get_visit_logs(
    date: Optional[str] = None,
    user_id: Optional[int] = None,
    current_user: User = Depends(require_permission("admin", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Admin: get all check-ins for a date."""
    query = select(SalesVisit)
    if date:
        from datetime import date as dt
        d = dt.fromisoformat(date)
        query = query.where(
            func.date(SalesVisit.created_at) == d
        )
    if user_id:
        query = query.where(SalesVisit.user_id == user_id)
    query = query.order_by(desc(SalesVisit.created_at)).limit(100)
    result = await db.execute(query)
    return result.scalars().all()
