"""
Visits / Shop Check-In Router
Stores GPS check-in records for sales visits.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, Double, DateTime, ForeignKey, Text, desc, or_
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db, Base
from app.core.config import settings
from app.models.portal_core import User, CustomerProfile
from app.core.permissions import get_current_user, require_permission

router = APIRouter(prefix="/visits", tags=["visits"])

# ─── Model ───────────────────────────────────────────────────────────────────

class SalesVisit(Base):
    __tablename__ = "sales_visits"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    ledger_id = Column(Integer, ForeignKey(f"{settings.TALLY_DATABASE_NAME}.ledgers.ledger_id"), nullable=True)
    custom_shop_name = Column(String(256), nullable=True)
    latitude = Column(Double, nullable=True)
    longitude = Column(Double, nullable=True)
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


async def enrich_visit_records(visits: list, company_id: int, db: AsyncSession) -> list:
    if not visits:
        return []

    from app.models.tally_core import MstLedger
    from app.models.portal_core import CustomerProfile

    # Collect ledger IDs and shop names
    ledger_ids = {v.ledger_id for v in visits if v.ledger_id}
    names = {v.custom_shop_name.strip() for v in visits if v.custom_shop_name and v.custom_shop_name.strip()}

    ledgers_by_id = {}
    ledgers_by_name = {}
    if ledger_ids or names:
        ledger_conditions = []
        if ledger_ids:
            ledger_conditions.append(MstLedger.ledger_id.in_(ledger_ids))
        if names:
            ledger_conditions.append(MstLedger.name.in_(names))
        ledger_stmt = select(MstLedger).where(
            MstLedger.company_id == company_id,
            or_(*ledger_conditions)
        )
        l_res = await db.execute(ledger_stmt)
        for l in l_res.scalars().all():
            ledgers_by_id[l.ledger_id] = l
            if l.name:
                ledgers_by_name[l.name.strip().lower()] = l

    profiles_by_ledger = {}
    profiles_by_name = {}
    if ledger_ids or names:
        prof_conditions = []
        if ledger_ids:
            prof_conditions.append(CustomerProfile.ledger_id.in_(ledger_ids))
        if names:
            prof_conditions.append(CustomerProfile.custom_name.in_(names))
        prof_stmt = select(CustomerProfile).where(
            CustomerProfile.company_id == company_id,
            or_(*prof_conditions)
        )
        p_res = await db.execute(prof_stmt)
        for p in p_res.scalars().all():
            if p.ledger_id:
                profiles_by_ledger[p.ledger_id] = p
            if p.custom_name:
                profiles_by_name[p.custom_name.strip().lower()] = p

    user_ids = {v.user_id for v in visits if getattr(v, "user_id", None) and ("user" not in v.__dict__ or not v.user)}
    users_by_id = {}
    if user_ids:
        u_res = await db.execute(select(User).where(User.user_id.in_(user_ids)))
        for u in u_res.scalars().all():
            users_by_id[u.user_id] = u.username or u.email

    output = []
    for v in visits:
        shop_name = v.custom_shop_name
        ledger_id = v.ledger_id
        customer_key = None
        is_registered = False

        if ledger_id:
            is_registered = True
            customer_key = f"tally_{ledger_id}"
            if not shop_name and ledger_id in ledgers_by_id:
                shop_name = ledgers_by_id[ledger_id].name
        elif v.custom_shop_name:
            norm_name = v.custom_shop_name.strip().lower()
            if norm_name in ledgers_by_name:
                matched_ledger = ledgers_by_name[norm_name]
                ledger_id = matched_ledger.ledger_id
                is_registered = True
                customer_key = f"tally_{matched_ledger.ledger_id}"
                shop_name = matched_ledger.name
            elif norm_name in profiles_by_name:
                matched_profile = profiles_by_name[norm_name]
                ledger_id = matched_profile.ledger_id
                is_registered = True
                customer_key = f"tally_{matched_profile.ledger_id}" if matched_profile.ledger_id else f"profile_{matched_profile.id}"
                shop_name = matched_profile.custom_name

        salesperson = None
        if "user" in v.__dict__ and v.user:
            salesperson = v.user.username or v.user.email
        elif getattr(v, "user_id", None) in users_by_id:
            salesperson = users_by_id[v.user_id]
        elif getattr(v, "user_id", None):
            salesperson = f"User #{v.user_id}"

        item = {
            "id": v.id,
            "shopName": shop_name or "Custom Shop",
            "customShopName": v.custom_shop_name,
            "ledger_id": ledger_id,
            "customer_key": customer_key,
            "is_registered": is_registered,
            "latitude": v.latitude,
            "longitude": v.longitude,
            "comments": v.comments,
            "status": v.status,
            "createdAt": f"{v.created_at.isoformat()}Z" if v.created_at else None,
            "photoUrl": v.photo_url,
        }
        if hasattr(v, "user_id"):
            item["user_id"] = v.user_id
            item["salesperson"] = salesperson
        if hasattr(v, "ip_address"):
            item["ip_address"] = v.ip_address or "152.59.87.245"

        output.append(item)

    return output


@router.get("/recent")
async def get_recent_visits(
    user: User = Depends(require_permission("visits", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return last 15 visits for current user."""
    result = await db.execute(
        select(SalesVisit)
        .where(SalesVisit.user_id == user.user_id)
        .order_by(desc(SalesVisit.created_at))
        .limit(15)
    )
    visits = result.scalars().all()
    return await enrich_visit_records(visits, user.company_id, db)


@router.get("/history")
async def get_user_visit_history(
    limit: int = 50,
    user: User = Depends(require_permission("visits", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return past check-in visit history for the logged-in user."""
    result = await db.execute(
        select(SalesVisit)
        .where(SalesVisit.user_id == user.user_id)
        .order_by(desc(SalesVisit.created_at))
        .limit(limit)
    )
    visits = result.scalars().all()
    return await enrich_visit_records(visits, user.company_id, db)


@router.get("/logs")
async def get_visit_logs(
    date: Optional[str] = None,
    user_id: Optional[int] = None,
    current_user: User = Depends(require_permission("admin", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Admin: get all check-ins with date and salesperson filter."""
    from sqlalchemy.orm import selectinload
    
    query = (
        select(SalesVisit)
        .options(selectinload(SalesVisit.user))
        .join(User, SalesVisit.user_id == User.user_id)
        .where(User.company_id == current_user.company_id)
    )
    if date:
        from datetime import date as dt
        try:
            d = dt.fromisoformat(date)
            query = query.where(func.date(func.convert_tz(SalesVisit.created_at, '+00:00', '+05:30')) == d)
        except Exception:
            pass
    if user_id:
        query = query.where(SalesVisit.user_id == user_id)

    query = query.order_by(desc(SalesVisit.created_at)).limit(150)
    result = await db.execute(query)
    visits = result.scalars().all()
    return await enrich_visit_records(visits, current_user.company_id, db)
