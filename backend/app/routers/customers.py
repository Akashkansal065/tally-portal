"""
Customers / Field Shop Directory Router
Dedicated to field sales, customer profiling, and GPS audit verification.
Strictly isolated from accounting: NO Tally ledger creation or accounting modifications.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, or_, and_, update
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
from collections import defaultdict, Counter

from app.core.database import get_db
from app.core.permissions import get_current_user, require_permission
from app.models.portal_core import User, CustomerProfile, CustomerLocationLog, CustomerPhoto, CustomerOwner
from app.models.tally_core import MstLedger, MstGroup, TrnVoucher, TrnAccounting
from app.services.geo_service import calculate_haversine_distance, evaluate_checkin_proximity
from app.services.imagekit_service import upload_customer_photo, delete_imagekit_file
from app.services.customer_health_service import calculate_visit_recency, calculate_customer_health

router = APIRouter(prefix="/customers", tags=["Customer Directory"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CustomerCreateRequest(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    route_name: Optional[str] = None
    shop_type: Optional[str] = "Retailer"
    tags: Optional[str] = None
    priority: Optional[str] = "medium"
    visit_frequency: Optional[str] = "weekly"
    notes: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class CustomerProfileUpdateRequest(BaseModel):
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    route_name: Optional[str] = None
    shop_type: Optional[str] = None
    tags: Optional[str] = None
    priority: Optional[str] = None
    visit_frequency: Optional[str] = None
    notes: Optional[str] = None


class TagLocationRequest(BaseModel):
    latitude: float
    longitude: float
    reason: Optional[str] = "Manual location tag"


class LinkLedgerRequest(BaseModel):
    ledger_id: int


class CustomerPhotoUploadRequest(BaseModel):
    photo_base64: str
    photo_type: str = "shop_front"  # "customer_owner", "shop_front", "shop_inside", "shop_board", "visiting_card", "qr_code", "other"
    caption: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_primary: Optional[bool] = False
    owner_id: Optional[int] = None


class CustomerOwnerCreate(BaseModel):
    name: str
    designation: Optional[str] = "Owner / Partner"
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    photo_url: Optional[str] = None
    is_primary: Optional[bool] = False
    notes: Optional[str] = None


class CustomerOwnerUpdate(BaseModel):
    name: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    email: Optional[str] = None
    photo_url: Optional[str] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = None


class OwnerPhotoUploadRequest(BaseModel):
    photo_base64: str
    caption: Optional[str] = None


# ─── Helper Functions ────────────────────────────────────────────────────────

def is_user_admin(user: User) -> bool:
    """Check if user has administrative privileges."""
    if user.role and user.role.name.lower() in ("admin", "superadmin", "owner"):
        return True
    if user.username and user.username.lower() == "admin":
        return True
    return False


def check_is_admin(user: User):
    """Ensure user has admin privileges before performing administrative mapping operations."""
    if not is_user_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Admin privileges required to perform this action."
        )

def build_maps_url(lat: Optional[float], lon: Optional[float], address: Optional[str] = None) -> str:
    """Generate universal Google Maps link for navigation."""
    if lat is not None and lon is not None:
        return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
    elif address:
        import urllib.parse
        encoded = urllib.parse.quote(address)
        return f"https://www.google.com/maps/search/?api=1&query={encoded}"
    return "https://www.google.com/maps"


def extract_locality_and_city(address: Optional[str]):
    """Extract sensible locality and city name from Indian address string."""
    if not address:
        return "", ""
    clean = address
    if " | Mobile: " in clean:
        clean = clean.split(" | Mobile: ")[0]
    import re
    # Strip pincodes
    clean = re.sub(r'\b\d{6}\b', '', clean).strip()
    parts = [p.strip() for p in clean.split(",") if p.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        val = parts[0].title()
        return val, val

    city = parts[-1].title()
    loc = parts[-2].title() if len(parts) >= 2 else city
    if len(loc) > 28:
        for kw in ['Near', 'Opp', 'Moh', 'Bazaar', 'Road', 'Nagar', 'Vihar', 'Colony', 'Ganj', 'Mandi', 'Chowk']:
            if kw in loc:
                idx = loc.find(kw)
                loc = loc[idx:].strip()
                break
    return loc[:28].strip(), city[:25].strip()


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("")
async def list_customers(
    search: Optional[str] = Query(None, description="Search by name, contact, phone, locality"),
    locality: Optional[str] = Query(None, description="Filter by locality"),
    city: Optional[str] = Query(None, description="Filter by city"),
    route_name: Optional[str] = Query(None, description="Filter by route/beat"),
    location_status: Optional[str] = Query("all", description="all, tagged, missing"),
    verification_filter: Optional[str] = Query("all", description="all, verified, mismatch, nearby, unverified"),
    radius_km: Optional[float] = Query(None, description="Radius filter in km (0.5, 1, 3, 5)"),
    visit_recency: Optional[str] = Query(None, description="all, visited_recent, due_soon, overdue, critical, never"),
    health_grade: Optional[str] = Query(None, description="all, HEALTHY, FAIR, AT_RISK"),
    sort_by: Optional[str] = Query("name_asc", description="name_asc, name_desc, nearest, missing_gps, last_visited, health_asc, health_desc"),
    my_lat: Optional[float] = Query(None, description="Current salesperson latitude"),
    my_lon: Optional[float] = Query(None, description="Current salesperson longitude"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all customers (Tally debtors read-only + field profiles).
    Zero accounting modification. Includes GPS coords, verification audit status,
    Customer Health Score, Days Since Last Visit badges, and Nearby Radius filters.
    """
    now = datetime.now()

    # 1. Fetch all groups to identify Sundry Debtors
    grp_res = await db.execute(
        select(MstGroup).where(MstGroup.company_id == user.company_id)
    )
    groups = grp_res.scalars().all()
    groups_dict = {g.group_id: g for g in groups}

    def is_sundry_debtor(group_id: Optional[int]) -> bool:
        curr_id = group_id
        visited = set()
        while curr_id and curr_id in groups_dict and curr_id not in visited:
            visited.add(curr_id)
            grp = groups_dict[curr_id]
            if grp.name and grp.name.strip().lower() == "sundry debtors":
                return True
            curr_id = grp.parent_group_id
        return False

    # 2. Fetch Tally ledgers for this company
    ledger_res = await db.execute(
        select(MstLedger).where(MstLedger.company_id == user.company_id)
    )
    all_ledgers = ledger_res.scalars().all()

    # 3. Fetch all CustomerProfiles in portal DB for this company
    profiles_res = await db.execute(
        select(CustomerProfile).where(CustomerProfile.company_id == user.company_id)
    )
    profiles = profiles_res.scalars().all()
    profile_by_ledger = {p.ledger_id: p for p in profiles if p.ledger_id is not None}
    standalone_profiles = [p for p in profiles if p.ledger_id is None]

    # 4. Fetch latest location log for each customer to get real-time audit status
    latest_logs_stmt = (
        select(CustomerLocationLog)
        .where(CustomerLocationLog.company_id == user.company_id)
        .order_by(desc(CustomerLocationLog.created_at))
    )
    logs_res = await db.execute(latest_logs_stmt)
    all_logs = logs_res.scalars().all()
    latest_log_by_profile = {}
    for log in all_logs:
        if log.customer_profile_id and log.customer_profile_id not in latest_log_by_profile:
            latest_log_by_profile[log.customer_profile_id] = log

    # 5. Fetch all owners for this company
    owners_res = await db.execute(
        select(CustomerOwner)
        .where(CustomerOwner.company_id == user.company_id)
        .order_by(CustomerOwner.is_primary.desc(), CustomerOwner.id.asc())
    )
    all_owners = owners_res.scalars().all()
    owners_by_profile = defaultdict(list)
    for o in all_owners:
        owners_by_profile[o.customer_profile_id].append({
            "id": o.id,
            "name": o.name,
            "designation": o.designation or "Owner / Partner",
            "phone": o.phone or "",
            "whatsapp_number": o.whatsapp_number or "",
            "email": o.email or "",
            "photo_url": o.photo_url,
            "is_primary": o.is_primary,
            "notes": o.notes or ""
        })

    # 6. Fetch Voucher Statistics per Ledger for Customer Health Calculation
    voucher_stats_by_ledger = {}
    try:
        voucher_stats_stmt = (
            select(
                TrnAccounting.ledger_id,
                func.max(TrnVoucher.voucher_date).label("last_voucher_date"),
                func.count(TrnVoucher.voucher_id).label("voucher_count")
            )
            .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
            .where(
                TrnVoucher.company_id == user.company_id,
                TrnVoucher.is_cancelled == False
            )
            .group_by(TrnAccounting.ledger_id)
        )
        v_res = await db.execute(voucher_stats_stmt)
        for row in v_res.all():
            voucher_stats_by_ledger[row.ledger_id] = (row.last_voucher_date, row.voucher_count)
    except Exception as e:
        print(f"Warning: could not fetch voucher stats: {e}")

    # 7. Fetch photo counts per profile
    photos_count_by_profile = {}
    try:
        photos_stmt = (
            select(
                CustomerPhoto.customer_profile_id,
                func.count(CustomerPhoto.id).label("photo_count")
            )
            .where(CustomerPhoto.company_id == user.company_id)
            .group_by(CustomerPhoto.customer_profile_id)
        )
        p_res = await db.execute(photos_stmt)
        for row in p_res.all():
            photos_count_by_profile[row.customer_profile_id] = row.photo_count
    except Exception as e:
        print(f"Warning: could not fetch photo counts: {e}")

    customers = []

    # Process Tally Sundry Debtors
    for l in all_ledgers:
        if not is_sundry_debtor(l.group_id):
            continue

        p = profile_by_ledger.get(l.ledger_id)

        # Clean address / mobile
        addr_clean = l.address or ""
        mobile_clean = l.mobile
        if addr_clean and " | Mobile: " in addr_clean:
            parts = addr_clean.split(" | Mobile: ")
            addr_clean = parts[0]
            if not mobile_clean and len(parts) > 1:
                mobile_clean = parts[1]

        lat = p.latitude if p else None
        lon = p.longitude if p else None
        e_loc, e_city = extract_locality_and_city(addr_clean)
        loc = (p.locality.strip() if (p and p.locality) else e_loc) or ""
        c_city = (p.city.strip() if (p and p.city) else (e_city or l.state)) or ""
        r_name = p.route_name if p else None

        latest_log = latest_log_by_profile.get(p.id) if p else None

        # Proximity to salesperson
        dist_from_me = None
        if my_lat is not None and my_lon is not None and lat is not None and lon is not None:
            dist_from_me = calculate_haversine_distance(my_lat, my_lon, lat, lon)

        # Visit Recency calculation
        recency = calculate_visit_recency(p.last_visit_at if p else None, now)

        # Health score calculation
        v_date, v_count = voucher_stats_by_ledger.get(l.ledger_id, (None, 0))
        has_contact = bool((p.phone if p and p.phone else l.phone) or (p.contact_person if p and p.contact_person else l.contact_person))
        has_photos = bool(photos_count_by_profile.get(p.id, 0) > 0 if p else False)
        health = calculate_customer_health(
            last_visit_at=p.last_visit_at if p else None,
            visit_frequency=p.visit_frequency if p else "weekly",
            last_voucher_date=v_date,
            voucher_count=v_count,
            has_verified_location=p.location_verified if p else False,
            has_contact=has_contact,
            has_photos=has_photos,
            now=now
        )

        cust = {
            "key": f"tally_{l.ledger_id}",
            "source": "tally",
            "ledger_id": l.ledger_id,
            "profile_id": p.id if p else None,
            "name": l.name,
            "contact_person": (p.contact_person if p and p.contact_person else l.contact_person) or "",
            "phone": (p.phone if p and p.phone else l.phone) or "",
            "mobile": (p.whatsapp_number if p and p.whatsapp_number else mobile_clean) or "",
            "whatsapp_number": (p.whatsapp_number if p and p.whatsapp_number else mobile_clean) or "",
            "email": (p.email if p and p.email else l.email) or "",
            "address": (p.address if p and p.address else addr_clean) or "",
            "locality": loc or "",
            "city": c_city or "",
            "state": l.state or (p.state if p else ""),
            "pincode": l.pincode or (p.pincode if p else ""),
            "route_name": r_name or "",
            "shop_type": (p.shop_type if p else "Retailer") or "Retailer",
            "tags": [t.strip() for t in p.tags.split(",") if t.strip()] if (p and p.tags) else [],
            "priority": (p.priority if p else "medium") or "medium",
            "latitude": lat,
            "longitude": lon,
            "has_location": lat is not None and lon is not None,
            "location_verified": p.location_verified if p else False,
            "maps_url": build_maps_url(lat, lon, addr_clean),
            "distance_from_me_meters": dist_from_me,
            "last_visit_at": p.last_visit_at.isoformat() if (p and p.last_visit_at) else None,
            "days_since_last_visit": recency["days"],
            "visit_recency_category": recency["category"],
            "visit_recency_label": recency["label"],
            "health_score": health,
            "total_visits": p.total_visits if p else 0,
            "notes": p.notes if p else "",
            "latest_verification_status": latest_log.verification_status if latest_log else ("NO_CHECK_IN" if (lat and lon) else "NO_BASE_COORDINATE"),
            "latest_checkin_distance": latest_log.distance_from_base_meters if latest_log else None,
            "latest_checkin_at": latest_log.created_at.isoformat() if latest_log else None,
            "owners": owners_by_profile.get(p.id, []) if p else [],
            "owners_count": len(owners_by_profile.get(p.id, [])) if p else 0,
        }
        customers.append(cust)

    # Process standalone field profiles (prospects / non-accounting shop profiles)
    for p in standalone_profiles:
        latest_log = latest_log_by_profile.get(p.id)
        dist_from_me = None
        if my_lat is not None and my_lon is not None and p.latitude is not None and p.longitude is not None:
            dist_from_me = calculate_haversine_distance(my_lat, my_lon, p.latitude, p.longitude)

        e_loc, e_city = extract_locality_and_city(p.address)
        loc = (p.locality.strip() if p.locality else e_loc) or ""
        c_city = (p.city.strip() if p.city else e_city) or ""

        # Visit Recency calculation
        recency = calculate_visit_recency(p.last_visit_at, now)

        # Health score calculation
        has_contact = bool(p.phone or p.contact_person)
        has_photos = bool(photos_count_by_profile.get(p.id, 0) > 0)
        health = calculate_customer_health(
            last_visit_at=p.last_visit_at,
            visit_frequency=p.visit_frequency,
            last_voucher_date=None,
            voucher_count=0,
            has_verified_location=p.location_verified,
            has_contact=has_contact,
            has_photos=has_photos,
            now=now
        )

        cust = {
            "key": f"profile_{p.id}",
            "source": "field_profile",
            "ledger_id": None,
            "profile_id": p.id,
            "name": p.custom_name or "Unnamed Shop",
            "contact_person": p.contact_person or "",
            "phone": p.phone or "",
            "mobile": p.phone or p.whatsapp_number or "",
            "whatsapp_number": p.whatsapp_number or p.phone or "",
            "email": p.email or "",
            "address": p.address or "",
            "locality": loc or "",
            "city": c_city or "",
            "state": p.state or "",
            "pincode": p.pincode or "",
            "route_name": p.route_name or "",
            "shop_type": p.shop_type or "Retailer",
            "tags": [t.strip() for t in p.tags.split(",") if t.strip()] if p.tags else [],
            "priority": p.priority or "medium",
            "latitude": p.latitude,
            "longitude": p.longitude,
            "has_location": p.latitude is not None and p.longitude is not None,
            "location_verified": p.location_verified,
            "maps_url": build_maps_url(p.latitude, p.longitude, p.address),
            "distance_from_me_meters": dist_from_me,
            "last_visit_at": p.last_visit_at.isoformat() if p.last_visit_at else None,
            "days_since_last_visit": recency["days"],
            "visit_recency_category": recency["category"],
            "visit_recency_label": recency["label"],
            "health_score": health,
            "total_visits": p.total_visits or 0,
            "notes": p.notes or "",
            "latest_verification_status": latest_log.verification_status if latest_log else ("NO_CHECK_IN" if (p.latitude and p.longitude) else "NO_BASE_COORDINATE"),
            "latest_checkin_distance": latest_log.distance_from_base_meters if latest_log else None,
            "latest_checkin_at": latest_log.created_at.isoformat() if latest_log else None,
            "owners": owners_by_profile.get(p.id, []),
            "owners_count": len(owners_by_profile.get(p.id, [])),
        }
        customers.append(cust)

    # 8. Apply filters in memory
    filtered = customers

    if search and isinstance(search, str):
        s_lower = search.strip().lower()
        filtered = [
            c for c in filtered
            if s_lower in c["name"].lower()
            or s_lower in (c["contact_person"] or "").lower()
            or s_lower in (c["mobile"] or "").lower()
            or s_lower in (c["phone"] or "").lower()
            or s_lower in (c["whatsapp_number"] or "").lower()
            or s_lower in (c["locality"] or "").lower()
            or s_lower in (c["city"] or "").lower()
            or s_lower in (c["address"] or "").lower()
            or any(s_lower in tag.lower() for tag in c["tags"])
            or any(s_lower in ow["name"].lower() or s_lower in (ow.get("phone") or "").lower() for ow in c.get("owners", []))
        ]

    if locality and isinstance(locality, str) and locality != "all":
        loc_lower = locality.strip().lower()
        filtered = [
            c for c in filtered
            if loc_lower in (c["locality"] or "").lower()
            or loc_lower in (c["city"] or "").lower()
            or loc_lower in (c["address"] or "").lower()
        ]

    if city and isinstance(city, str) and city != "all":
        city_lower = city.strip().lower()
        filtered = [c for c in filtered if (c["city"] or "").lower() == city_lower]

    if route_name and isinstance(route_name, str) and route_name != "all":
        route_lower = route_name.strip().lower()
        filtered = [c for c in filtered if (c["route_name"] or "").lower() == route_lower]

    if isinstance(location_status, str):
        if location_status == "tagged":
            filtered = [c for c in filtered if c["has_location"]]
        elif location_status == "missing":
            filtered = [c for c in filtered if not c["has_location"]]

    if isinstance(verification_filter, str):
        if verification_filter == "verified":
            filtered = [c for c in filtered if c["latest_verification_status"] == "VERIFIED_ON_SITE"]
        elif verification_filter == "mismatch":
            filtered = [c for c in filtered if c["latest_verification_status"] == "MISMATCH_FAR"]
        elif verification_filter == "nearby":
            filtered = [c for c in filtered if c["latest_verification_status"] == "NEARBY"]
        elif verification_filter == "unverified":
            filtered = [c for c in filtered if c["latest_verification_status"] in ("NO_CHECK_IN", "NO_BASE_COORDINATE")]

    # Nearby Distance Radius Filter
    if isinstance(radius_km, (int, float)) and radius_km > 0:
        max_dist_meters = radius_km * 1000.0
        filtered = [
            c for c in filtered
            if c["distance_from_me_meters"] is not None and c["distance_from_me_meters"] <= max_dist_meters
        ]

    # Visit Recency Filter
    if isinstance(visit_recency, str) and visit_recency != "all":
        if visit_recency == "visited_recent":
            filtered = [c for c in filtered if c["days_since_last_visit"] is not None and c["days_since_last_visit"] <= 7]
        elif visit_recency == "due_soon":
            filtered = [c for c in filtered if c["days_since_last_visit"] is not None and 7 < c["days_since_last_visit"] <= 14]
        elif visit_recency == "overdue":
            filtered = [c for c in filtered if c["days_since_last_visit"] is not None and c["days_since_last_visit"] > 14]
        elif visit_recency == "critical":
            filtered = [c for c in filtered if c["days_since_last_visit"] is not None and c["days_since_last_visit"] > 30]
        elif visit_recency == "never":
            filtered = [c for c in filtered if c["days_since_last_visit"] is None]

    # Health Grade Filter
    if isinstance(health_grade, str) and health_grade != "all":
        hg_upper = health_grade.upper()
        filtered = [c for c in filtered if c.get("health_score", {}).get("grade") == hg_upper]

    if not isinstance(sort_by, str):
        sort_by = "name_asc"

    # Sort logic
    if sort_by == "nearest":
        filtered.sort(
            key=lambda c: (
                c["distance_from_me_meters"] is None,
                c["distance_from_me_meters"] if c["distance_from_me_meters"] is not None else float("inf"),
                c["name"].lower()
            )
        )
    elif sort_by == "name_desc":
        filtered.sort(key=lambda c: c["name"].lower(), reverse=True)
    elif sort_by == "missing_gps":
        filtered.sort(key=lambda c: (c["has_location"], c["name"].lower()))
    elif sort_by == "last_visited":
        filtered.sort(key=lambda c: (c["last_visit_at"] is None, c["last_visit_at"] or ""), reverse=True)
    elif sort_by == "health_desc":
        filtered.sort(key=lambda c: c.get("health_score", {}).get("score", 0), reverse=True)
    elif sort_by == "health_asc":
        filtered.sort(key=lambda c: c.get("health_score", {}).get("score", 0))
    else:
        filtered.sort(key=lambda c: c["name"].lower())

    # Summary metrics
    total_count = len(customers)
    tagged_count = sum(1 for c in customers if c["has_location"])
    missing_count = total_count - tagged_count
    mismatch_count = sum(1 for c in customers if c["latest_verification_status"] == "MISMATCH_FAR")
    verified_count = sum(1 for c in customers if c["latest_verification_status"] == "VERIFIED_ON_SITE")
    healthy_count = sum(1 for c in customers if c.get("health_score", {}).get("grade") == "HEALTHY")
    fair_count = sum(1 for c in customers if c.get("health_score", {}).get("grade") == "FAIR")
    at_risk_count = sum(1 for c in customers if c.get("health_score", {}).get("grade") == "AT_RISK")

    return {
        "customers": filtered,
        "metrics": {
            "total": total_count,
            "tagged": tagged_count,
            "missing_location": missing_count,
            "mismatch_count": mismatch_count,
            "verified_count": verified_count,
            "healthy_count": healthy_count,
            "fair_count": fair_count,
            "at_risk_count": at_risk_count,
        }
    }


