from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, desc, and_, Date, Boolean, JSON, Index
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import asyncio
import base64
import time
import urllib.request
import urllib.parse
import json
import math
import calendar
import io

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.core.database import get_db, Base
from app.core.tenancy import rows_of_account, users_of_account
from app.core.permissions import require_permission
from app.services.notifications import TEAM_ATTENDANCE_LINK, attendance_approval_link, my_attendance_link
from app.models.portal_core import User, Role, Company
from app.core.config import settings
from app.core.datetime_utils import IST, get_ist_now, get_ist_date, to_ist_iso


# ─── Models ───────────────────────────────────────────────────────────────────

class OfficeLocation(Base):
    __tablename__ = "portal_office_locations"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.companies.company_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    address = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_meters = Column(Integer, default=200, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Attendance(Base):
    __tablename__ = "portal_attendance"
    __table_args__ = (
        Index("ix_portal_attendance_user_checkin", "user_id", "check_in_time"),
        Index("ix_portal_attendance_account", "account_id"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, index=True)
    # Attendance belongs to the account, not to one company: a person clocks in once a day. Not read yet.
    account_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.accounts.account_id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False)
    check_in_time = Column(DateTime, nullable=False, server_default=func.now())
    check_out_time = Column(DateTime, nullable=True)
    check_in_latitude = Column(String(32), nullable=True)
    check_in_longitude = Column(String(32), nullable=True)
    check_out_latitude = Column(String(32), nullable=True)
    check_out_longitude = Column(String(32), nullable=True)
    check_in_photo_url = Column(String(1024), nullable=True)
    check_out_photo_url = Column(String(1024), nullable=True)
    check_in_comments = Column(String(1024), nullable=True)
    check_out_comments = Column(String(1024), nullable=True)
    check_in_ip_address = Column(String(64), nullable=True)
    check_out_ip_address = Column(String(64), nullable=True)
    check_in_device_fingerprint = Column(String(1024), nullable=True)
    check_out_device_fingerprint = Column(String(1024), nullable=True)
    is_auto_punch_out = Column(Boolean, default=False, nullable=True)
    auto_punch_out_reason = Column(String(64), nullable=True)
    warning_notification_sent_at = Column(DateTime, nullable=True)
    midnight_warning_sent_at = Column(DateTime, nullable=True)
    
    check_in_location_tag = Column(String(128), nullable=True)
    check_in_distance_meters = Column(Float, nullable=True)
    check_in_office_id = Column(Integer, nullable=True)
    check_in_accuracy_meters = Column(Float, nullable=True)
    check_in_place_name = Column(String(256), nullable=True)
    check_out_location_tag = Column(String(128), nullable=True)
    check_out_distance_meters = Column(Float, nullable=True)
    check_out_office_id = Column(Integer, nullable=True)
    check_out_accuracy_meters = Column(Float, nullable=True)
    check_out_place_name = Column(String(256), nullable=True)

    # Periodic Location Tracking ("Last Known Location")
    last_known_latitude = Column(String(32), nullable=True)
    last_known_longitude = Column(String(32), nullable=True)
    last_known_accuracy_meters = Column(Float, nullable=True)
    last_known_place_name = Column(String(256), nullable=True)
    last_known_time = Column(DateTime, nullable=True)
    movement_trail = Column(JSON, nullable=True)  # legacy: no longer written; portal_attendance_locations is the trail

    # Approvals Workflow
    approval_status = Column(String(32), default="approved", nullable=False)
    is_out_of_office = Column(Boolean, default=False, nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String(512), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_user_id], lazy="selectin")


