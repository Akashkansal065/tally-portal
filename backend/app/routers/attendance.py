from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, desc, and_, Date
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date, timedelta
import base64
import urllib.request
import urllib.parse
import json

from app.core.database import get_db, Base
from app.core.permissions import require_permission
from app.models.user import User, Role
from app.core.config import settings

# ─── Model ───────────────────────────────────────────────────────────────────

class Attendance(Base):
    __tablename__ = "portal_attendance"
    __table_args__ = {"schema": settings.PORTAL_DATABASE_NAME}

    id = Column(Integer, primary_key=True, index=True)
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
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

# ─── Schemas ─────────────────────────────────────────────────────────────────

class PunchRequest(BaseModel):
    type: str # "in" or "out"
    latitude: float
    longitude: float
    deviceFingerprint: str
    photoBase64: str
    comments: Optional[str] = None

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

@router.get("/today")
async def get_today_attendance(
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Attendance).where(Attendance.user_id == user.user_id).order_by(desc(Attendance.check_in_time)).limit(1)
    res = await db.execute(stmt)
    latest = res.scalars().first()
    
    if not latest:
        return {"success": True, "attendance": None}
        
    # If the user is currently clocked in (no check-out time), return it as active session
    if latest.check_out_time is None:
        return {"success": True, "attendance": {
            "id": latest.id,
            "userId": latest.user_id,
            "checkInTime": latest.check_in_time.isoformat() if latest.check_in_time else None,
            "checkOutTime": None,
            "checkInLatitude": latest.check_in_latitude,
            "checkInLongitude": latest.check_in_longitude,
            "checkOutLatitude": latest.check_out_latitude,
            "checkOutLongitude": latest.check_out_longitude,
            "checkInPhotoUrl": latest.check_in_photo_url,
            "checkOutPhotoUrl": latest.check_out_photo_url,
            "checkInComments": latest.check_in_comments,
            "checkOutComments": latest.check_out_comments,
            "checkInIpAddress": latest.check_in_ip_address,
            "checkOutIpAddress": latest.check_out_ip_address,
            "checkInDeviceFingerprint": latest.check_in_device_fingerprint,
            "checkOutDeviceFingerprint": latest.check_out_device_fingerprint,
        }}
        
    # If latest session is completed, only return it if it was checked in today
    now = datetime.now()
    if latest.check_in_time.date() == now.date():
        return {"success": True, "attendance": {
            "id": latest.id,
            "userId": latest.user_id,
            "checkInTime": latest.check_in_time.isoformat() if latest.check_in_time else None,
            "checkOutTime": latest.check_out_time.isoformat() if latest.check_out_time else None,
            "checkInLatitude": latest.check_in_latitude,
            "checkInLongitude": latest.check_in_longitude,
            "checkOutLatitude": latest.check_out_latitude,
            "checkOutLongitude": latest.check_out_longitude,
            "checkInPhotoUrl": latest.check_in_photo_url,
            "checkOutPhotoUrl": latest.check_out_photo_url,
            "checkInComments": latest.check_in_comments,
            "checkOutComments": latest.check_out_comments,
            "checkInIpAddress": latest.check_in_ip_address,
            "checkOutIpAddress": latest.check_out_ip_address,
            "checkInDeviceFingerprint": latest.check_in_device_fingerprint,
            "checkOutDeviceFingerprint": latest.check_out_device_fingerprint,
        }}
        
    return {"success": True, "attendance": None}