@router.get("/localities")
async def get_localities_and_routes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return distinct localities, cities, and routes with customer counts for instant filter chips."""
    from collections import Counter

    grp_res = await db.execute(select(MstGroup).where(MstGroup.company_id == user.company_id))
    groups = grp_res.scalars().all()
    groups_dict = {g.group_id: g for g in groups}

    def is_sundry_debtor(group_id: Optional[int]) -> bool:
        curr_id = group_id
        visited = set()
        while curr_id and curr_id in groups_dict and curr_id not in visited:
            visited.add(curr_id)
            grp = groups_dict[curr_id]
            if grp.name and grp.name.strip().lower() == "sundry debtors":
                return True
            curr_id = grp.parent_group_id
        return False

    profiles_res = await db.execute(
        select(CustomerProfile).where(CustomerProfile.company_id == user.company_id)
    )
    profiles = profiles_res.scalars().all()
    profile_by_ledger = {p.ledger_id: p for p in profiles if p.ledger_id is not None}

    loc_counter = Counter()
    city_counter = Counter()
    routes_set = set()

    ledger_res = await db.execute(select(MstLedger).where(MstLedger.company_id == user.company_id))
    all_ledgers = ledger_res.scalars().all()

    for l in all_ledgers:
        if not is_sundry_debtor(l.group_id):
            continue
        p = profile_by_ledger.get(l.ledger_id)
        if p and p.locality:
            loc_counter[p.locality.strip()] += 1
        else:
            e_loc, e_city = extract_locality_and_city(l.address)
            if e_loc:
                loc_counter[e_loc] += 1

        if p and p.city:
            city_counter[p.city.strip()] += 1
        else:
            e_loc, e_city = extract_locality_and_city(l.address)
            if e_city:
                city_counter[e_city] += 1

        if p and p.route_name:
            routes_set.add(p.route_name.strip())

    for p in profiles:
        if p.ledger_id is None:
            if p.locality:
                loc_counter[p.locality.strip()] += 1
            if p.city:
                city_counter[p.city.strip()] += 1
            if p.route_name:
                routes_set.add(p.route_name.strip())

    top_localities = [
        {"name": name, "count": count}
        for name, count in loc_counter.most_common(50)
        if name
    ]
    top_cities = [
        {"name": name, "count": count}
        for name, count in city_counter.most_common(30)
        if name
    ]

    return {
        "localities": top_localities,
        "cities": top_cities,
        "routes": sorted(list(routes_set))
    }


@router.get("/unlinked-ledgers")
async def get_unlinked_ledgers(
    search: Optional[str] = Query(None, description="Search ledger name, address, phone"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch Tally Sundry Debtors that are NOT yet linked to any CustomerProfile.
    Admin only. Zero accounting impact.
    """
    check_is_admin(user)

    # 1. Fetch all groups to identify Sundry Debtors
    grp_res = await db.execute(
        select(MstGroup).where(MstGroup.company_id == user.company_id)
    )
    groups = grp_res.scalars().all()
    groups_dict = {g.group_id: g for g in groups}

    def is_sundry_debtor(group_id: Optional[int]) -> bool:
        curr_id = group_id
        visited = set()
        while curr_id and curr_id in groups_dict and curr_id not in visited:
            visited.add(curr_id)
            grp = groups_dict[curr_id]
            if grp.name and grp.name.strip().lower() == "sundry debtors":
                return True
            curr_id = grp.parent_group_id
        return False

    # 2. Get set of already linked ledger_ids
    linked_res = await db.execute(
        select(CustomerProfile.ledger_id).where(
            CustomerProfile.company_id == user.company_id,
            CustomerProfile.ledger_id.isnot(None)
        )
    )
    already_linked_ids = set(linked_res.scalars().all())

    # 3. Fetch all Tally ledgers for this company
    ledger_res = await db.execute(
        select(MstLedger).where(MstLedger.company_id == user.company_id)
    )
    all_ledgers = ledger_res.scalars().all()

    unlinked = []
    for l in all_ledgers:
        if l.ledger_id in already_linked_ids:
            continue
        if not is_sundry_debtor(l.group_id):
            continue

        addr_clean = l.address or ""
        mobile_clean = l.mobile or ""
        if addr_clean and " | Mobile: " in addr_clean:
            parts = addr_clean.split(" | Mobile: ")
            addr_clean = parts[0]
            if not mobile_clean and len(parts) > 1:
                mobile_clean = parts[1]

        if search and isinstance(search, str) and search.strip():
            s = search.strip().lower()
            if (
                s not in l.name.lower()
                and s not in addr_clean.lower()
                and s not in mobile_clean.lower()
                and s not in (l.state or "").lower()
            ):
                continue

        unlinked.append({
            "ledger_id": l.ledger_id,
            "name": l.name,
            "address": addr_clean,
            "mobile": mobile_clean,
            "state": l.state or "",
            "pincode": l.pincode or "",
        })

    unlinked.sort(key=lambda x: x["name"].lower())
    return {"unlinked_ledgers": unlinked}