class AttendanceLocationLog(Base):
    __tablename__ = "portal_attendance_locations"
    __table_args__ = (
        Index("ix_attendance_locations_latest", "attendance_id", "recorded_at"),
        Index("ix_attendance_locations_account", "account_id"),
        {"schema": settings.PORTAL_DATABASE_NAME},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    account_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.accounts.account_id", ondelete="SET NULL"), nullable=True)
    attendance_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.portal_attendance.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey(f"{settings.PORTAL_DATABASE_NAME}.users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    latitude = Column(String(32), nullable=False)
    longitude = Column(String(32), nullable=False)
    accuracy_meters = Column(Float, nullable=True)
    distance_from_prev_meters = Column(Float, nullable=True)
    place_name = Column(String(256), nullable=True)
    recorded_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    attendance = relationship("Attendance", backref="location_logs")
    user = relationship("User", foreign_keys=[user_id])

# ─── Schemas ─────────────────────────────────────────────────────────────────

class AttendanceApprovalDecision(BaseModel):
    reason: Optional[str] = None


class BulkApprovalRequest(BaseModel):
    attendance_ids: List[int]


class LocationPingRequest(BaseModel):
    latitude: float
    longitude: float
    accuracyMeters: Optional[float] = None


class PunchRequest(BaseModel):
    type: str # "in" or "out"
    latitude: float
    longitude: float
    accuracyMeters: Optional[float] = None
    deviceFingerprint: str
    photoBase64: str
    comments: Optional[str] = None


class OfficeLocationCreate(BaseModel):
    name: str
    address: Optional[str] = None
    latitude: float
    longitude: float
    radius_meters: Optional[int] = 200


class OfficeLocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_meters: Optional[int] = None
    is_active: Optional[bool] = None


# ─── Geofencing & Distance Helpers ──────────────────────────────────────────

def reverse_geocode_place(lat: float, lon: float) -> Optional[str]:
    """Best-effort reverse geocode via OpenStreetMap Nominatim to get nearest place name."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        req = urllib.request.Request(url, headers={"User-Agent": "MyTally/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            # Try to get the most specific place name
            name = data.get("name")
            if name:
                return name[:256]
            addr = data.get("address", {})
            # Fallback: use the most specific address component
            for key in ["shop", "amenity", "building", "road", "neighbourhood", "suburb"]:
                if addr.get(key):
                    return addr[key][:256]
            display = data.get("display_name", "")
            return display[:256] if display else None
    except Exception:
        return None


# Nominatim's usage policy allows at most 1 request/second per application
NOMINATIM_MIN_INTERVAL_SECONDS = 1.0
_geocode_lock = asyncio.Lock()
_last_geocode_at = 0.0

async def reverse_geocode_place_async(lat: float, lon: float, skip_if_busy: bool = False) -> Optional[str]:
    """Runs the blocking Nominatim lookup off the event loop, throttled to one request per second.
    skip_if_busy returns None instead of queueing behind another lookup (for frequent background pings)."""
    global _last_geocode_at
    if skip_if_busy and _geocode_lock.locked():
        return None
    async with _geocode_lock:
        wait = NOMINATIM_MIN_INTERVAL_SECONDS - (time.monotonic() - _last_geocode_at)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            return await asyncio.to_thread(reverse_geocode_place, lat, lon)
        finally:
            _last_geocode_at = time.monotonic()

def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes Great-Circle distance in meters between two coordinates."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def resolve_location_tag(lat: Optional[float], lon: Optional[float], offices: List[OfficeLocation]) -> tuple[str, Optional[float], Optional[int]]:
    """Resolves whether a punch coordinate is inside an office geofence or remote."""
    if lat is None or lon is None:
        return ("No GPS", None, None)
    if not offices:
        return ("Remote / Field", None, None)

    closest_office = None
    min_dist = float("inf")
    for off in offices:
        if not off.is_active:
            continue
        dist = haversine_distance_meters(lat, lon, off.latitude, off.longitude)
        if dist < min_dist:
            min_dist = dist
            closest_office = off

    if not closest_office or min_dist == float("inf"):
        return ("Remote / Field", None, None)

    dist_rounded = round(min_dist, 1)
    if min_dist <= closest_office.radius_meters:
        tag = f"In Office: {closest_office.name}"
    else:
        if min_dist >= 1000:
            dist_str = f"{min_dist / 1000:.1f} km"
        else:
            dist_str = f"{int(min_dist)}m"
        tag = f"Outside Radius ({dist_str} from {closest_office.name})"
    return (tag, dist_rounded, closest_office.id)


# Helper upload
def upload_image_to_imagekit(file_base64: str, file_name: str) -> Optional[str]:
    if not settings.IMAGEKIT_PRIVATE_KEY:
        return None
    try:
        if ',' in file_base64:
            file_base64 = file_base64.split(',', 1)[1]
            
        url = "https://upload.imagekit.io/api/v1/files/upload"
        auth_str = f"{settings.IMAGEKIT_PRIVATE_KEY}:"
        auth_header = base64.b64encode(auth_str.encode()).decode()
        
        data = urllib.parse.urlencode({
            "file": file_base64,
            "fileName": file_name,
            "folder": "/attendance"
        }).encode('utf-8')
        
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            return res_data.get("url")
    except Exception as e:
        print("ImageKit upload exception:", e)
    return None


# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/attendance", tags=["Attendance"])


# ─── Office Locations Endpoints ──────────────────────────────────────────────

@router.get("/offices")
async def list_office_locations(
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    """Lists configured office locations / geofences for the user's company."""
    stmt = (
        select(OfficeLocation)
        .where(OfficeLocation.company_id == user.company_id)
        .order_by(OfficeLocation.name.asc())
    )
    res = await db.execute(stmt)
    offices = res.scalars().all()
    return {
        "success": True,
        "offices": [
            {
                "id": o.id,
                "name": o.name,
                "address": o.address,
                "latitude": o.latitude,
                "longitude": o.longitude,
                "radiusMeters": o.radius_meters,
                "isActive": o.is_active,
                "createdAt": to_ist_iso(o.created_at) if o.created_at else None,
            }
            for o in offices
        ]
    }


@router.post("/offices")
async def create_office_location(
    req: OfficeLocationCreate,
    user: User = Depends(require_permission("attendance", "create")),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new office geofence location for attendance tagging."""
    office = OfficeLocation(
        company_id=user.company_id,
        name=req.name.strip(),
        address=req.address.strip() if req.address else None,
        latitude=req.latitude,
        longitude=req.longitude,
        radius_meters=req.radius_meters or 200,
        is_active=True,
    )
    db.add(office)
    await db.commit()
    await db.refresh(office)
    return {
        "success": True,
        "message": f"Office location '{office.name}' created successfully.",
        "office": {
            "id": office.id,
            "name": office.name,
            "address": office.address,
            "latitude": office.latitude,
            "longitude": office.longitude,
            "radiusMeters": office.radius_meters,
            "isActive": office.is_active,
        }
    }


@router.put("/offices/{office_id}")
async def update_office_location(
    office_id: int,
    req: OfficeLocationUpdate,
    user: User = Depends(require_permission("attendance", "update")),
    db: AsyncSession = Depends(get_db)
):
    """Updates an existing office location / geofence radius."""
    stmt = select(OfficeLocation).where(
        OfficeLocation.id == office_id,
        OfficeLocation.company_id == user.company_id
    )
    res = await db.execute(stmt)
    office = res.scalars().first()
    if not office:
        raise HTTPException(status_code=404, detail="Office location not found")

    if req.name is not None:
        office.name = req.name.strip()
    if req.address is not None:
        office.address = req.address.strip() if req.address else None
    if req.latitude is not None:
        office.latitude = req.latitude
    if req.longitude is not None:
        office.longitude = req.longitude
    if req.radius_meters is not None:
        office.radius_meters = req.radius_meters
    if req.is_active is not None:
        office.is_active = req.is_active

    await db.commit()
    return {"success": True, "message": "Office location updated successfully."}


@router.delete("/offices/{office_id}")
async def delete_office_location(
    office_id: int,
    user: User = Depends(require_permission("attendance", "delete")),
    db: AsyncSession = Depends(get_db)
):
    """Deletes an office location."""
    stmt = select(OfficeLocation).where(
        OfficeLocation.id == office_id,
        OfficeLocation.company_id == user.company_id
    )
    res = await db.execute(stmt)
    office = res.scalars().first()
    if not office:
        raise HTTPException(status_code=404, detail="Office location not found")

    await db.delete(office)
    await db.commit()
    return {"success": True, "message": "Office location deleted."}


# ─── Attendance Core Endpoints ───────────────────────────────────────────────

@router.get("/today")
async def get_today_attendance(
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Attendance)
        .options(selectinload(Attendance.approved_by))
        .where(Attendance.user_id == user.user_id)
        .order_by(desc(Attendance.check_in_time))
        .limit(1)
    )
    res = await db.execute(stmt)
    latest = res.scalars().first()
    
    if not latest:
        return {"success": True, "attendance": None}
        
    # Helper to serialize record
    def serialize_att(rec: Attendance):
        return {
            "id": rec.id,
            "userId": rec.user_id,
            "checkInTime": to_ist_iso(rec.check_in_time),
            "checkOutTime": to_ist_iso(rec.check_out_time) if rec.check_out_time else None,
            "checkInLatitude": rec.check_in_latitude,
            "checkInLongitude": rec.check_in_longitude,
            "checkOutLatitude": rec.check_out_latitude,
            "checkOutLongitude": rec.check_out_longitude,
            "checkInPhotoUrl": rec.check_in_photo_url,
            "checkOutPhotoUrl": rec.check_out_photo_url,
            "checkInComments": rec.check_in_comments,
            "checkOutComments": rec.check_out_comments,
            "checkInIpAddress": rec.check_in_ip_address,
            "checkOutIpAddress": rec.check_out_ip_address,
            "checkInDeviceFingerprint": rec.check_in_device_fingerprint,
            "checkOutDeviceFingerprint": rec.check_out_device_fingerprint,
            "isAutoPunchOut": bool(rec.is_auto_punch_out) if rec.is_auto_punch_out else False,
            "autoPunchOutReason": rec.auto_punch_out_reason,
            "checkInLocationTag": rec.check_in_location_tag,
            "checkInDistanceMeters": rec.check_in_distance_meters,
            "checkInAccuracyMeters": rec.check_in_accuracy_meters,
            "checkInPlaceName": rec.check_in_place_name,
            "checkOutLocationTag": rec.check_out_location_tag,
            "checkOutDistanceMeters": rec.check_out_distance_meters,
            "checkOutAccuracyMeters": rec.check_out_accuracy_meters,
            "checkOutPlaceName": rec.check_out_place_name,
            "lastKnownLatitude": rec.last_known_latitude,
            "lastKnownLongitude": rec.last_known_longitude,
            "lastKnownAccuracyMeters": rec.last_known_accuracy_meters,
            "lastKnownPlaceName": rec.last_known_place_name,
            "lastKnownTime": to_ist_iso(rec.last_known_time) if rec.last_known_time else None,
            "approvalStatus": rec.approval_status or "approved",
            "isOutOfOffice": bool(rec.is_out_of_office) if rec.is_out_of_office else False,
            "approvedByUserId": rec.approved_by_user_id,
            "approvedByUsername": rec.approved_by.username if rec.approved_by else None,
            "approvedAt": to_ist_iso(rec.approved_at) if rec.approved_at else None,
            "rejectionReason": rec.rejection_reason,
        }

    # If the user is currently clocked in (no check-out time), return it as active session
    if latest.check_out_time is None:
        return {"success": True, "attendance": serialize_att(latest)}
        
    # If latest session is completed, only return it if it was checked in today (in IST)
    now_ist = get_ist_now()
    if latest.check_in_time.date() == now_ist.date():
        return {"success": True, "attendance": serialize_att(latest)}
        
    return {"success": True, "attendance": None}


# Breadcrumb filtering. Phone GPS is typically off by 5-50 m, so movement only counts when it exceeds
# both a floor and the fix's own reported accuracy; otherwise a parked phone records a cloud of jitter.
MIN_BREADCRUMB_DISTANCE_METERS = 15.0
STATIONARY_HEARTBEAT_SECONDS = 600
GEOCODE_REFRESH_DISTANCE_METERS = 25.0

# Older app builds ping every 3-10 seconds on 1 m of movement. A ping that arrives sooner than this after the
# last one the server processed is answered from memory without touching the database. The state lives in
# this process, which is fine because the backend runs a single worker.
PING_MIN_INTERVAL_SECONDS = 15
_last_processed_ping: Dict[int, tuple] = {}  # user_id -> (time.monotonic() when processed, shift was active)


def forget_ping_state(user_id: int) -> None:
    """Called when a shift starts or ends so the user's next ping reads the database."""
    _last_processed_ping.pop(user_id, None)


async def _last_breadcrumb(db: AsyncSession, attendance_id: int) -> Optional["AttendanceLocationLog"]:
    return (await db.execute(
        select(AttendanceLocationLog)
        .where(AttendanceLocationLog.attendance_id == attendance_id)
        .order_by(desc(AttendanceLocationLog.recorded_at), desc(AttendanceLocationLog.id))
        .limit(1)
    )).scalars().first()


def _distance_from(lat_str: Optional[str], lon_str: Optional[str], lat: float, lon: float) -> Optional[float]:
    try:
        return haversine_distance_meters(float(lat_str), float(lon_str), lat, lon)
    except (TypeError, ValueError):
        return None


@router.post("/ping-location")
async def ping_location(
    req: LocationPingRequest,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Periodic background location ping from the active web app / mobile wrapper.
    Always refreshes 'last_known_*' on the active attendance session. Adds a breadcrumb to
    portal_attendance_locations when the user has moved beyond GPS noise since the previous
    breadcrumb, or as a heartbeat every STATIONARY_HEARTBEAT_SECONDS while stationary.
    Pings closer together than PING_MIN_INTERVAL_SECONDS are acknowledged without a database query.
    """
    processed_at = time.monotonic()
    last = _last_processed_ping.get(user.user_id)
    if last and processed_at - last[0] < PING_MIN_INTERVAL_SECONDS:
        return {"success": True, "active": last[1], "recorded": False, "throttled": True}

    stmt = (
        select(Attendance)
        .where(
            and_(
                Attendance.user_id == user.user_id,
                Attendance.check_out_time.is_(None)
            )
        )
        .order_by(desc(Attendance.check_in_time))
        .limit(1)
    )
    res = await db.execute(stmt)
    rec = res.scalars().first()

    if not rec:
        _last_processed_ping[user.user_id] = (processed_at, False)
        return {"success": True, "active": False, "message": "No active shift"}

    now_ist = get_ist_now()

    # Compare against the last *recorded* breadcrumb, not the last ping: measuring ping-to-ping
    # would never accumulate slow movement that stays under the threshold on every single ping.
    last_crumb = await _last_breadcrumb(db, rec.id)
    if last_crumb is not None:
        ref_lat, ref_lon, ref_time, ref_place = last_crumb.latitude, last_crumb.longitude, last_crumb.recorded_at, last_crumb.place_name
    else:
        # Sessions started before breadcrumbs existed: measure from the check-in
        ref_lat, ref_lon, ref_time, ref_place = rec.check_in_latitude, rec.check_in_longitude, rec.check_in_time, rec.check_in_place_name

    dist_moved = _distance_from(ref_lat, ref_lon, req.latitude, req.longitude)
    elapsed_sec = (now_ist - ref_time.replace(tzinfo=None)).total_seconds() if ref_time else None
    move_threshold = max(MIN_BREADCRUMB_DISTANCE_METERS, req.accuracyMeters or 0.0)

    should_log = (
        last_crumb is None
        or dist_moved is None
        or dist_moved >= move_threshold
        or elapsed_sec is None
        or elapsed_sec >= STATIONARY_HEARTBEAT_SECONDS
    )

    # Reverse geocode only for a recorded move that is far enough to change the place name
    place_name = rec.last_known_place_name or ref_place
    if not place_name or (should_log and dist_moved is not None and dist_moved >= GEOCODE_REFRESH_DISTANCE_METERS):
        geocoded = await reverse_geocode_place_async(req.latitude, req.longitude, skip_if_busy=True)
        if geocoded:
            place_name = geocoded

    # Update latest known location on attendance record
    rec.last_known_latitude = str(req.latitude)
    rec.last_known_longitude = str(req.longitude)
    rec.last_known_accuracy_meters = req.accuracyMeters
    rec.last_known_place_name = place_name
    rec.last_known_time = now_ist

    if should_log:
        db.add(AttendanceLocationLog(
            attendance_id=rec.id,
            user_id=user.user_id,
            account_id=user.account_id,
            latitude=str(req.latitude),
            longitude=str(req.longitude),
            accuracy_meters=req.accuracyMeters,
            distance_from_prev_meters=round(dist_moved or 0.0, 1),
            place_name=place_name,
            recorded_at=now_ist
        ))

    await db.commit()
    _last_processed_ping[user.user_id] = (processed_at, True)
    return {
        "success": True,
        "active": True,
        "lastKnownTime": to_ist_iso(now_ist),
        "placeName": place_name,
        "distanceMovedMeters": round(dist_moved or 0.0, 1),
        "recorded": should_log
    }


@router.post("/punch")
async def punch_attendance(
    req: PunchRequest,
    request: Request,
    user: User = Depends(require_permission("attendance", "create")),
    db: AsyncSession = Depends(get_db)
):
    if not req.photoBase64:
        raise HTTPException(status_code=400, detail="Photo is required for attendance verification")
        
    # Process photo (blocking HTTP upload, kept off the event loop)
    photo_url = await asyncio.to_thread(
        upload_image_to_imagekit,
        req.photoBase64,
        f"attendance_{req.type}_{user.user_id}_{int(datetime.utcnow().timestamp())}.jpg"
    )
    if not photo_url:
        photo_url = f"attendance_{req.type}_{user.user_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
    ip_address = request.headers.get("x-forwarded-for") or request.client.host or "unknown"
    sanitized_comments = req.comments[:1024] if req.comments else None
    now_ist = get_ist_now()
    formatted_ist = now_ist.strftime("%I:%M %p")

    # Fetch active office locations for the company to resolve geofence tag
    offices_res = await db.execute(
        select(OfficeLocation).where(
            OfficeLocation.company_id == user.company_id,
            OfficeLocation.is_active == True
        )
    )
    offices = offices_res.scalars().all()
    loc_tag, dist_m, off_id = resolve_location_tag(req.latitude, req.longitude, offices)
    
    # Check whether the punch coordinate is outside the office geofence
    is_out = not loc_tag.startswith("In Office:")
    
    if req.type == "in":
        # Check if already clocked in (either active session or already checkin today in IST)
        stmt = select(Attendance).where(Attendance.user_id == user.user_id).order_by(desc(Attendance.check_in_time)).limit(1)
        res = await db.execute(stmt)
        latest = res.scalars().first()
        if latest:
            if latest.check_out_time is None:
                raise HTTPException(status_code=400, detail="You are already clocked in. Please clock out first.")
            if latest.check_in_time.date() == now_ist.date():
                raise HTTPException(status_code=400, detail="You have already completed your shift today.")
            
        approval_status = "pending" if is_out else "approved"
        
        attendance = Attendance(
            user_id=user.user_id,
            account_id=user.account_id,
            check_in_time=now_ist,
            check_in_latitude=str(req.latitude),
            check_in_longitude=str(req.longitude),
            check_in_photo_url=photo_url,
            check_in_comments=sanitized_comments,
            check_in_ip_address=ip_address,
            check_in_device_fingerprint=req.deviceFingerprint,
            check_in_location_tag=loc_tag,
            check_in_distance_meters=dist_m,
            check_in_office_id=off_id,
            check_in_accuracy_meters=req.accuracyMeters,
            is_out_of_office=is_out,
            approval_status=approval_status,
        )

        # Best-effort reverse geocode for human-readable place name
        place_name = await reverse_geocode_place_async(req.latitude, req.longitude)
        attendance.check_in_place_name = place_name

        # Initialize last known location with check-in coordinates
        attendance.last_known_latitude = str(req.latitude)
        attendance.last_known_longitude = str(req.longitude)
        attendance.last_known_accuracy_meters = req.accuracyMeters
        attendance.last_known_place_name = place_name
        attendance.last_known_time = now_ist

        db.add(attendance)
        await db.commit()
        await db.refresh(attendance)
        forget_ping_state(user.user_id)

        # Record initial check-in location breadcrumb
        try:
            init_log = AttendanceLocationLog(
                attendance_id=attendance.id,
                user_id=user.user_id,
                account_id=user.account_id,
                latitude=str(req.latitude),
                longitude=str(req.longitude),
                accuracy_meters=req.accuracyMeters,
                distance_from_prev_meters=0.0,
                place_name=place_name,
                recorded_at=now_ist
            )
            db.add(init_log)
            await db.commit()
        except Exception as e:
            print("Error logging check-in location breadcrumb:", e)

        # Notify admins of punch in: an approval request, or one grouped "N staff clocked in today" entry
        from app.routers.notifications import notify_admins
        if is_out:
            await notify_admins(
                db=db,
                company_id=user.company_id,
                type="attendance_approval",
                title="Attendance Approval Required: Clock-In",
                message=f"{user.username} clocked in OUTSIDE office geofence ({loc_tag}) at {formatted_ist}. Admin approval required.",
                reference_id=str(attendance.id),
                reference_type="attendance",
                link=attendance_approval_link(attendance.id),
                group_key=f"approval:attendance:{attendance.id}",
                exclude_user_id=user.user_id,
                auto_commit=True,
            )
        else:
            await notify_admins(
                db=db,
                company_id=user.company_id,
                type="attendance_activity",
                title="Attendance: Clock-In",
                message=f"{user.username} clocked in at {formatted_ist} ({loc_tag})",
                reference_id=str(attendance.id),
                reference_type="attendance",
                link=TEAM_ATTENDANCE_LINK,
                group_key=f"clock_in:{now_ist.date().isoformat()}",
                group_title=lambda n: f"{n} staff clocked in today",
                exclude_user_id=user.user_id,
                auto_commit=True,
            )

        resp_msg = "Clocked in successfully. Pending admin approval (Outside office geofence)." if is_out else "Clocked in successfully"
        return {
            "success": True, 
            "message": resp_msg,
            "locationTag": loc_tag,
            "distanceMeters": dist_m,
            "accuracyMeters": req.accuracyMeters,
            "placeName": place_name,
            "approvalStatus": approval_status,
            "isOutOfOffice": is_out
        }
    else:
        # Check checkout session
        stmt = select(Attendance).where(Attendance.user_id == user.user_id).order_by(desc(Attendance.check_in_time)).limit(1)
        res = await db.execute(stmt)
        latest = res.scalars().first()
        if not latest or latest.check_out_time is not None:
            raise HTTPException(status_code=400, detail="You do not have any active clocked-in session to clock out of.")
            
        latest.check_out_time = now_ist
        latest.check_out_latitude = str(req.latitude)
        latest.check_out_longitude = str(req.longitude)
        latest.check_out_photo_url = photo_url
        latest.check_out_comments = sanitized_comments
        latest.check_out_ip_address = ip_address
        latest.check_out_device_fingerprint = req.deviceFingerprint
        latest.check_out_location_tag = loc_tag
        latest.check_out_distance_meters = dist_m
        latest.check_out_office_id = off_id
        latest.check_out_accuracy_meters = req.accuracyMeters
        
        # Best-effort reverse geocode for place name
        checkout_place_name = await reverse_geocode_place_async(req.latitude, req.longitude)
        latest.check_out_place_name = checkout_place_name
        
        # If punch-out was out of office, flag is_out_of_office and require approval if not already rejected
        if is_out:
            latest.is_out_of_office = True
            if latest.approval_status != "rejected":
                latest.approval_status = "pending"

        # Record checkout location breadcrumb, measured from the previous breadcrumb so the
        # trail's summed distances stay consistent
        last_crumb = await _last_breadcrumb(db, latest.id)
        if last_crumb is not None:
            dist_from_last = _distance_from(last_crumb.latitude, last_crumb.longitude, req.latitude, req.longitude) or 0.0
        else:
            dist_from_last = _distance_from(latest.check_in_latitude, latest.check_in_longitude, req.latitude, req.longitude) or 0.0

        checkout_log = AttendanceLocationLog(
            attendance_id=latest.id,
            user_id=user.user_id,
            account_id=user.account_id,
            latitude=str(req.latitude),
            longitude=str(req.longitude),
            accuracy_meters=req.accuracyMeters,
            distance_from_prev_meters=round(dist_from_last, 1),
            place_name=checkout_place_name or latest.last_known_place_name,
            recorded_at=now_ist
        )
        db.add(checkout_log)

        await db.commit()
        forget_ping_state(user.user_id)

        # Notify admins of punch out. A pending approval updates the clock-in's approval request (same group).
        from app.routers.notifications import notify_admins
        if latest.approval_status == "pending":
            await notify_admins(
                db=db,
                company_id=user.company_id,
                type="attendance_approval",
                title="Attendance Approval Required: Clock-Out",
                message=f"{user.username} clocked out OUTSIDE office geofence ({loc_tag}) at {formatted_ist}. Admin approval required.",
                reference_id=str(latest.id),
                reference_type="attendance",
                link=attendance_approval_link(latest.id),
                group_key=f"approval:attendance:{latest.id}",
                exclude_user_id=user.user_id,
                auto_commit=True,
            )
        else:
            await notify_admins(
                db=db,
                company_id=user.company_id,
                type="attendance_activity",
                title="Attendance: Clock-Out",
                message=f"{user.username} clocked out at {formatted_ist} ({loc_tag})",
                reference_id=str(latest.id),
                reference_type="attendance",
                link=TEAM_ATTENDANCE_LINK,
                group_key=f"clock_out:{now_ist.date().isoformat()}",
                group_title=lambda n: f"{n} staff clocked out today",
                exclude_user_id=user.user_id,
                auto_commit=True,
            )

        resp_msg = "Clocked out successfully. Pending admin approval (Outside office geofence)." if latest.approval_status == "pending" else "Clocked out successfully"
        return {
            "success": True, 
            "message": resp_msg,
            "locationTag": loc_tag,
            "distanceMeters": dist_m,
            "accuracyMeters": req.accuracyMeters,
            "placeName": checkout_place_name,
            "approvalStatus": latest.approval_status,
            "isOutOfOffice": latest.is_out_of_office
        }


@router.get("/history")
async def get_attendance_history(
    limit: int = 30,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Attendance)
        .options(selectinload(Attendance.approved_by))
        .where(Attendance.user_id == user.user_id)
        .order_by(desc(Attendance.check_in_time))
        .limit(limit)
    )
    res = await db.execute(stmt)
    history = res.scalars().all()
    
    return {
        "success": True,
        "history": [
            {
                "id": h.id,
                "userId": h.user_id,
                "checkInTime": to_ist_iso(h.check_in_time),
                "checkOutTime": to_ist_iso(h.check_out_time),
                "checkInLatitude": h.check_in_latitude,
                "checkInLongitude": h.check_in_longitude,
                "checkOutLatitude": h.check_out_latitude,
                "checkOutLongitude": h.check_out_longitude,
                "checkInPhotoUrl": h.check_in_photo_url,
                "checkOutPhotoUrl": h.check_out_photo_url,
                "checkInComments": h.check_in_comments,
                "checkOutComments": h.check_out_comments,
                "checkInIpAddress": h.check_in_ip_address,
                "checkOutIpAddress": h.check_out_ip_address,
                "checkInDeviceFingerprint": h.check_in_device_fingerprint,
                "checkOutDeviceFingerprint": h.check_out_device_fingerprint,
                "isAutoPunchOut": bool(h.is_auto_punch_out) if h.is_auto_punch_out else False,
                "autoPunchOutReason": h.auto_punch_out_reason,
                "checkInLocationTag": h.check_in_location_tag,
                "checkInDistanceMeters": h.check_in_distance_meters,
                "checkInAccuracyMeters": h.check_in_accuracy_meters,
                "checkInPlaceName": h.check_in_place_name,
                "checkOutLocationTag": h.check_out_location_tag,
                "checkOutDistanceMeters": h.check_out_distance_meters,
                "checkOutAccuracyMeters": h.check_out_accuracy_meters,
                "checkOutPlaceName": h.check_out_place_name,
                "lastKnownLatitude": h.last_known_latitude,
                "lastKnownLongitude": h.last_known_longitude,
                "lastKnownAccuracyMeters": h.last_known_accuracy_meters,
                "lastKnownPlaceName": h.last_known_place_name,
                "lastKnownTime": to_ist_iso(h.last_known_time) if h.last_known_time else None,
                "approvalStatus": h.approval_status or "approved",
                "isOutOfOffice": bool(h.is_out_of_office) if h.is_out_of_office else False,
                "approvedByUserId": h.approved_by_user_id,
                "approvedByUsername": h.approved_by.username if h.approved_by else None,
                "approvedAt": to_ist_iso(h.approved_at) if h.approved_at else None,
                "rejectionReason": h.rejection_reason,
            }
            for h in history
        ]
    }


@router.get("/admin/today-team")
async def get_team_attendance_for_admin(
    dateStr: Optional[str] = None,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    # Verify Admin role
    role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
    role = role_q.scalars().first()
    if not role or role.name.lower() not in ("admin", "superadmin", "owner"):
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    target_date = datetime.strptime(dateStr, "%Y-%m-%d").date() if dateStr else get_ist_date()
    
    # Get all users in the company
    users_stmt = select(User).where(users_of_account(user)).order_by(User.username)
    res_users = await db.execute(users_stmt)
    all_users = res_users.scalars().all()
    
    if not all_users:
        return {"success": True, "data": []}

    user_ids = [u.user_id for u in all_users]

    # Get all attendance logs for the target date for this company's users
    start_of_target = datetime.combine(target_date, datetime.min.time())
    end_of_target = datetime.combine(target_date, datetime.max.time())
    
    stmt = (
        select(Attendance)
        .options(selectinload(Attendance.approved_by))
        .where(
            and_(
                Attendance.user_id.in_(user_ids),
                Attendance.check_in_time >= start_of_target,
                Attendance.check_in_time <= end_of_target
            )
        )
    )
    res_att = await db.execute(stmt)
    records = res_att.scalars().all()
    
    records_map = {r.user_id: r for r in records}
    
    data = []
    for u in all_users:
        rec = records_map.get(u.user_id)
        data.append({
            "userId": u.user_id,
            "username": u.username,
            "isActive": u.is_active,
            "attendance": {
                "id": rec.id,
                "userId": rec.user_id,
                "checkInTime": to_ist_iso(rec.check_in_time) if rec else None,
                "checkOutTime": to_ist_iso(rec.check_out_time) if rec else None,
                "checkInLatitude": rec.check_in_latitude,
                "checkInLongitude": rec.check_in_longitude,
                "checkOutLatitude": rec.check_out_latitude,
                "checkOutLongitude": rec.check_out_longitude,
                "checkInPhotoUrl": rec.check_in_photo_url,
                "checkOutPhotoUrl": rec.check_out_photo_url,
                "checkInComments": rec.check_in_comments,
                "checkOutComments": rec.check_out_comments,
                "isAutoPunchOut": bool(rec.is_auto_punch_out) if (rec and rec.is_auto_punch_out) else False,
                "autoPunchOutReason": rec.auto_punch_out_reason if rec else None,
                "checkInLocationTag": rec.check_in_location_tag if rec else None,
                "checkInDistanceMeters": rec.check_in_distance_meters if rec else None,
                "checkInAccuracyMeters": rec.check_in_accuracy_meters if rec else None,
                "checkInPlaceName": rec.check_in_place_name if rec else None,
                "checkOutLocationTag": rec.check_out_location_tag if rec else None,
                "checkOutDistanceMeters": rec.check_out_distance_meters if rec else None,
                "checkOutAccuracyMeters": rec.check_out_accuracy_meters if rec else None,
                "checkOutPlaceName": rec.check_out_place_name if rec else None,
                "lastKnownLatitude": rec.last_known_latitude if rec else None,
                "lastKnownLongitude": rec.last_known_longitude if rec else None,
                "lastKnownAccuracyMeters": rec.last_known_accuracy_meters if rec else None,
                "lastKnownPlaceName": rec.last_known_place_name if rec else None,
                "lastKnownTime": to_ist_iso(rec.last_known_time) if (rec and rec.last_known_time) else None,
                "approvalStatus": rec.approval_status if rec else None,
                "isOutOfOffice": bool(rec.is_out_of_office) if (rec and rec.is_out_of_office) else False,
                "approvedByUserId": rec.approved_by_user_id if rec else None,
                "approvedByUsername": rec.approved_by.username if (rec and rec.approved_by) else None,
                "approvedAt": to_ist_iso(rec.approved_at) if (rec and rec.approved_at) else None,
                "rejectionReason": rec.rejection_reason if rec else None,
            } if rec else None
        })
        
    return {"success": True, "data": data}


@router.get("/admin/history-team")
async def get_full_team_attendance_history(
    startDateStr: str,
    endDateStr: str,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
    role = role_q.scalars().first()
    if not role or role.name.lower() not in ("admin", "superadmin", "owner"):
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    start_date = datetime.strptime(startDateStr, "%Y-%m-%d")
    end_date = datetime.strptime(endDateStr, "%Y-%m-%d") + timedelta(days=1)
    
    stmt = (
        select(Attendance)
        .options(selectinload(Attendance.user), selectinload(Attendance.approved_by))
        .join(User, Attendance.user_id == User.user_id)
        .where(
            and_(
                rows_of_account(Attendance, user),
                Attendance.check_in_time >= start_date,
                Attendance.check_in_time < end_date
            )
        )
        .order_by(desc(Attendance.check_in_time))
    )
    
    res = await db.execute(stmt)
    history = res.scalars().all()
    
    return {
        "success": True,
        "history": [
            {
                "id": h.id,
                "userId": h.user_id,
                "username": h.user.username if h.user else "Unknown",
                "checkInTime": to_ist_iso(h.check_in_time),
                "checkOutTime": to_ist_iso(h.check_out_time),
                "checkInLatitude": h.check_in_latitude,
                "checkInLongitude": h.check_in_longitude,
                "checkOutLatitude": h.check_out_latitude,
                "checkOutLongitude": h.check_out_longitude,
                "checkInPhotoUrl": h.check_in_photo_url,
                "checkOutPhotoUrl": h.check_out_photo_url,
                "checkInComments": h.check_in_comments,
                "checkOutComments": h.check_out_comments,
                "checkInIpAddress": h.check_in_ip_address,
                "checkOutIpAddress": h.check_out_ip_address,
                "isAutoPunchOut": bool(h.is_auto_punch_out) if h.is_auto_punch_out else False,
                "autoPunchOutReason": h.auto_punch_out_reason,
                "checkInLocationTag": h.check_in_location_tag,
                "checkInDistanceMeters": h.check_in_distance_meters,
                "checkInAccuracyMeters": h.check_in_accuracy_meters,
                "checkInPlaceName": h.check_in_place_name,
                "checkOutLocationTag": h.check_out_location_tag,
                "checkOutDistanceMeters": h.check_out_distance_meters,
                "checkOutAccuracyMeters": h.check_out_accuracy_meters,
                "checkOutPlaceName": h.check_out_place_name,
                "lastKnownLatitude": h.last_known_latitude,
                "lastKnownLongitude": h.last_known_longitude,
                "lastKnownAccuracyMeters": h.last_known_accuracy_meters,
                "lastKnownPlaceName": h.last_known_place_name,
                "lastKnownTime": to_ist_iso(h.last_known_time) if h.last_known_time else None,
                "approvalStatus": h.approval_status or "approved",
                "isOutOfOffice": bool(h.is_out_of_office) if h.is_out_of_office else False,
                "approvedByUserId": h.approved_by_user_id,
                "approvedByUsername": h.approved_by.username if h.approved_by else None,
                "approvedAt": to_ist_iso(h.approved_at) if h.approved_at else None,
                "rejectionReason": h.rejection_reason,
            }
            for h in history
        ]
    }


@router.get("/{attendance_id}/trail")
async def get_attendance_trail(
    attendance_id: int,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the chronological location trail (breadcrumbs) for a specific attendance session.
    Allowed for the attendance record owner or managers/admins.
    """
    att_res = await db.execute(
        select(Attendance)
        .options(selectinload(Attendance.user))
        .where(Attendance.id == attendance_id)
    )
    att = att_res.scalars().first()
    # Attendance belongs to an account: a record of another business does not exist as far as this caller goes
    if not att or (att.account_id is not None and att.account_id != user.account_id) \
            or (att.account_id is None and att.user is not None and att.user.account_id != user.account_id):
        raise HTTPException(status_code=404, detail="Attendance record not found")

    # Authorization: Owner or Admin/Manager
    if att.user_id != user.user_id:
        role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
        role = role_q.scalars().first()
        if not role or role.name.lower() not in ("admin", "superadmin", "owner", "manager"):
            raise HTTPException(status_code=403, detail="Unauthorized to view this location trail")

    logs_res = await db.execute(
        select(AttendanceLocationLog)
        .where(AttendanceLocationLog.attendance_id == attendance_id)
        .order_by(AttendanceLocationLog.recorded_at.asc())
    )
    logs = logs_res.scalars().all()

    total_dist = 0.0
    trail_points = []
    for l in logs:
        dist = l.distance_from_prev_meters or 0.0
        total_dist += dist
        try:
            lat_f = float(l.latitude)
            lon_f = float(l.longitude)
        except (ValueError, TypeError):
            continue
        trail_points.append({
            "id": l.id,
            "latitude": lat_f,
            "longitude": lon_f,
            "accuracyMeters": l.accuracy_meters,
            "distanceFromPrevMeters": round(dist, 1),
            "placeName": l.place_name,
            "recordedAt": to_ist_iso(l.recorded_at),
            "mapsUrl": f"https://www.google.com/maps?q={l.latitude},{l.longitude}"
        })

    # Compact JSON form for export and client-side processing, always built from the breadcrumb
    # table (movement_trail on the attendance row is legacy and no longer written)
    clean_trail_json = [
        {
            "lat": p["latitude"],
            "lng": p["longitude"],
            "time": p["recordedAt"],
            "acc": p["accuracyMeters"],
            "dist": p["distanceFromPrevMeters"],
            "place": p["placeName"]
        } for p in trail_points
    ]

    return {
        "success": True,
        "attendanceId": att.id,
        "userId": att.user_id,
        "employeeName": att.user.username if att.user else "Employee",
        "checkInTime": to_ist_iso(att.check_in_time),
        "checkOutTime": to_ist_iso(att.check_out_time) if att.check_out_time else None,
        "checkInPlace": att.check_in_place_name,
        "checkOutPlace": att.check_out_place_name,
        "lastKnownPlace": att.last_known_place_name,
        "lastKnownTime": to_ist_iso(att.last_known_time) if att.last_known_time else None,
        "totalPoints": len(trail_points),
        "totalDistanceMeters": round(total_dist, 1),
        "trail": trail_points,
        "trailJson": clean_trail_json
    }


@router.get("/{attendance_id}/trail/export")
async def export_attendance_trail_json(
    attendance_id: int,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Downloads the entire movement trail as a formatted JSON document.
    """
    trail_data = await get_attendance_trail(attendance_id, user, db)
    json_bytes = json.dumps(trail_data, indent=2).encode('utf-8')
    emp_name = trail_data.get('employeeName', 'user').replace(' ', '_')
    filename = f"movement_trail_{emp_name}_att_{attendance_id}.json"
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ─── Attendance Approvals Endpoints ──────────────────────────────────────────

@router.get("/admin/approvals")
async def get_attendance_approvals(
    status_filter: Optional[str] = "pending",  # "pending", "approved", "rejected", "all"
    limit: int = 100,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches attendance records that require or have had admin approval for out-of-office punches.
    """
    role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
    role = role_q.scalars().first()
    if not role or role.name.lower() not in ("admin", "superadmin", "owner"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    base_query = (
        select(Attendance)
        .options(selectinload(Attendance.user), selectinload(Attendance.approved_by))
        .join(User, Attendance.user_id == User.user_id)
        .where(rows_of_account(Attendance, user))
    )

    if status_filter and status_filter != "all":
        base_query = base_query.where(Attendance.approval_status == status_filter)
    else:
        # Show all out of office or pending approval
        base_query = base_query.where(
            (Attendance.is_out_of_office == True) | (Attendance.approval_status == "pending")
        )

    base_query = base_query.order_by(desc(Attendance.check_in_time)).limit(limit)

    res = await db.execute(base_query)
    records = res.scalars().all()

    # Total pending count in company
    pending_count_stmt = (
        select(func.count(Attendance.id))
        .join(User, Attendance.user_id == User.user_id)
        .where(
            rows_of_account(Attendance, user),
            Attendance.approval_status == "pending"
        )
    )
    pending_res = await db.execute(pending_count_stmt)
    pending_count = pending_res.scalar() or 0

    return {
        "success": True,
        "pendingCount": pending_count,
        "records": [
            {
                "id": r.id,
                "userId": r.user_id,
                "username": r.user.username if r.user else f"User #{r.user_id}",
                "checkInTime": to_ist_iso(r.check_in_time),
                "checkOutTime": to_ist_iso(r.check_out_time),
                "checkInLatitude": r.check_in_latitude,
                "checkInLongitude": r.check_in_longitude,
                "checkOutLatitude": r.check_out_latitude,
                "checkOutLongitude": r.check_out_longitude,
                "checkInLocationTag": r.check_in_location_tag,
                "checkInDistanceMeters": r.check_in_distance_meters,
                "checkInAccuracyMeters": r.check_in_accuracy_meters,
                "checkInPlaceName": r.check_in_place_name,
                "checkOutLocationTag": r.check_out_location_tag,
                "checkOutDistanceMeters": r.check_out_distance_meters,
                "checkOutAccuracyMeters": r.check_out_accuracy_meters,
                "checkOutPlaceName": r.check_out_place_name,
                "checkInPhotoUrl": r.check_in_photo_url,
                "checkOutPhotoUrl": r.check_out_photo_url,
                "checkInComments": r.check_in_comments,
                "checkOutComments": r.check_out_comments,
                "approvalStatus": r.approval_status or "approved",
                "isOutOfOffice": bool(r.is_out_of_office),
                "approvedByUserId": r.approved_by_user_id,
                "approvedByUsername": r.approved_by.username if r.approved_by else None,
                "approvedAt": to_ist_iso(r.approved_at) if r.approved_at else None,
                "rejectionReason": r.rejection_reason,
                "isAutoPunchOut": bool(r.is_auto_punch_out),
            }
            for r in records
        ]
    }


@router.post("/admin/approve/{attendance_id}")
async def approve_attendance(
    attendance_id: int,
    user: User = Depends(require_permission("attendance", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Approves an out-of-office attendance punch.
    """
    role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
    role = role_q.scalars().first()
    if not role or role.name.lower() not in ("admin", "superadmin", "owner"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    stmt = (
        select(Attendance)
        .options(selectinload(Attendance.user))
        .join(User, Attendance.user_id == User.user_id)
        .where(
            Attendance.id == attendance_id,
            rows_of_account(Attendance, user)
        )
    )
    res = await db.execute(stmt)
    rec = res.scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    rec.approval_status = "approved"
    rec.approved_by_user_id = user.user_id
    rec.approved_at = get_ist_now()
    rec.rejection_reason = None
    await db.commit()

    # Notify employee
    from app.routers.notifications import notify_user
    date_str = rec.check_in_time.strftime("%d %b %Y") if rec.check_in_time else "recent shift"
    await notify_user(
        db=db,
        company_id=user.company_id,
        user_id=rec.user_id,
        type="attendance",
        title="Attendance Approved",
        message=f"Your out-of-office attendance for {date_str} has been approved by Admin ({user.username}).",
        reference_id=str(rec.id),
        reference_type="attendance",
        link=my_attendance_link(rec.id),
        auto_commit=True,
    )

    return {
        "success": True,
        "message": f"Attendance #{rec.id} for {rec.user.username if rec.user else 'User'} approved successfully."
    }


@router.post("/admin/reject/{attendance_id}")
async def reject_attendance(
    attendance_id: int,
    req: AttendanceApprovalDecision,
    user: User = Depends(require_permission("attendance", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Rejects an out-of-office attendance punch with optional reason.
    """
    role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
    role = role_q.scalars().first()
    if not role or role.name.lower() not in ("admin", "superadmin", "owner"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    stmt = (
        select(Attendance)
        .options(selectinload(Attendance.user))
        .join(User, Attendance.user_id == User.user_id)
        .where(
            Attendance.id == attendance_id,
            rows_of_account(Attendance, user)
        )
    )
    res = await db.execute(stmt)
    rec = res.scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    rec.approval_status = "rejected"
    rec.approved_by_user_id = user.user_id
    rec.approved_at = get_ist_now()
    rec.rejection_reason = req.reason or "Rejected by admin"
    await db.commit()

    # Notify employee
    from app.routers.notifications import notify_user
    date_str = rec.check_in_time.strftime("%d %b %Y") if rec.check_in_time else "recent shift"
    reason_text = f" Reason: {req.reason}" if req.reason else ""
    await notify_user(
        db=db,
        company_id=user.company_id,
        user_id=rec.user_id,
        type="attendance",
        title="Attendance Rejected",
        message=f"Your out-of-office attendance for {date_str} was rejected by Admin ({user.username}).{reason_text}",
        reference_id=str(rec.id),
        reference_type="attendance",
        link=my_attendance_link(rec.id),
        auto_commit=True,
    )

    return {
        "success": True,
        "message": f"Attendance #{rec.id} for {rec.user.username if rec.user else 'User'} rejected."
    }


@router.post("/admin/bulk-approve")
async def bulk_approve_attendance(
    req: BulkApprovalRequest,
    user: User = Depends(require_permission("attendance", "update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Approves multiple out-of-office attendance records in bulk.
    """
    role_q = await db.execute(select(Role).where(Role.role_id == user.role_id))
    role = role_q.scalars().first()
    if not role or role.name.lower() not in ("admin", "superadmin", "owner"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    if not req.attendance_ids:
        raise HTTPException(status_code=400, detail="No attendance IDs provided.")

    stmt = (
        select(Attendance)
        .options(selectinload(Attendance.user))
        .join(User, Attendance.user_id == User.user_id)
        .where(
            Attendance.id.in_(req.attendance_ids),
            rows_of_account(Attendance, user)
        )
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    now_ist = get_ist_now()
    from app.routers.notifications import notify_user
    approved_count = 0
    for rec in records:
        rec.approval_status = "approved"
        rec.approved_by_user_id = user.user_id
        rec.approved_at = now_ist
        rec.rejection_reason = None
        approved_count += 1

        date_str = rec.check_in_time.strftime("%d %b %Y") if rec.check_in_time else "recent shift"
        await notify_user(
            db=db,
            company_id=user.company_id,
            user_id=rec.user_id,
            type="attendance",
            title="Attendance Approved",
            message=f"Your out-of-office attendance for {date_str} has been approved by Admin ({user.username}).",
            reference_id=str(rec.id),
            reference_type="attendance",
            link=my_attendance_link(rec.id),
            auto_commit=False,
        )

    await db.commit()
    return {
        "success": True,
        "message": f"Successfully approved {approved_count} attendance records."
    }


# ─── Monthly Muster Roll & Timesheet Analytics ───────────────────────────────

@router.get("/admin/muster-roll")
async def get_monthly_muster_roll(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes a monthly muster roll matrix for all company employees.
    Returns day-by-day status ('P', 'HD', 'A', 'WO', '-') and calculated totals.
    """
    now_ist = get_ist_now()
    cur_year = year or now_ist.year
    cur_month = month or now_ist.month

    if cur_month < 1 or cur_month > 12:
        raise HTTPException(status_code=400, detail="Invalid month. Must be between 1 and 12.")

    _, num_days = calendar.monthrange(cur_year, cur_month)
    month_name = calendar.month_name[cur_month]
    today_date = now_ist.date()

    # Build calendar days metadata
    days_meta = []
    for d in range(1, num_days + 1):
        day_date = date(cur_year, cur_month, d)
        days_meta.append({
            "day": d,
            "date": day_date.isoformat(),
            "weekday": day_date.strftime("%a"),
            "isSunday": day_date.weekday() == 6,
            "isPast": day_date <= today_date,
        })

    # Fetch active company users
    users_stmt = select(User).where(users_of_account(user), User.is_active == True).order_by(User.username.asc())
    res_users = await db.execute(users_stmt)
    all_users = res_users.scalars().all()

    # Fetch all attendances for the month
    start_dt = datetime(cur_year, cur_month, 1, 0, 0, 0)
    end_dt = datetime(cur_year, cur_month, num_days, 23, 59, 59)
    att_stmt = (
        select(Attendance)
        .join(User, Attendance.user_id == User.user_id)
        .where(
            rows_of_account(Attendance, user),
            Attendance.check_in_time >= start_dt,
            Attendance.check_in_time <= end_dt
        )
        .order_by(Attendance.check_in_time.asc())
    )
    res_att = await db.execute(att_stmt)
    attendances = res_att.scalars().all()

    # Map records by (user_id, day)
    user_day_records: Dict[tuple[int, int], List[Attendance]] = {}
    for a in attendances:
        c_date = a.check_in_time.date()
        if c_date.year == cur_year and c_date.month == cur_month:
            key = (a.user_id, c_date.day)
            user_day_records.setdefault(key, []).append(a)

    employees_data = []
    total_company_hours = 0.0
    total_presents_all = 0
    total_working_days_elapsed = sum(1 for m in days_meta if m["isPast"] and not m["isSunday"])

    for u in all_users:
        emp_days: Dict[str, Any] = {}
        pres_count = 0
        hd_count = 0
        abs_count = 0
        wo_count = 0
        emp_hours = 0.0
        auto_punch_count = 0

        for d_meta in days_meta:
            d = d_meta["day"]
            day_date = date(cur_year, cur_month, d)
            recs = user_day_records.get((u.user_id, d), [])

            if recs:
                # Use the primary/longest session of the day
                rec = recs[0]
                hours = 0.0
                if rec.check_out_time:
                    dur_sec = (rec.check_out_time - rec.check_in_time).total_seconds()
                    hours = max(0.0, round(dur_sec / 3600.0, 1))
                elif day_date == today_date:
                    dur_sec = (now_ist - rec.check_in_time).total_seconds()
                    hours = max(0.0, round(dur_sec / 3600.0, 1))

                # Check approval status
                is_rejected = (rec.approval_status == "rejected")
                if is_rejected:
                    status_code = "A"
                    abs_count += 1
                    effective_hours = 0.0
                else:
                    effective_hours = hours
                    emp_hours += effective_hours
                    # Status threshold
                    if hours >= 7.5 or (rec.check_out_time is None and day_date == today_date):
                        status_code = "P"
                        pres_count += 1
                    elif 4.0 <= hours < 7.5:
                        status_code = "HD"
                        hd_count += 1
                    else:
                        status_code = "HD"
                        hd_count += 1

                emp_days[str(d)] = {
                    "status": status_code,
                    "checkIn": rec.check_in_time.strftime("%I:%M %p"),
                    "checkOut": rec.check_out_time.strftime("%I:%M %p") if rec.check_out_time else None,
                    "hours": effective_hours,
                    "locationTag": rec.check_in_location_tag or "Remote / Field",
                    "isAutoPunchOut": bool(rec.is_auto_punch_out),
                    "photoUrl": rec.check_in_photo_url,
                    "approvalStatus": rec.approval_status or "approved",
                    "isOutOfOffice": bool(rec.is_out_of_office) if rec.is_out_of_office else False,
                    "attendanceId": rec.id,
                    "rejectionReason": rec.rejection_reason,
                }
            else:
                if day_date > today_date:
                    status_code = "-"
                elif d_meta["isSunday"]:
                    status_code = "WO"
                    wo_count += 1
                else:
                    status_code = "A"
                    abs_count += 1

                emp_days[str(d)] = {
                    "status": status_code,
                    "checkIn": None,
                    "checkOut": None,
                    "hours": 0.0,
                    "locationTag": None,
                    "isAutoPunchOut": False,
                    "photoUrl": None,
                    "approvalStatus": "approved",
                    "isOutOfOffice": False,
                    "attendanceId": None,
                    "rejectionReason": None,
                }

        effective_days = pres_count + (0.5 * hd_count)
        total_presents_all += pres_count
        total_company_hours += emp_hours

        employees_data.append({
            "userId": u.user_id,
            "username": u.username,
            "days": emp_days,
            "summary": {
                "totalPresent": pres_count,
                "totalHalfDay": hd_count,
                "totalAbsent": abs_count,
                "totalWeekOff": wo_count,
                "effectiveDays": round(effective_days, 1),
                "totalHours": round(emp_hours, 1),
                "autoPunchOuts": auto_punch_count,
            }
        })

    # Company KPI metrics
    num_employees = len(all_users)
    potential_work_slots = (num_employees * total_working_days_elapsed) if (num_employees and total_working_days_elapsed) else 1
    avg_attendance_pct = round((total_presents_all / potential_work_slots) * 100, 1) if potential_work_slots else 0.0

    return {
        "success": True,
        "year": cur_year,
        "month": cur_month,
        "monthName": month_name,
        "totalDays": num_days,
        "days": days_meta,
        "employees": employees_data,
        "companySummary": {
            "totalStaff": num_employees,
            "workingDaysElapsed": total_working_days_elapsed,
            "avgAttendancePct": avg_attendance_pct,
            "totalCompanyHours": round(total_company_hours, 1),
        }
    }


@router.get("/admin/export-excel")
async def export_monthly_muster_roll_excel(
    year: Optional[int] = None,
    month: Optional[int] = None,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a professionally formatted Excel (.xlsx) Muster Roll spreadsheet.
    Includes corporate branding, colored presence cells (P/HD/A/WO), and summary totals.
    """
    now_ist = get_ist_now()
    cur_year = year or now_ist.year
    cur_month = month or now_ist.month

    if cur_month < 1 or cur_month > 12:
        raise HTTPException(status_code=400, detail="Invalid month.")

    # Fetch company name
    comp_q = await db.execute(select(Company).where(Company.company_id == user.company_id))
    company = comp_q.scalars().first()
    company_name = company.name if company else "MyTally Company"

    # Reuse muster roll calculation
    data = await get_monthly_muster_roll(year=cur_year, month=cur_month, user=user, db=db)
    days_meta = data["days"]
    employees = data["employees"]
    month_name = data["monthName"]

    # Initialize workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Muster Roll - {month_name[:3]}"

    # Styles
    title_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    title_font = Font(name="Arial", size=15, bold=True, color="FFFFFF")
    subtitle_font = Font(name="Arial", size=10, italic=True, color="4B5563")

    header_fill = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
    header_sun_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    header_font = Font(name="Arial", size=9, bold=True, color="1F2937")

    fill_p = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")  # emerald-100
    font_p = Font(name="Arial", size=9, bold=True, color="166534")

    fill_hd = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid") # amber-100
    font_hd = Font(name="Arial", size=9, bold=True, color="92400E")

    fill_a = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")  # red-100
    font_a = Font(name="Arial", size=9, bold=True, color="991B1B")

    fill_wo = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid") # slate-100
    font_wo = Font(name="Arial", size=9, color="64748B")

    thin_border_side = Side(border_style="thin", color="D1D5DB")
    cell_border = Border(top=thin_border_side, left=thin_border_side, right=thin_border_side, bottom=thin_border_side)

    # Row 1: Company Title Banner
    num_days = len(days_meta)
    total_cols = 3 + num_days + 6
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    cell_t1 = ws.cell(row=1, column=1, value=company_name.upper())
    cell_t1.fill = title_fill
    cell_t1.font = title_font
    cell_t1.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    # Row 2: Subtitle
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
    cell_t2 = ws.cell(
        row=2, 
        column=1, 
        value=f"MONTHLY ATTENDANCE MUSTER ROLL — {month_name.upper()} {cur_year} | Generated on {now_ist.strftime('%d-%b-%Y %I:%M %p IST')} | Total Staff: {len(employees)}"
    )
    cell_t2.font = subtitle_font
    cell_t2.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # Row 4: Table Headers - Top Line
    ws.cell(row=4, column=1, value="Sl.").font = header_font
    ws.cell(row=4, column=2, value="Employee Name").font = header_font
    ws.cell(row=4, column=3, value="User ID").font = header_font

    col_idx = 4
    for d in days_meta:
        c = ws.cell(row=4, column=col_idx, value=f"{d['day']}\n{d['weekday']}")
        c.font = header_font
        c.fill = header_sun_fill if d["isSunday"] else header_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = cell_border
        col_idx += 1

    summary_headers = ["Present (P)", "Half Day (HD)", "Absent (A)", "Week Off (WO)", "Effective Days", "Total Hours"]
    for sh in summary_headers:
        c = ws.cell(row=4, column=col_idx, value=sh)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = cell_border
        col_idx += 1

    for c_i in range(1, 4):
        ws.cell(row=4, column=c_i).fill = header_fill
        ws.cell(row=4, column=c_i).alignment = Alignment(horizontal="center", vertical="center")
        ws.cell(row=4, column=c_i).border = cell_border

    ws.row_dimensions[4].height = 28

    # Data Rows
    current_row = 5
    for idx, emp in enumerate(employees, start=1):
        ws.cell(row=current_row, column=1, value=idx).alignment = Alignment(horizontal="center")
        ws.cell(row=current_row, column=1).border = cell_border

        ws.cell(row=current_row, column=2, value=emp["username"]).alignment = Alignment(horizontal="left")
        ws.cell(row=current_row, column=2).border = cell_border

        ws.cell(row=current_row, column=3, value=f"#{emp['userId']}").alignment = Alignment(horizontal="center")
        ws.cell(row=current_row, column=3).border = cell_border

        col_i = 4
        for d in days_meta:
            day_info = emp["days"].get(str(d["day"]), {})
            st = day_info.get("status", "-")
            cell = ws.cell(row=current_row, column=col_i, value=st)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = cell_border

            if st == "P":
                cell.fill = fill_p
                cell.font = font_p
            elif st == "HD":
                cell.fill = fill_hd
                cell.font = font_hd
            elif st == "A":
                cell.fill = fill_a
                cell.font = font_a
            elif st == "WO":
                cell.fill = fill_wo
                cell.font = font_wo

            col_i += 1

        # Summary columns
        summ = emp["summary"]
        ws.cell(row=current_row, column=col_i, value=summ["totalPresent"]).border = cell_border
        ws.cell(row=current_row, column=col_i).alignment = Alignment(horizontal="center")
        col_i += 1

        ws.cell(row=current_row, column=col_i, value=summ["totalHalfDay"]).border = cell_border
        ws.cell(row=current_row, column=col_i).alignment = Alignment(horizontal="center")
        col_i += 1

        ws.cell(row=current_row, column=col_i, value=summ["totalAbsent"]).border = cell_border
        ws.cell(row=current_row, column=col_i).alignment = Alignment(horizontal="center")
        col_i += 1

        ws.cell(row=current_row, column=col_i, value=summ["totalWeekOff"]).border = cell_border
        ws.cell(row=current_row, column=col_i).alignment = Alignment(horizontal="center")
        col_i += 1

        ws.cell(row=current_row, column=col_i, value=summ["effectiveDays"]).border = cell_border
        ws.cell(row=current_row, column=col_i).font = Font(name="Arial", size=9, bold=True)
        ws.cell(row=current_row, column=col_i).alignment = Alignment(horizontal="center")
        col_i += 1

        ws.cell(row=current_row, column=col_i, value=f"{summ['totalHours']}h").border = cell_border
        ws.cell(row=current_row, column=col_i).alignment = Alignment(horizontal="center")
        col_i += 1

        ws.row_dimensions[current_row].height = 20
        current_row += 1

    # Column widths
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 10
    for col_num in range(4, 4 + num_days):
        ws.column_dimensions[get_column_letter(col_num)].width = 5.5
    for col_num in range(4 + num_days, total_cols + 1):
        ws.column_dimensions[get_column_letter(col_num)].width = 14

    # Output as downloadable bytes
    output_stream = io.BytesIO()
    wb.save(output_stream)
    output_stream.seek(0)
    file_bytes = output_stream.getvalue()

    filename = f"Attendance_Muster_Roll_{month_name}_{cur_year}.xlsx"
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