@router.post("/punch")
async def punch_attendance(
    req: PunchRequest,
    request: Request,
    user: User = Depends(require_permission("attendance", "create")),
    db: AsyncSession = Depends(get_db)
):
    if not req.photoBase64:
        raise HTTPException(status_code=400, detail="Photo is required for attendance verification")
        
    # Process photo
    photo_url = upload_image_to_imagekit(
        req.photoBase64,
        f"attendance_{req.type}_{user.user_id}_{int(datetime.utcnow().timestamp())}.jpg"
    )
    if not photo_url:
        photo_url = f"attendance_{req.type}_{user.user_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
    ip_address = request.headers.get("x-forwarded-for") or request.client.host or "unknown"
    sanitized_comments = req.comments[:1024] if req.comments else None
    
    if req.type == "in":
        # Check if already clocked in (either active session or already checkin today)
        stmt = select(Attendance).where(Attendance.user_id == user.user_id).order_by(desc(Attendance.check_in_time)).limit(1)
        res = await db.execute(stmt)
        latest = res.scalars().first()
        if latest:
            if latest.check_out_time is None:
                raise HTTPException(status_code=400, detail="You are already clocked in. Please clock out first.")
            if latest.check_in_time.date() == datetime.now().date():
                raise HTTPException(status_code=400, detail="You have already completed your shift today.")
            
        attendance = Attendance(
            user_id=user.user_id,
            check_in_time=datetime.now(),
            check_in_latitude=str(req.latitude),
            check_in_longitude=str(req.longitude),
            check_in_photo_url=photo_url,
            check_in_comments=sanitized_comments,
            check_in_ip_address=ip_address,
            check_in_device_fingerprint=req.deviceFingerprint
        )
        db.add(attendance)
        await db.commit()
        return {"success": True, "message": "Clocked in successfully"}
    else:
        # Check checkout session
        stmt = select(Attendance).where(Attendance.user_id == user.user_id).order_by(desc(Attendance.check_in_time)).limit(1)
        res = await db.execute(stmt)
        latest = res.scalars().first()
        if not latest or latest.check_out_time is not None:
            raise HTTPException(status_code=400, detail="You do not have any active clocked-in session to clock out of.")
            
        latest.check_out_time = datetime.now()
        latest.check_out_latitude = str(req.latitude)
        latest.check_out_longitude = str(req.longitude)
        latest.check_out_photo_url = photo_url
        latest.check_out_comments = sanitized_comments
        latest.check_out_ip_address = ip_address
        latest.check_out_device_fingerprint = req.deviceFingerprint
        
        await db.commit()
        return {"success": True, "message": "Clocked out successfully"}

@router.get("/history")
async def get_attendance_history(
    limit: int = 30,
    user: User = Depends(require_permission("attendance", "read")),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Attendance).where(Attendance.user_id == user.user_id).order_by(desc(Attendance.check_in_time)).limit(limit)
    res = await db.execute(stmt)
    history = res.scalars().all()
    
    return {
        "success": True,
        "history": [
            {
                "id": h.id,
                "userId": h.user_id,
                "checkInTime": h.check_in_time.isoformat() if h.check_in_time else None,
                "checkOutTime": h.check_out_time.isoformat() if h.check_out_time else None,
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
    if not role or role.name != "Admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    target_date = datetime.strptime(dateStr, "%Y-%m-%d").date() if dateStr else datetime.now().date()
    
    # Get all users with dataentry/sales role (or non-admin users)
    # Get role id for admin to exclude
    admin_role_q = await db.execute(select(Role).where(Role.name == "Admin"))
    admin_role = admin_role_q.scalars().first()
    
    users_stmt = select(User).where(User.company_id == user.company_id)
    if admin_role:
        users_stmt = users_stmt.where(User.role_id != admin_role.role_id)
        
    res_users = await db.execute(users_stmt)
    all_users = res_users.scalars().all()
    
    # Get all attendance logs for the target date
    start_of_target = datetime.combine(target_date, datetime.min.time())
    end_of_target = datetime.combine(target_date, datetime.max.time())
    
    stmt = select(Attendance).where(
        and_(
            Attendance.check_in_time >= start_of_target,
            Attendance.check_in_time <= end_of_target
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
                "checkInTime": rec.check_in_time.isoformat() if rec.check_in_time else None,
                "checkOutTime": rec.check_out_time.isoformat() if rec.check_out_time else None,
                "checkInLatitude": rec.check_in_latitude,
                "checkInLongitude": rec.check_in_longitude,
                "checkOutLatitude": rec.check_out_latitude,
                "checkOutLongitude": rec.check_out_longitude,
                "checkInPhotoUrl": rec.check_in_photo_url,
                "checkOutPhotoUrl": rec.check_out_photo_url,
                "checkInComments": rec.check_in_comments,
                "checkOutComments": rec.check_out_comments,
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
    if not role or role.name != "Admin":
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    start_date = datetime.strptime(startDateStr, "%Y-%m-%d")
    end_date = datetime.strptime(endDateStr, "%Y-%m-%d") + timedelta(days=1)
    
    stmt = select(Attendance).options(selectinload(Attendance.user)).where(
        and_(
            Attendance.check_in_time >= start_date,
            Attendance.check_in_time < end_date
        )
    ).order_by(desc(Attendance.check_in_time))
    
    res = await db.execute(stmt)
    history = res.scalars().all()
    
    return {
        "success": True,
        "history": [
            {
                "id": h.id,
                "userId": h.user_id,
                "username": h.user.username if h.user else "Unknown",
                "checkInTime": h.check_in_time.isoformat() if h.check_in_time else None,
                "checkOutTime": h.check_out_time.isoformat() if h.check_out_time else None,
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
            }
            for h in history
        ]
    }