@router.post("")
async def create_field_customer(
    req: CustomerCreateRequest,
    user: User = Depends(require_permission("visits", "create")),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a new customer profile strictly in the portal DB.
    Guaranteed ZERO Tally accounting impact.
    """
    profile = CustomerProfile(
        company_id=user.company_id,
        ledger_id=None,  # Standalone field prospect / profile
        custom_name=req.name.strip(),
        contact_person=req.contact_person.strip() if req.contact_person else None,
        phone=req.phone.strip() if req.phone else None,
        whatsapp_number=req.whatsapp_number.strip() if req.whatsapp_number else req.phone,
        email=req.email.strip() if req.email else None,
        address=req.address.strip() if req.address else None,
        locality=req.locality.strip() if req.locality else None,
        city=req.city.strip() if req.city else None,
        state=req.state.strip() if req.state else None,
        pincode=req.pincode.strip() if req.pincode else None,
        route_name=req.route_name.strip() if req.route_name else None,
        shop_type=req.shop_type or "Retailer",
        tags=req.tags.strip() if req.tags else None,
        priority=req.priority or "medium",
        visit_frequency=req.visit_frequency or "weekly",
        notes=req.notes.strip() if req.notes else None,
        latitude=req.latitude,
        longitude=req.longitude,
        location_verified=True if (req.latitude and req.longitude) else False,
        location_verified_at=func.now() if (req.latitude and req.longitude) else None,
        created_by=user.user_id,
    )
    db.add(profile)
    await db.flush()

    # If coordinates were submitted, record first location log entry
    if req.latitude is not None and req.longitude is not None:
        loc_log = CustomerLocationLog(
            company_id=user.company_id,
            customer_profile_id=profile.id,
            ledger_id=None,
            user_id=user.user_id,
            latitude=req.latitude,
            longitude=req.longitude,
            distance_from_base_meters=0.0,
            verification_status="ESTABLISHED_BASE",
            source="manual_tag",
            notes=f"Initial location established on creation by {user.username}"
        )
        db.add(loc_log)

    # Automatically create primary owner record if contact person or phone is provided
    if req.contact_person or req.phone:
        owner = CustomerOwner(
            company_id=user.company_id,
            customer_profile_id=profile.id,
            name=req.contact_person.strip() if req.contact_person else req.name.strip(),
            designation="Owner / Proprietor",
            phone=req.phone.strip() if req.phone else None,
            whatsapp_number=req.whatsapp_number.strip() if req.whatsapp_number else req.phone,
            email=req.email.strip() if req.email else None,
            is_primary=True,
            notes="Primary contact person recorded during customer registration",
        )
        db.add(owner)

    await db.commit()
    await db.refresh(profile)

    return {
        "success": True,
        "id": profile.id,
        "message": f"Customer profile for '{profile.custom_name}' created successfully (Portal only, no accounting modified)."
    }


@router.put("/{target_id}/profile")
async def update_customer_profile(
    target_id: str,
    req: CustomerProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update extended customer profile fields (locality, city, route, tags, notes, contact).
    target_id can be 'tally_123', 'ledger_123', or 'profile_456'.
    """
    clean_id = str(target_id).strip()
    profile = None
    if clean_id.startswith("tally_") or clean_id.startswith("ledger_"):
        lid = int(clean_id.replace("tally_", "").replace("ledger_", ""))
        res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.ledger_id == lid
            )
        )
        profile = res.scalars().first()
        if not profile:
            profile = CustomerProfile(
                company_id=user.company_id,
                ledger_id=lid,
                created_by=user.user_id
            )
            db.add(profile)
    elif clean_id.startswith("profile_"):
        pid = int(clean_id.replace("profile_", ""))
        res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.id == pid
            )
        )
        profile = res.scalars().first()
    else:
        # Fallback treat as integer ledger_id or profile_id
        try:
            val = int(clean_id)
            res = await db.execute(
                select(CustomerProfile).where(
                    CustomerProfile.company_id == user.company_id,
                    or_(CustomerProfile.id == val, CustomerProfile.ledger_id == val)
                )
            )
            profile = res.scalars().first()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer identifier")

    if not profile:
        raise HTTPException(status_code=404, detail="Customer profile not found")

    if req.contact_person is not None:
        profile.contact_person = req.contact_person
    if req.phone is not None:
        profile.phone = req.phone
    if req.whatsapp_number is not None:
        profile.whatsapp_number = req.whatsapp_number
    if req.email is not None:
        profile.email = req.email
    if req.address is not None:
        profile.address = req.address
    if req.locality is not None:
        profile.locality = req.locality
    if req.city is not None:
        profile.city = req.city
    if req.state is not None:
        profile.state = req.state
    if req.pincode is not None:
        profile.pincode = req.pincode
    if req.route_name is not None:
        profile.route_name = req.route_name
    if req.shop_type is not None:
        profile.shop_type = req.shop_type
    if req.tags is not None:
        profile.tags = req.tags
    if req.priority is not None:
        profile.priority = req.priority
    if req.visit_frequency is not None:
        profile.visit_frequency = req.visit_frequency
    if req.notes is not None:
        profile.notes = req.notes

    profile.updated_at = func.now()
    await db.commit()

    return {"success": True, "message": "Customer profile updated successfully"}


