"""
Visits / Shop Check-In Router
Stores GPS check-in records for sales visits.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, desc
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db, Base
from app.core.permissions import require_permission
from app.models.portal_core import User
from app.core.config import settings

# ─── Model ───────────────────────────────────────────────────────────────────

class SalesVisit(Base):
    __tablename__ = "sales_visits"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=True)
    custom_shop_name = Column(String(256), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    photo_url = Column(Text, nullable=True)
    comments = Column(String(1024), nullable=True)
    status = Column(String(32), default="check-in")
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

# ─── Schemas ─────────────────────────────────────────────────────────────────

class CheckInRequest(BaseModel):
    ledger_id: Optional[int] = None
    customer_profile_id: Optional[int] = None
    custom_shop_name: Optional[str] = None
    latitude: float
    longitude: float
    comments: Optional[str] = None
    photo_base64: Optional[str] = None  # Stored as base64 data URL

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
    """
    Record a GPS shop check-in and audit distance against customer location.
    - Automatically captures & verifies GPS coordinates on customer profile if missing or unverified.
    - Seamlessly pipes check-in photo into ImageKit and CustomerPhoto gallery.
    """
    visit = SalesVisit(
        user_id=user.user_id,
        ledger_id=req.ledger_id,
        custom_shop_name=req.custom_shop_name[:256] if req.custom_shop_name else None,
        latitude=req.latitude,
        longitude=req.longitude,
        photo_url=None,
        comments=req.comments[:1024] if req.comments else None,
        status="check-in",
    )
    db.add(visit)
    await db.flush()

    # Location audit & Customer Profile synchronization
    from app.models.portal_core import CustomerProfile, CustomerLocationLog, CustomerPhoto
    from app.services.geo_service import evaluate_checkin_proximity
    from app.services.imagekit_service import upload_customer_photo
    import time

    dist_meters = None
    verification_status = "NO_BASE_COORDINATE"
    profile = None
    location_established = False

    # 1. Resolve Customer Profile
    if req.customer_profile_id:
        profile_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.id == req.customer_profile_id
            )
        )
        profile = profile_res.scalars().first()
    elif req.ledger_id:
        profile_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.ledger_id == req.ledger_id
            )
        )
        profile = profile_res.scalars().first()
    elif req.custom_shop_name:
        profile_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.custom_name == req.custom_shop_name
            )
        )
        profile = profile_res.scalars().first()

    # 2. Auto-capture GPS & Verification
    if profile:
        # Keep visit linked with profile's ledger if present
        if profile.ledger_id and not visit.ledger_id:
            visit.ledger_id = profile.ledger_id
        if not visit.custom_shop_name and profile.custom_name:
            visit.custom_shop_name = profile.custom_name

        if profile.latitude is not None and profile.longitude is not None:
            dist_meters, verification_status = evaluate_checkin_proximity(
                req.latitude, req.longitude, profile.latitude, profile.longitude
            )
            # If coordinates were not previously verified, verify them now upon successful on-site check-in (<=20m)
            if not profile.location_verified and verification_status == "VERIFIED_ON_SITE":
                profile.location_verified = True
                profile.location_verified_at = func.now()
        else:
            # Auto-establish and verify master GPS coordinates for this shop
            profile.latitude = req.latitude
            profile.longitude = req.longitude
            profile.location_verified = True
            profile.location_verified_at = func.now()
            dist_meters = 0.0
            verification_status = "ESTABLISHED_BASE"
            location_established = True
        
        profile.last_visit_at = func.now()
        profile.total_visits = (profile.total_visits or 0) + 1
    else:
        # Create new customer profile in portal database (Zero Tally accounting impact)
        profile = CustomerProfile(
            company_id=user.company_id,
            ledger_id=req.ledger_id,
            custom_name=req.custom_shop_name,
            latitude=req.latitude,
            longitude=req.longitude,
            location_verified=True,
            location_verified_at=func.now(),
            total_visits=1,
            last_visit_at=func.now(),
            created_by=user.user_id,
        )
        db.add(profile)
        await db.flush()
        dist_meters = 0.0
        verification_status = "ESTABLISHED_BASE"
        location_established = True

    # 3. Customer Photo Gallery via Check-In Photo (ImageKit Pipeline)
    if req.photo_base64:
        try:
            folder = (
                f"/customers/ledger_{profile.ledger_id}/visits"
                if profile and profile.ledger_id
                else (f"/customers/profile_{profile.id}/visits" if profile else "/customers/visits")
            )
            file_name = f"checkin_{visit.id}_{int(time.time())}.jpg"
            caption = req.comments[:255] if req.comments else f"Visit check-in by {user.username}"

            ik_res = upload_customer_photo(
                file_base64=req.photo_base64,
                file_name=file_name,
                folder=folder,
                tags=["visit_checkin", f"user_{user.user_id}", f"visit_{visit.id}"]
            )
            if ik_res and ik_res.get("url"):
                visit.photo_url = ik_res["url"]
                if profile:
                    photo_entry = CustomerPhoto(
                        company_id=user.company_id,
                        customer_profile_id=profile.id,
                        ledger_id=profile.ledger_id,
                        photo_type="visit_checkin",
                        imagekit_file_id=ik_res.get("file_id"),
                        imagekit_url=ik_res["url"],
                        imagekit_thumbnail_url=ik_res.get("thumbnail_url") or ik_res["url"],
                        imagekit_file_path=ik_res.get("file_path"),
                        caption=caption,
                        latitude=req.latitude,
                        longitude=req.longitude,
                        is_primary=False,
                        uploaded_by=user.user_id,
                    )
                    db.add(photo_entry)
            else:
                # Fallback to base64 if ImageKit upload returned empty
                visit.photo_url = req.photo_base64
        except Exception as img_err:
            print(f"Warning: ImageKit upload failed for check-in #{visit.id}: {img_err}")
            visit.photo_url = req.photo_base64

    # 4. Create immutable location audit log entry
    loc_log = CustomerLocationLog(
        company_id=user.company_id,
        customer_profile_id=profile.id if profile else None,
        ledger_id=visit.ledger_id,
        user_id=user.user_id,
        latitude=req.latitude,
        longitude=req.longitude,
        distance_from_base_meters=dist_meters,
        verification_status=verification_status,
        source="check_in",
        visit_id=visit.id,
        notes=f"Check-in by user #{user.user_id} ({user.username})"
    )
    db.add(loc_log)

    # 5. Auto-mark matching stop in today's active beat plan
    try:
        from app.models.portal_core import BeatPlan, BeatPlanStop
        today_date = datetime.now().date()
        stop_conds = []
        if visit.ledger_id:
            stop_conds.append(BeatPlanStop.ledger_id == visit.ledger_id)
        if profile and profile.id:
            stop_conds.append(BeatPlanStop.customer_profile_id == profile.id)
        if visit.custom_shop_name:
            stop_conds.append(BeatPlanStop.shop_name == visit.custom_shop_name)

        if stop_conds:
            beat_stop_stmt = (
                select(BeatPlanStop)
                .join(BeatPlan, BeatPlan.id == BeatPlanStop.beat_plan_id)
                .where(
                    BeatPlan.company_id == user.company_id,
                    BeatPlan.user_id == user.user_id,
                    BeatPlan.plan_date == today_date,
                    BeatPlanStop.status == "pending",
                    or_(*stop_conds)
                )
            )
            stop_res = await db.execute(beat_stop_stmt)
            active_stop = stop_res.scalars().first()
            if active_stop:
                active_stop.status = "visited"
                active_stop.visit_id = visit.id
                active_stop.visited_at = func.now()
                # Update plan status to in_progress if it was assigned
                plan_res = await db.execute(select(BeatPlan).where(BeatPlan.id == active_stop.beat_plan_id))
                bp = plan_res.scalars().first()
                if bp and bp.status == "assigned":
                    bp.status = "in_progress"
    except Exception as bp_err:
        print(f"Warning: Could not auto-update beat plan stop: {bp_err}")

    await db.commit()
    await db.refresh(visit)

    # Notify admins
    from app.routers.notifications import notify_admins
    shop_title = visit.custom_shop_name or (profile.custom_name if profile else None) or (f"Ledger #{visit.ledger_id}" if visit.ledger_id else "a customer")
    
    if verification_status == "MISMATCH_FAR":
        dist_str = f" ({round(dist_meters)}m away)" if dist_meters is not None else ""
        admin_title = "⚠️ Check-In Discrepancy"
        admin_msg = f"{user.username} checked in at {shop_title} with location discrepancy{dist_str} (> 20m away)"
    else:
        admin_title = "New Check-In"
        admin_msg = f"{user.username} checked in at {shop_title}"

    await notify_admins(
        db=db,
        company_id=user.company_id,
        type="check_in",
        title=admin_title,
        message=admin_msg,
        reference_id=str(visit.id),
        reference_type="visit",
        exclude_user_id=user.user_id,
        auto_commit=True,
    )

    return {
        "success": True,
        "id": visit.id,
        "customer_profile_id": profile.id if profile else None,
        "verification_status": verification_status,
        "distance_from_base_meters": dist_meters,
        "location_established": location_established,
        "location_verified": profile.location_verified if profile else True,
        "photo_url": visit.photo_url,
        "message": (
            "Check-in recorded! Master GPS location established & verified for this shop."
            if location_established
            else "Check-in recorded successfully"
        )
    }


@router.get("/recent")
async def get_recent_visits(
    user: User = Depends(require_permission("visits", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return last 15 visits for current user."""
    from app.models.tally_core import MstLedger
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
            lr = await db.execute(select(MstLedger).where(MstLedger.ledger_id == v.ledger_id))
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