@router.post("/{target_id}/link-ledger")
async def link_customer_to_ledger(
    target_id: str,
    req: LinkLedgerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Link an unmapped customer profile to an existing Tally Sundry Debtor ledger.
    Admin only. Available only for customer profiles without a ledger ID mapping.
    Guaranteed ZERO Tally accounting changes.
    """
    check_is_admin(user)

    # 1. Resolve customer profile
    profile = None
    clean_id = str(target_id).strip()
    if clean_id.startswith("profile_"):
        pid = int(clean_id.replace("profile_", ""))
        res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.id == pid
            )
        )
        profile = res.scalars().first()
    elif clean_id.startswith("tally_") or clean_id.startswith("ledger_"):
        raise HTTPException(
            status_code=400,
            detail="Cannot link an already mapped Tally customer."
        )
    else:
        try:
            pid = int(clean_id)
            res = await db.execute(
                select(CustomerProfile).where(
                    CustomerProfile.company_id == user.company_id,
                    CustomerProfile.id == pid
                )
            )
            profile = res.scalars().first()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid profile identifier")

    if not profile:
        raise HTTPException(status_code=404, detail="Customer profile not found")

    # Strict constraint: Only for profiles without an existing ledger ID mapping
    if profile.ledger_id is not None:
        raise HTTPException(
            status_code=400,
            detail="This customer profile is already linked to a Tally ledger."
        )

    # 2. Validate the target ledger exists in company and is not already linked
    led_res = await db.execute(
        select(MstLedger).where(
            MstLedger.company_id == user.company_id,
            MstLedger.ledger_id == req.ledger_id
        )
    )
    ledger = led_res.scalars().first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Selected Tally ledger not found in this company.")

    existing_link_res = await db.execute(
        select(CustomerProfile).where(
            CustomerProfile.company_id == user.company_id,
            CustomerProfile.ledger_id == req.ledger_id
        )
    )
    if existing_link_res.scalars().first():
        raise HTTPException(
            status_code=400,
            detail=f"The ledger '{ledger.name}' is already linked to another customer profile."
        )

    # 3. Perform the link (strictly portal DB metadata)
    profile.ledger_id = req.ledger_id
    profile.updated_at = func.now()

    # Backfill ledger_id in existing location logs for this customer profile
    await db.execute(
        update(CustomerLocationLog)
        .where(
            CustomerLocationLog.customer_profile_id == profile.id,
            CustomerLocationLog.company_id == user.company_id
        )
        .values(ledger_id=req.ledger_id)
    )

    # Record an audit log entry for the linking event
    audit_log = CustomerLocationLog(
        company_id=user.company_id,
        customer_profile_id=profile.id,
        ledger_id=req.ledger_id,
        user_id=user.user_id,
        latitude=profile.latitude or 0.0,
        longitude=profile.longitude or 0.0,
        distance_from_base_meters=0.0,
        verification_status="LEDGER_LINKED",
        source="admin_override",
        notes=f"Admin {user.username} linked profile '{profile.custom_name}' to Tally ledger '{ledger.name}' (ID #{ledger.ledger_id})"
    )
    db.add(audit_log)

    await db.commit()
    await db.refresh(profile)

    return {
        "success": True,
        "message": f"Successfully linked '{profile.custom_name}' to Tally ledger '{ledger.name}'.",
        "ledger_id": ledger.ledger_id,
        "ledger_name": ledger.name
    }


@router.post("/{target_id}/tag-location")
async def tag_customer_location(
    target_id: str,
    req: TagLocationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually tag / calibrate master GPS coordinate for a customer shop.
    Records an audit log entry in customer_location_logs.
    """
    clean_id = str(target_id).strip()
    profile = None
    ledger_id = None
    if clean_id.startswith("tally_") or clean_id.startswith("ledger_"):
        ledger_id = int(clean_id.replace("tally_", "").replace("ledger_", ""))
        res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.ledger_id == ledger_id
            )
        )
        profile = res.scalars().first()
        if not profile:
            profile = CustomerProfile(
                company_id=user.company_id,
                ledger_id=ledger_id,
                created_by=user.user_id
            )
            db.add(profile)
            await db.flush()
    elif clean_id.startswith("profile_"):
        pid = int(clean_id.replace("profile_", ""))
        res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.id == pid
            )
        )
        profile = res.scalars().first()
        if profile:
            ledger_id = profile.ledger_id
    else:
        try:
            val = int(clean_id)
            res = await db.execute(
                select(CustomerProfile).where(
                    CustomerProfile.company_id == user.company_id,
                    or_(CustomerProfile.id == val, CustomerProfile.ledger_id == val)
                )
            )
            profile = res.scalars().first()
            if profile:
                ledger_id = profile.ledger_id
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer identifier")

    if not profile:
        raise HTTPException(status_code=404, detail="Customer profile not found")

    old_lat = profile.latitude
    old_lon = profile.longitude

    # Update master GPS coordinates
    profile.latitude = req.latitude
    profile.longitude = req.longitude
    profile.location_verified = True
    profile.location_verified_at = func.now()

    # Determine status & log
    verification_status = "ESTABLISHED_BASE" if (old_lat is None or old_lon is None) else "ADMIN_OVERRIDE"

    log_entry = CustomerLocationLog(
        company_id=user.company_id,
        customer_profile_id=profile.id,
        ledger_id=ledger_id,
        user_id=user.user_id,
        latitude=req.latitude,
        longitude=req.longitude,
        distance_from_base_meters=0.0,
        verification_status=verification_status,
        source="manual_tag" if user.role != "admin" else "admin_override",
        notes=req.reason or f"Location tagged by {user.username}"
    )
    db.add(log_entry)
    await db.commit()

    return {
        "success": True,
        "latitude": req.latitude,
        "longitude": req.longitude,
        "message": f"Master shop location tagged successfully at {req.latitude}, {req.longitude}"
    }


@router.get("/{target_id}/location-history")
async def get_customer_location_history(
    target_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full history of GPS taggings and check-ins for this shop over time.
    Audits whether salespeople checked in near the actual shop location.
    """
    clean_id = str(target_id).strip()
    profile_id = None
    ledger_id = None

    if clean_id.startswith("tally_") or clean_id.startswith("ledger_"):
        ledger_id = int(clean_id.replace("tally_", "").replace("ledger_", ""))
        p_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.ledger_id == ledger_id
            )
        )
        p = p_res.scalars().first()
        if p:
            profile_id = p.id
    elif clean_id.startswith("profile_"):
        profile_id = int(clean_id.replace("profile_", ""))
    else:
        try:
            val = int(clean_id)
            profile_id = val
        except ValueError:
            pass

    # Build query
    conditions = [CustomerLocationLog.company_id == user.company_id]
    or_conds = []
    if profile_id:
        or_conds.append(CustomerLocationLog.customer_profile_id == profile_id)
    if ledger_id:
        or_conds.append(CustomerLocationLog.ledger_id == ledger_id)

    if not or_conds:
        return {"history": []}

    conditions.append(or_(*or_conds))

    from sqlalchemy.orm import selectinload
    stmt = (
        select(CustomerLocationLog)
        .options(selectinload(CustomerLocationLog.user))
        .where(and_(*conditions))
        .order_by(desc(CustomerLocationLog.created_at))
        .limit(50)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    output = []
    for log in logs:
        u_name = log.user.username if (log.user and log.user.username) else (log.user.email if log.user else f"User #{log.user_id}")
        output.append({
            "id": log.id,
            "latitude": log.latitude,
            "longitude": log.longitude,
            "distance_from_base_meters": log.distance_from_base_meters,
            "verification_status": log.verification_status,
            "source": log.source,
            "user_id": log.user_id,
            "salesperson": u_name,
            "notes": log.notes,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={log.latitude},{log.longitude}"
        })

    return {"history": output}


@router.get("/{target_id}")
async def get_customer_profile_detail(
    target_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get full 360-degree customer profile for the customer profile page:
    - Basic shop details & contact person
    - Media (owner photo, storefront photo)
    - Photos gallery (all uploaded photos from ImageKit)
    - GPS coordinates & verification audit status
    - Recent sales visits timeline & location logs
    """
    from sqlalchemy.orm import selectinload
    from app.routers.visits import SalesVisit

    profile = None
    ledger = None

    if target_id.startswith("tally_") or target_id.startswith("ledger_"):
        lid_str = target_id.replace("tally_", "").replace("ledger_", "")
        lid = int(lid_str)
        led_res = await db.execute(
            select(MstLedger).where(
                MstLedger.company_id == user.company_id,
                MstLedger.ledger_id == lid
            )
        )
        ledger = led_res.scalars().first()
        prof_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.ledger_id == lid
            )
        )
        profile = prof_res.scalars().first()
    elif target_id.startswith("profile_"):
        pid = int(target_id.replace("profile_", ""))
        prof_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.id == pid
            )
        )
        profile = prof_res.scalars().first()
        if profile and profile.ledger_id:
            led_res = await db.execute(
                select(MstLedger).where(
                    MstLedger.company_id == user.company_id,
                    MstLedger.ledger_id == profile.ledger_id
                )
            )
            ledger = led_res.scalars().first()
    else:
        try:
            val = int(target_id)
            prof_res = await db.execute(
                select(CustomerProfile).where(
                    CustomerProfile.company_id == user.company_id,
                    or_(CustomerProfile.id == val, CustomerProfile.ledger_id == val)
                )
            )
            profile = prof_res.scalars().first()
            if profile and profile.ledger_id:
                led_res = await db.execute(
                    select(MstLedger).where(
                        MstLedger.company_id == user.company_id,
                        MstLedger.ledger_id == profile.ledger_id
                    )
                )
                ledger = led_res.scalars().first()
            elif not profile:
                led_res = await db.execute(
                    select(MstLedger).where(
                        MstLedger.company_id == user.company_id,
                        MstLedger.ledger_id == val
                    )
                )
                ledger = led_res.scalars().first()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer identifier")

    if not profile and not ledger:
        raise HTTPException(status_code=404, detail="Customer not found")

    addr_clean = (ledger.address or "") if ledger else (profile.address or "")
    mobile_clean = (ledger.mobile or "") if ledger else ""
    if addr_clean and " | Mobile: " in addr_clean:
        parts = addr_clean.split(" | Mobile: ")
        addr_clean = parts[0]
        if not mobile_clean and len(parts) > 1:
            mobile_clean = parts[1]

    e_loc, e_city = extract_locality_and_city(addr_clean)
    loc = (profile.locality.strip() if profile and profile.locality else e_loc) or ""
    c_city = (profile.city.strip() if profile and profile.city else (e_city or (ledger.state if ledger else ""))) or ""

    name = (ledger.name if ledger else profile.custom_name) or "Unnamed Shop"
    lat = profile.latitude if profile else None
    lon = profile.longitude if profile else None

    # Fetch Photos
    photos = []
    if profile:
        photo_stmt = (
            select(CustomerPhoto)
            .options(selectinload(CustomerPhoto.user))
            .where(
                CustomerPhoto.company_id == user.company_id,
                CustomerPhoto.customer_profile_id == profile.id
            )
            .order_by(desc(CustomerPhoto.created_at))
        )
        photo_res = await db.execute(photo_stmt)
        for ph in photo_res.scalars().all():
            u_name = ph.user.username if ph.user else "Staff"
            photos.append({
                "id": ph.id,
                "photo_type": ph.photo_type,
                "imagekit_url": ph.imagekit_url,
                "imagekit_thumbnail_url": ph.imagekit_thumbnail_url or ph.imagekit_url,
                "imagekit_file_path": ph.imagekit_file_path,
                "caption": ph.caption,
                "latitude": ph.latitude,
                "longitude": ph.longitude,
                "is_primary": ph.is_primary,
                "uploaded_by_name": u_name,
                "created_at": ph.created_at.isoformat() if ph.created_at else None,
            })

    # Fetch Recent Visits
    visits = []
    visit_conds = []
    if ledger:
        visit_conds.append(SalesVisit.ledger_id == ledger.ledger_id)
    if profile and profile.custom_name:
        visit_conds.append(SalesVisit.custom_shop_name == profile.custom_name)

    if visit_conds:
        v_stmt = (
            select(SalesVisit)
            .options(selectinload(SalesVisit.user))
            .where(or_(*visit_conds))
            .order_by(desc(SalesVisit.created_at))
            .limit(15)
        )
        v_res = await db.execute(v_stmt)
        for v in v_res.scalars().all():
            u_name = v.user.username if v.user else "Sales Rep"
            visits.append({
                "id": v.id,
                "salesperson": u_name,
                "comments": v.comments,
                "latitude": v.latitude,
                "longitude": v.longitude,
                "photo_url": v.photo_url,
                "status": v.status,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            })

    # Fetch Latest location log
    latest_log = None
    if profile:
        log_stmt = (
            select(CustomerLocationLog)
            .where(
                CustomerLocationLog.company_id == user.company_id,
                CustomerLocationLog.customer_profile_id == profile.id
            )
            .order_by(desc(CustomerLocationLog.created_at))
            .limit(1)
        )
        log_res = await db.execute(log_stmt)
        latest_log = log_res.scalars().first()

    # Fetch all owners / partners
    owners_list = []
    if profile:
        owners_stmt = (
            select(CustomerOwner)
            .where(
                CustomerOwner.company_id == user.company_id,
                CustomerOwner.customer_profile_id == profile.id
            )
            .order_by(desc(CustomerOwner.is_primary), CustomerOwner.id.asc())
        )
        owners_res = await db.execute(owners_stmt)
        for o in owners_res.scalars().all():
            owners_list.append({
                "id": o.id,
                "name": o.name,
                "designation": o.designation or "Owner / Partner",
                "phone": o.phone or "",
                "whatsapp_number": o.whatsapp_number or "",
                "email": o.email or "",
                "photo_url": o.photo_url,
                "imagekit_file_id": o.imagekit_file_id,
                "is_primary": o.is_primary,
                "notes": o.notes or "",
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })

    # If no owners in customer_owners table, fallback to the main contact person as virtual primary owner
    if not owners_list:
        fallback_name = (profile.contact_person if profile and profile.contact_person else None) or (ledger.contact_person if ledger and ledger.contact_person else None) or (ledger.name if ledger else "Primary Owner")
        fallback_phone = (profile.phone if profile and profile.phone else None) or (ledger.phone if ledger and ledger.phone else None) or ""
        fallback_wa = (profile.whatsapp_number if profile and profile.whatsapp_number else None) or mobile_clean or fallback_phone
        owners_list.append({
            "id": None,
            "name": fallback_name,
            "designation": "Primary Owner",
            "phone": fallback_phone,
            "whatsapp_number": fallback_wa,
            "email": (profile.email if profile and profile.email else (ledger.email if ledger else "")) or "",
            "photo_url": profile.customer_photo_url if profile else None,
            "imagekit_file_id": None,
            "is_primary": True,
            "notes": "",
            "created_at": None,
        })

    now = datetime.now()
    recency = calculate_visit_recency(profile.last_visit_at if profile else None, now)

    v_date, v_count = (None, 0)
    if ledger:
        try:
            v_res = await db.execute(
                select(
                    func.max(TrnVoucher.voucher_date).label("last_voucher_date"),
                    func.count(TrnVoucher.voucher_id).label("voucher_count")
                )
                .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
                .where(
                    TrnAccounting.ledger_id == ledger.ledger_id,
                    TrnVoucher.company_id == user.company_id,
                    TrnVoucher.is_cancelled == False
                )
            )
            row = v_res.first()
            if row:
                v_date = row.last_voucher_date
                v_count = row.voucher_count or 0
        except Exception:
            pass

    has_contact = bool((profile.phone if profile and profile.phone else (ledger.phone if ledger else None)) or (profile.contact_person if profile and profile.contact_person else (ledger.contact_person if ledger else None)))
    has_photos = len(photos) > 0
    health = calculate_customer_health(
        last_visit_at=profile.last_visit_at if profile else None,
        visit_frequency=profile.visit_frequency if profile else "weekly",
        last_voucher_date=v_date,
        voucher_count=v_count,
        has_verified_location=profile.location_verified if profile else False,
        has_contact=has_contact,
        has_photos=has_photos,
        now=now
    )

    # ── Financial Ledger Statement & Vouchers ──
    financial_summary = None
    recent_vouchers = []

    if ledger:
        op_bal = float(ledger.opening_balance or 0)
        op_type = ledger.opening_balance_type or "Dr"
        
        # Opening balance in Tally is as of FY start (2026-04-01).
        # Any vouchers dated before 2026-04-01 are already included in ledger.opening_balance.
        fy_anchor_date = datetime.strptime("2026-04-01", "%Y-%m-%d").date()
        base_net = (float(ledger.opening_balance) if op_type == 'Cr' else -float(ledger.opening_balance)) if ledger.opening_balance else 0.0

        pre_fy_stmt = select(
            func.sum(TrnAccounting.credit_amount - TrnAccounting.debit_amount)
        ).join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id).where(
            TrnAccounting.ledger_id == ledger.ledger_id,
            TrnVoucher.voucher_date < fy_anchor_date,
            TrnVoucher.is_cancelled == False
        )
        pre_fy_res = await db.execute(pre_fy_stmt)
        pre_fy_val = float(pre_fy_res.scalar() or 0.0)
        true_base_net = base_net - pre_fy_val

        total_dr = 0.0
        total_cr = 0.0

        try:
            bal_stmt = (
                select(
                    func.sum(TrnAccounting.debit_amount).label("total_dr"),
                    func.sum(TrnAccounting.credit_amount).label("total_cr")
                )
                .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
                .where(
                    TrnAccounting.ledger_id == ledger.ledger_id,
                    TrnVoucher.is_cancelled == False
                )
            )
            bal_res = await db.execute(bal_stmt)
            b_row = bal_res.first()
            if b_row:
                total_dr = float(b_row.total_dr or 0)
                total_cr = float(b_row.total_cr or 0)
        except Exception:
            pass

        # Net balance across all recorded transactions (positive = Dr, negative = Cr)
        net_bal = -true_base_net + (total_dr - total_cr)

        financial_summary = {
            "closing_balance": round(abs(net_bal), 2),
            "raw_balance": round(net_bal, 2),
            "balance_type": "Dr" if net_bal >= 0 else "Cr",
            "opening_balance": round(op_bal, 2),
            "opening_balance_type": op_type,
            "total_billed_debit": round(total_dr, 2),
            "total_collected_credit": round(total_cr, 2),
        }

        try:
            v_detail_stmt = (
                select(TrnVoucher, TrnAccounting)
                .join(TrnAccounting, TrnAccounting.voucher_id == TrnVoucher.voucher_id)
                .options(selectinload(TrnVoucher.voucher_type))
                .where(
                    TrnAccounting.ledger_id == ledger.ledger_id,
                    TrnVoucher.company_id == user.company_id,
                    TrnVoucher.is_cancelled == False
                )
                .order_by(desc(TrnVoucher.voucher_date), desc(TrnVoucher.voucher_id))
                .limit(15)
            )
            v_detail_res = await db.execute(v_detail_stmt)
            for v_item, acc_item in v_detail_res.all():
                vt_name = v_item.voucher_type.name if (v_item.voucher_type and hasattr(v_item.voucher_type, 'name')) else str(v_item.voucher_type_id or "Voucher")
                dr_val = float(acc_item.debit_amount or 0)
                cr_val = float(acc_item.credit_amount or 0)
                recent_vouchers.append({
                    "voucher_id": v_item.voucher_id,
                    "date": v_item.voucher_date.isoformat() if v_item.voucher_date else None,
                    "voucher_type": vt_name,
                    "voucher_number": v_item.voucher_number or f"#{v_item.voucher_id}",
                    "debit": round(dr_val, 2),
                    "credit": round(cr_val, 2),
                    "amount": round(dr_val if dr_val > 0 else cr_val, 2),
                    "type": "Dr" if dr_val > 0 else "Cr",
                    "narration": v_item.narration or getattr(acc_item, 'entry_narration', '') or ""
                })
        except Exception as v_err:
            print(f"Warning: Could not fetch vouchers for customer statement: {v_err}")

    # ── Recent Portal Orders ──
    recent_orders = []
    try:
        from app.routers.orders import TempOrder
        o_conds = []
        if ledger:
            o_conds.append(TempOrder.ledger_id == ledger.ledger_id)
        if name:
            o_conds.append(TempOrder.custom_customer_name == name)
        if o_conds:
            o_stmt = (
                select(TempOrder)
                .options(selectinload(TempOrder.items), selectinload(TempOrder.user))
                .where(or_(*o_conds))
                .order_by(desc(TempOrder.created_at))
                .limit(10)
            )
            o_res = await db.execute(o_stmt)
            for o in o_res.scalars().all():
                items_cnt = sum(it.quantity or 0 for it in o.items) if o.items else 0
                amt = sum(float(it.quantity or 0) * float(it.price or 0) for it in o.items) if o.items else 0.0
                recent_orders.append({
                    "id": o.id,
                    "status": o.status,
                    "items_count": items_cnt,
                    "total_amount": round(amt, 2),
                    "created_by": o.user.username if o.user else "Salesperson",
                    "created_at": o.created_at.isoformat() if o.created_at else None
                })
    except Exception as ord_err:
        print(f"Warning: Could not fetch orders for customer: {ord_err}")

    # ── Recent Shop Payments ──
    recent_payments = []
    try:
        from app.models.portal_core import ShopPayment
        if ledger:
            p_stmt = (
                select(ShopPayment)
                .options(selectinload(ShopPayment.user))
                .where(ShopPayment.ledger_id == ledger.ledger_id)
                .order_by(desc(ShopPayment.created_at))
                .limit(10)
            )
            p_res = await db.execute(p_stmt)
            for p in p_res.scalars().all():
                recent_payments.append({
                    "id": p.id,
                    "amount": float(p.amount or 0),
                    "payment_mode": p.payment_mode,
                    "cheque_date": p.cheque_date.isoformat() if p.cheque_date else None,
                    "status": p.status,
                    "comments": p.comments,
                    "collected_by": p.user.username if p.user else "Staff",
                    "created_at": p.created_at.isoformat() if p.created_at else None
                })
    except Exception as pay_err:
        print(f"Warning: Could not fetch payments for customer: {pay_err}")

    return {
        "key": f"tally_{ledger.ledger_id}" if ledger else f"profile_{profile.id}",
        "source": "tally" if ledger else "field_profile",
        "ledger_id": ledger.ledger_id if ledger else (profile.ledger_id if profile else None),
        "profile_id": profile.id if profile else None,
        "name": name,
        "contact_person": (profile.contact_person if profile and profile.contact_person else (ledger.contact_person if ledger else "")) or "",
        "phone": (profile.phone if profile and profile.phone else (ledger.phone if ledger else "")) or "",
        "mobile": (profile.whatsapp_number if profile and profile.whatsapp_number else mobile_clean) or "",
        "whatsapp_number": (profile.whatsapp_number if profile and profile.whatsapp_number else mobile_clean) or "",
        "email": (profile.email if profile and profile.email else (ledger.email if ledger else "")) or "",
        "address": (profile.address if profile and profile.address else addr_clean) or "",
        "locality": loc,
        "city": c_city,
        "state": (ledger.state if ledger else (profile.state if profile else "")) or "",
        "pincode": (ledger.pincode if ledger else (profile.pincode if profile else "")) or "",
        "route_name": (profile.route_name if profile else "") or "",
        "shop_type": (profile.shop_type if profile else "Retailer") or "Retailer",
        "tags": [t.strip() for t in profile.tags.split(",") if t.strip()] if (profile and profile.tags) else [],
        "priority": (profile.priority if profile else "medium") or "medium",
        "visit_frequency": (profile.visit_frequency if profile else "weekly") or "weekly",
        "notes": (profile.notes if profile else "") or "",
        "customer_photo_url": profile.customer_photo_url if profile else None,
        "shop_photo_url": profile.shop_photo_url if profile else None,
        "latitude": lat,
        "longitude": lon,
        "has_location": lat is not None and lon is not None,
        "location_verified": profile.location_verified if profile else False,
        "location_verified_at": profile.location_verified_at.isoformat() if (profile and profile.location_verified_at) else None,
        "maps_url": build_maps_url(lat, lon, addr_clean),
        "days_since_last_visit": recency["days"],
        "visit_recency_category": recency["category"],
        "visit_recency_label": recency["label"],
        "health_score": health,
        "latest_verification_status": latest_log.verification_status if latest_log else ("NO_CHECK_IN" if (lat and lon) else "NO_BASE_COORDINATE"),
        "latest_checkin_distance": latest_log.distance_from_base_meters if latest_log else None,
        "latest_checkin_at": latest_log.created_at.isoformat() if latest_log else None,
        "owners": owners_list,
        "photos": photos,
        "visits": visits,
        "financial_summary": financial_summary,
        "recent_vouchers": recent_vouchers,
        "recent_orders": recent_orders,
        "recent_payments": recent_payments,
        "tally_details": {
            "ledger_id": ledger.ledger_id,
            "name": ledger.name,
            "group_id": ledger.group_id,
            "state": ledger.state,
            "pincode": ledger.pincode,
        } if ledger else None
    }