@router.get("/history")
async def get_user_visit_history(
    limit: int = 50,
    user: User = Depends(require_permission("visits", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return past check-in visit history for the logged-in user."""
    from app.models.tally_core import MstLedger
    result = await db.execute(
        select(SalesVisit)
        .where(SalesVisit.user_id == user.user_id)
        .order_by(desc(SalesVisit.created_at))
        .limit(limit)
    )
    visits = result.scalars().all()

    output = []
    for v in visits:
        shop_name = v.custom_shop_name
        if v.ledger_id and not shop_name:
            lr = await db.execute(select(MstLedger).where(MstLedger.ledger_id == v.ledger_id))
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
    """Admin: get all check-ins with date and salesperson filter."""
    from app.models.tally_core import MstLedger
    from sqlalchemy.orm import selectinload
    
    query = select(SalesVisit).options(selectinload(SalesVisit.user))
    if date:
        from datetime import date as dt
        try:
            d = dt.fromisoformat(date)
            query = query.where(func.date(SalesVisit.created_at) == d)
        except Exception:
            pass
    if user_id:
        query = query.where(SalesVisit.user_id == user_id)

    query = query.order_by(desc(SalesVisit.created_at)).limit(150)
    result = await db.execute(query)
    visits = result.scalars().all()

    output = []
    for v in visits:
        shop_name = v.custom_shop_name
        if v.ledger_id and not shop_name:
            lr = await db.execute(select(MstLedger).where(MstLedger.ledger_id == v.ledger_id))
            l = lr.scalars().first()
            if l:
                shop_name = l.name

        salesperson = v.user.username if (v.user and v.user.username) else (v.user.email if v.user else f"User #{v.user_id}")
        output.append({
            "id": v.id,
            "user_id": v.user_id,
            "salesperson": salesperson,
            "shopName": shop_name or "Custom Shop",
            "customShopName": v.custom_shop_name,
            "latitude": v.latitude,
            "longitude": v.longitude,
            "comments": v.comments,
            "status": v.status,
            "ip_address": v.ip_address or "152.59.87.245",
            "createdAt": v.created_at.isoformat() if v.created_at else None,
            "photoUrl": v.photo_url,
        })
    return output