@router.post("/{target_id}/photos")
async def upload_customer_shop_photo(
    target_id: str,
    req: CustomerPhotoUploadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a customer owner portrait or shop photo to ImageKit in a dedicated directory.
    - Dedicated directory for Tally customer: /customers/ledger_{ledger_id}/ (with /shop subfolder for shop photos)
    - Dedicated directory for field prospect: /customers/profile_{profile_id}/
    """
    if not req.photo_base64 or len(req.photo_base64.strip()) < 20:
        raise HTTPException(status_code=400, detail="Invalid photo data provided.")

    valid_types = {"customer_owner", "shop_front", "shop_inside", "shop_board", "visiting_card", "qr_code", "other"}
    photo_type = req.photo_type if req.photo_type in valid_types else "shop_front"

    # Resolve CustomerProfile
    profile = None
    ledger_id = None
    if target_id.startswith("tally_") or target_id.startswith("ledger_"):
        lid = int(target_id.replace("tally_", "").replace("ledger_", ""))
        ledger_id = lid
        p_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.ledger_id == lid
            )
        )
        profile = p_res.scalars().first()
        if not profile:
            profile = CustomerProfile(
                company_id=user.company_id,
                ledger_id=lid,
                created_by=user.user_id
            )
            db.add(profile)
            await db.flush()
    elif target_id.startswith("profile_"):
        pid = int(target_id.replace("profile_", ""))
        p_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.id == pid
            )
        )
        profile = p_res.scalars().first()
        if profile:
            ledger_id = profile.ledger_id
    else:
        try:
            val = int(target_id)
            p_res = await db.execute(
                select(CustomerProfile).where(
                    CustomerProfile.company_id == user.company_id,
                    or_(CustomerProfile.id == val, CustomerProfile.ledger_id == val)
                )
            )
            profile = p_res.scalars().first()
            if profile:
                ledger_id = profile.ledger_id
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer identifier")

    if not profile:
        raise HTTPException(status_code=404, detail="Customer profile not found")

    # Dedicated folder in ImageKit per ledger_id as requested
    if ledger_id:
        folder = f"/customers/ledger_{ledger_id}"
    else:
        folder = f"/customers/profile_{profile.id}"

    if photo_type != "customer_owner":
        folder = f"{folder}/shop"

    ts = int(datetime.now().timestamp())
    file_name = f"{photo_type}_{ts}.jpg"
    tags = ["customer", photo_type, f"company_{user.company_id}"]
    if ledger_id:
        tags.append(f"ledger_{ledger_id}")

    # Upload to ImageKit
    ik_res = upload_customer_photo(
        file_base64=req.photo_base64,
        file_name=file_name,
        folder=folder,
        tags=tags
    )

    is_primary = req.is_primary or False
    if photo_type == "customer_owner":
        profile.customer_photo_url = ik_res["url"]
        is_primary = True
        target_owner = None
        if req.owner_id:
            ow_res = await db.execute(
                select(CustomerOwner).where(
                    CustomerOwner.id == req.owner_id,
                    CustomerOwner.company_id == user.company_id
                )
            )
            target_owner = ow_res.scalars().first()
        if not target_owner:
            ow_res = await db.execute(
                select(CustomerOwner).where(
                    CustomerOwner.customer_profile_id == profile.id,
                    CustomerOwner.company_id == user.company_id,
                    CustomerOwner.is_primary == True
                )
            )
            target_owner = ow_res.scalars().first()

        if target_owner:
            target_owner.photo_url = ik_res["url"]
            target_owner.imagekit_file_id = ik_res["file_id"]
    elif photo_type == "shop_front":
        if not profile.shop_photo_url or is_primary:
            profile.shop_photo_url = ik_res["url"]
            is_primary = True

    photo_entry = CustomerPhoto(
        company_id=user.company_id,
        customer_profile_id=profile.id,
        ledger_id=ledger_id,
        photo_type=photo_type,
        imagekit_file_id=ik_res["file_id"],
        imagekit_url=ik_res["url"],
        imagekit_thumbnail_url=ik_res["thumbnail_url"],
        imagekit_file_path=ik_res["file_path"],
        caption=req.caption,
        latitude=req.latitude,
        longitude=req.longitude,
        is_primary=is_primary,
        uploaded_by=user.user_id,
    )
    db.add(photo_entry)
    profile.updated_at = func.now()
    await db.commit()
    await db.refresh(photo_entry)

    return {
        "success": True,
        "message": f"Photo ({photo_type}) uploaded successfully to ImageKit directory '{folder}'.",
        "photo": {
            "id": photo_entry.id,
            "photo_type": photo_entry.photo_type,
            "imagekit_url": photo_entry.imagekit_url,
            "imagekit_thumbnail_url": photo_entry.imagekit_thumbnail_url,
            "imagekit_file_path": photo_entry.imagekit_file_path,
            "caption": photo_entry.caption,
            "latitude": photo_entry.latitude,
            "longitude": photo_entry.longitude,
            "is_primary": photo_entry.is_primary,
            "uploaded_by_name": user.username,
            "created_at": photo_entry.created_at.isoformat() if photo_entry.created_at else None,
        }
    }


@router.get("/{target_id}/photos")
async def list_customer_photos(
    target_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all photos uploaded for this customer."""
    from sqlalchemy.orm import selectinload

    profile_id = None
    if target_id.startswith("tally_") or target_id.startswith("ledger_"):
        lid = int(target_id.replace("tally_", "").replace("ledger_", ""))
        p_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == user.company_id,
                CustomerProfile.ledger_id == lid
            )
        )
        p = p_res.scalars().first()
        if p:
            profile_id = p.id
    elif target_id.startswith("profile_"):
        profile_id = int(target_id.replace("profile_", ""))
    else:
        try:
            val = int(target_id)
            p_res = await db.execute(
                select(CustomerProfile).where(
                    CustomerProfile.company_id == user.company_id,
                    or_(CustomerProfile.id == val, CustomerProfile.ledger_id == val)
                )
            )
            p = p_res.scalars().first()
            if p:
                profile_id = p.id
        except ValueError:
            pass

    if not profile_id:
        return {"photos": []}

    stmt = (
        select(CustomerPhoto)
        .options(selectinload(CustomerPhoto.user))
        .where(
            CustomerPhoto.company_id == user.company_id,
            CustomerPhoto.customer_profile_id == profile_id
        )
        .order_by(desc(CustomerPhoto.created_at))
    )
    res = await db.execute(stmt)
    photos = res.scalars().all()

    return {
        "photos": [
            {
                "id": ph.id,
                "photo_type": ph.photo_type,
                "imagekit_url": ph.imagekit_url,
                "imagekit_thumbnail_url": ph.imagekit_thumbnail_url or ph.imagekit_url,
                "imagekit_file_path": ph.imagekit_file_path,
                "caption": ph.caption,
                "latitude": ph.latitude,
                "longitude": ph.longitude,
                "is_primary": ph.is_primary,
                "uploaded_by_name": ph.user.username if ph.user else "Staff",
                "created_at": ph.created_at.isoformat() if ph.created_at else None,
            }
            for ph in photos
        ]
    }


@router.delete("/{target_id}/photos/{photo_id}")
async def delete_customer_photo_endpoint(
    target_id: str,
    photo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a customer photo from database and ImageKit storage."""
    res = await db.execute(
        select(CustomerPhoto).where(
            CustomerPhoto.id == photo_id,
            CustomerPhoto.company_id == user.company_id
        )
    )
    photo = res.scalars().first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Delete from ImageKit
    if photo.imagekit_file_id:
        delete_imagekit_file(photo.imagekit_file_id)

    # Clean up profile photo URL if this was primary
    prof_res = await db.execute(
        select(CustomerProfile).where(CustomerProfile.id == photo.customer_profile_id)
    )
    prof = prof_res.scalars().first()
    if prof:
        if prof.customer_photo_url == photo.imagekit_url:
            prof.customer_photo_url = None
        if prof.shop_photo_url == photo.imagekit_url:
            prof.shop_photo_url = None

    await db.delete(photo)
    await db.commit()

    return {"success": True, "message": "Photo deleted successfully from storage."}


@router.delete("/{target_id}")
async def delete_customer_endpoint(
    target_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a field-tagged customer lead that has NO Tally ledger mapping.
    Strictly blocked if the customer is linked to any Tally ledger.
    """
    # 1. Inspect target_id prefix
    clean_id = str(target_id).strip()
    if clean_id.startswith("tally_") or clean_id.startswith("ledger_"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete customer linked to a Tally ledger. Tally customers are permanent accounting masters and cannot be deleted."
        )

    # 2. Extract profile id
    profile_id = None
    if clean_id.startswith("profile_"):
        try:
            profile_id = int(clean_id.replace("profile_", ""))
        except ValueError:
            pass
    elif clean_id.isdigit():
        profile_id = int(clean_id)

    if not profile_id:
        raise HTTPException(status_code=400, detail="Invalid customer identifier.")

    # 3. Fetch profile
    res = await db.execute(
        select(CustomerProfile).where(
            CustomerProfile.id == profile_id,
            CustomerProfile.company_id == user.company_id
        )
    )
    profile = res.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail="Customer lead not found.")

    # 4. STRICT RULE: Cannot delete if customer has a ledger_id
    if profile.ledger_id is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete customer because they are mapped to Tally Ledger #{profile.ledger_id}. Only unmapped field leads can be deleted."
        )

    # 5. Permission Check: Admin or the salesperson who created it
    user_is_admin = is_user_admin(user)
    user_is_creator = (profile.created_by is not None and profile.created_by == user.user_id)
    if not (user_is_admin or user_is_creator):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this customer lead. Only an Admin or the creator can delete it."
        )

    # 6. Clean up photos from ImageKit
    photos_res = await db.execute(
        select(CustomerPhoto).where(CustomerPhoto.customer_profile_id == profile.id)
    )
    photos = photos_res.scalars().all()
    for ph in photos:
        if ph.imagekit_file_id:
            try:
                delete_imagekit_file(ph.imagekit_file_id)
            except Exception as e:
                print(f"[ImageKit] Error deleting photo file {ph.imagekit_file_id}: {e}")

    # 7. Delete profile (cascades to location_logs and photos in DB)
    customer_name = profile.custom_name or f"Lead #{profile.id}"
    await db.delete(profile)
    await db.commit()

    return {
        "success": True,
        "message": f"Wrongly tagged customer lead '{customer_name}' was deleted successfully."
    }


# ─── Multi-Owner Management Endpoints ────────────────────────────────────────

async def resolve_customer_profile_for_target(
    target_id: str,
    company_id: int,
    user_id: int,
    db: AsyncSession
) -> CustomerProfile:
    """Resolve CustomerProfile from target_id (or create one for Tally ledger if needed)."""
    clean_id = str(target_id).strip()
    profile = None

    if clean_id.startswith("tally_") or clean_id.startswith("ledger_"):
        lid = int(clean_id.replace("tally_", "").replace("ledger_", ""))
        p_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == company_id,
                CustomerProfile.ledger_id == lid
            )
        )
        profile = p_res.scalars().first()
        if not profile:
            l_res = await db.execute(
                select(MstLedger).where(
                    MstLedger.company_id == company_id,
                    MstLedger.ledger_id == lid
                )
            )
            ledger = l_res.scalars().first()
            if not ledger:
                raise HTTPException(status_code=404, detail="Tally ledger not found")
            profile = CustomerProfile(
                company_id=company_id,
                ledger_id=lid,
                contact_person=ledger.contact_person,
                phone=ledger.phone,
                whatsapp_number=ledger.mobile,
                email=ledger.email,
                created_by=user_id
            )
            db.add(profile)
            await db.flush()
    elif clean_id.startswith("profile_"):
        pid = int(clean_id.replace("profile_", ""))
        p_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == company_id,
                CustomerProfile.id == pid
            )
        )
        profile = p_res.scalars().first()
    elif clean_id.isdigit():
        val = int(clean_id)
        p_res = await db.execute(
            select(CustomerProfile).where(
                CustomerProfile.company_id == company_id,
                or_(CustomerProfile.id == val, CustomerProfile.ledger_id == val)
            )
        )
        profile = p_res.scalars().first()
        if not profile:
            l_res = await db.execute(
                select(MstLedger).where(
                    MstLedger.company_id == company_id,
                    MstLedger.ledger_id == val
                )
            )
            ledger = l_res.scalars().first()
            if ledger:
                profile = CustomerProfile(
                    company_id=company_id,
                    ledger_id=val,
                    contact_person=ledger.contact_person,
                    phone=ledger.phone,
                    whatsapp_number=ledger.mobile,
                    email=ledger.email,
                    created_by=user_id
                )
                db.add(profile)
                await db.flush()

    if not profile:
        raise HTTPException(status_code=404, detail="Customer profile not found.")
    return profile


@router.get("/{target_id}/owners")
async def get_customer_owners(
    target_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all registered owners/partners for a customer."""
    profile = await resolve_customer_profile_for_target(target_id, user.company_id, user.user_id, db)

    owners_stmt = (
        select(CustomerOwner)
        .where(
            CustomerOwner.company_id == user.company_id,
            CustomerOwner.customer_profile_id == profile.id
        )
        .order_by(desc(CustomerOwner.is_primary), CustomerOwner.id.asc())
    )
    owners_res = await db.execute(owners_stmt)
    owners = owners_res.scalars().all()

    return {
        "owners": [
            {
                "id": o.id,
                "name": o.name,
                "designation": o.designation or "Owner / Partner",
                "phone": o.phone or "",
                "whatsapp_number": o.whatsapp_number or "",
                "email": o.email or "",
                "photo_url": o.photo_url,
                "is_primary": o.is_primary,
                "notes": o.notes or "",
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in owners
        ]
    }


@router.post("/{target_id}/owners")
async def add_customer_owner(
    target_id: str,
    req: CustomerOwnerCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a new owner or business partner to a customer shop."""
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Owner name is required.")

    profile = await resolve_customer_profile_for_target(target_id, user.company_id, user.user_id, db)

    # Check existing owners count
    existing_cnt_res = await db.execute(
        select(func.count(CustomerOwner.id)).where(
            CustomerOwner.company_id == user.company_id,
            CustomerOwner.customer_profile_id == profile.id
        )
    )
    existing_count = existing_cnt_res.scalar() or 0

    is_primary = req.is_primary
    if existing_count == 0:
        is_primary = True

    if is_primary:
        # Demote existing owners
        await db.execute(
            update(CustomerOwner)
            .where(
                CustomerOwner.company_id == user.company_id,
                CustomerOwner.customer_profile_id == profile.id
            )
            .values(is_primary=False)
        )
        # Sync profile contact fields
        profile.contact_person = req.name.strip()
        if req.phone:
            profile.phone = req.phone.strip()
        if req.whatsapp_number:
            profile.whatsapp_number = req.whatsapp_number.strip()
        if req.photo_url:
            profile.customer_photo_url = req.photo_url

    new_owner = CustomerOwner(
        company_id=user.company_id,
        customer_profile_id=profile.id,
        name=req.name.strip(),
        designation=req.designation.strip() if req.designation else "Owner / Partner",
        phone=req.phone.strip() if req.phone else None,
        whatsapp_number=req.whatsapp_number.strip() if req.whatsapp_number else (req.phone.strip() if req.phone else None),
        email=req.email.strip() if req.email else None,
        photo_url=req.photo_url,
        is_primary=is_primary,
        notes=req.notes.strip() if req.notes else None
    )
    db.add(new_owner)
    profile.updated_at = func.now()
    await db.commit()
    await db.refresh(new_owner)

    return {
        "success": True,
        "message": f"Owner '{new_owner.name}' added successfully.",
        "owner": {
            "id": new_owner.id,
            "name": new_owner.name,
            "designation": new_owner.designation,
            "phone": new_owner.phone or "",
            "whatsapp_number": new_owner.whatsapp_number or "",
            "email": new_owner.email or "",
            "photo_url": new_owner.photo_url,
            "is_primary": new_owner.is_primary,
            "notes": new_owner.notes or "",
            "created_at": new_owner.created_at.isoformat() if new_owner.created_at else None,
        }
    }


@router.put("/{target_id}/owners/{owner_id}")
async def update_customer_owner(
    target_id: str,
    owner_id: int,
    req: CustomerOwnerUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update details of an existing owner/partner."""
    profile = await resolve_customer_profile_for_target(target_id, user.company_id, user.user_id, db)

    ow_res = await db.execute(
        select(CustomerOwner).where(
            CustomerOwner.id == owner_id,
            CustomerOwner.company_id == user.company_id,
            CustomerOwner.customer_profile_id == profile.id
        )
    )
    owner = ow_res.scalars().first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found.")

    if req.name is not None:
        owner.name = req.name.strip()
    if req.designation is not None:
        owner.designation = req.designation.strip()
    if req.phone is not None:
        owner.phone = req.phone.strip() if req.phone else None
    if req.whatsapp_number is not None:
        owner.whatsapp_number = req.whatsapp_number.strip() if req.whatsapp_number else None
    if req.email is not None:
        owner.email = req.email.strip() if req.email else None
    if req.photo_url is not None:
        owner.photo_url = req.photo_url
    if req.notes is not None:
        owner.notes = req.notes.strip() if req.notes else None

    if req.is_primary is True:
        # Demote others
        await db.execute(
            update(CustomerOwner)
            .where(
                CustomerOwner.company_id == user.company_id,
                CustomerOwner.customer_profile_id == profile.id,
                CustomerOwner.id != owner.id
            )
            .values(is_primary=False)
        )
        owner.is_primary = True
        # Sync profile contact fields
        profile.contact_person = owner.name
        if owner.phone:
            profile.phone = owner.phone
        if owner.whatsapp_number:
            profile.whatsapp_number = owner.whatsapp_number
        if owner.photo_url:
            profile.customer_photo_url = owner.photo_url

    profile.updated_at = func.now()
    await db.commit()
    await db.refresh(owner)

    return {
        "success": True,
        "message": f"Owner '{owner.name}' updated successfully.",
        "owner": {
            "id": owner.id,
            "name": owner.name,
            "designation": owner.designation,
            "phone": owner.phone or "",
            "whatsapp_number": owner.whatsapp_number or "",
            "email": owner.email or "",
            "photo_url": owner.photo_url,
            "is_primary": owner.is_primary,
            "notes": owner.notes or "",
            "created_at": owner.created_at.isoformat() if owner.created_at else None,
        }
    }


@router.delete("/{target_id}/owners/{owner_id}")
async def delete_customer_owner(
    target_id: str,
    owner_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete an owner/partner from a customer shop."""
    profile = await resolve_customer_profile_for_target(target_id, user.company_id, user.user_id, db)

    ow_res = await db.execute(
        select(CustomerOwner).where(
            CustomerOwner.id == owner_id,
            CustomerOwner.company_id == user.company_id,
            CustomerOwner.customer_profile_id == profile.id
        )
    )
    owner = ow_res.scalars().first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found.")

    was_primary = owner.is_primary
    owner_name = owner.name

    if owner.imagekit_file_id:
        try:
            delete_imagekit_file(owner.imagekit_file_id)
        except Exception:
            pass

    await db.delete(owner)
    await db.flush()

    # If the deleted owner was primary, promote next owner
    if was_primary:
        next_res = await db.execute(
            select(CustomerOwner)
            .where(
                CustomerOwner.company_id == user.company_id,
                CustomerOwner.customer_profile_id == profile.id
            )
            .order_by(CustomerOwner.id.asc())
        )
        next_owner = next_res.scalars().first()
        if next_owner:
            next_owner.is_primary = True
            profile.contact_person = next_owner.name
            profile.phone = next_owner.phone
            profile.whatsapp_number = next_owner.whatsapp_number
            profile.customer_photo_url = next_owner.photo_url
        else:
            profile.contact_person = None

    profile.updated_at = func.now()
    await db.commit()

    return {
        "success": True,
        "message": f"Owner '{owner_name}' deleted successfully."
    }


@router.post("/{target_id}/owners/{owner_id}/photo")
async def upload_owner_photo(
    target_id: str,
    owner_id: int,
    req: OwnerPhotoUploadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload photo for a specific owner/partner to ImageKit in the customer directory."""
    if not req.photo_base64 or len(req.photo_base64.strip()) < 20:
        raise HTTPException(status_code=400, detail="Invalid photo data.")

    profile = await resolve_customer_profile_for_target(target_id, user.company_id, user.user_id, db)

    ow_res = await db.execute(
        select(CustomerOwner).where(
            CustomerOwner.id == owner_id,
            CustomerOwner.company_id == user.company_id,
            CustomerOwner.customer_profile_id == profile.id
        )
    )
    owner = ow_res.scalars().first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found.")

    ledger_id = profile.ledger_id
    if ledger_id:
        folder = f"/customers/ledger_{ledger_id}/owners"
    else:
        folder = f"/customers/profile_{profile.id}/owners"

    ts = int(datetime.now().timestamp())
    file_name = f"owner_{owner.id}_{ts}.jpg"
    tags = ["customer", "owner_portrait", f"company_{user.company_id}"]
    if ledger_id:
        tags.append(f"ledger_{ledger_id}")

    # Delete old file if present
    if owner.imagekit_file_id:
        try:
            delete_imagekit_file(owner.imagekit_file_id)
        except Exception:
            pass

    ik_res = upload_customer_photo(
        file_base64=req.photo_base64,
        file_name=file_name,
        folder=folder,
        tags=tags
    )

    owner.photo_url = ik_res["url"]
    owner.imagekit_file_id = ik_res["file_id"]

    if owner.is_primary:
        profile.customer_photo_url = ik_res["url"]

    # Also add into CustomerPhoto gallery
    photo_entry = CustomerPhoto(
        company_id=user.company_id,
        customer_profile_id=profile.id,
        ledger_id=ledger_id,
        photo_type="customer_owner",
        imagekit_file_id=ik_res["file_id"],
        imagekit_url=ik_res["url"],
        imagekit_thumbnail_url=ik_res["thumbnail_url"],
        imagekit_file_path=ik_res["file_path"],
        caption=req.caption or f"Owner photo: {owner.name} ({owner.designation})",
        is_primary=owner.is_primary,
        uploaded_by=user.user_id,
    )
    db.add(photo_entry)

    profile.updated_at = func.now()
    await db.commit()
    await db.refresh(owner)

    return {
        "success": True,
        "message": f"Photo for {owner.name} uploaded successfully.",
        "photo_url": ik_res["url"],
        "thumbnail_url": ik_res["thumbnail_url"],
        "owner": {
            "id": owner.id,
            "name": owner.name,
            "photo_url": owner.photo_url
        }
    }

