"""
Daily Beat Planner Router
Provides daily route/beat assignment, planned vs actual tracking,
nearest-neighbor route optimization, and end-of-day summary scorecards.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_, and_, func, desc, cast, Date
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
import math

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.portal_core import (
    User, CustomerProfile, BeatPlan, BeatPlanStop, ShopPayment
)
from app.models.tally_core import MstLedger
from app.routers.visits import SalesVisit
from app.routers.orders import TempOrder, TempOrderItem

router = APIRouter(prefix="/planner", tags=["planner"])


# ─── Helper Functions ────────────────────────────────────────────────────────

def check_is_admin(user: User) -> bool:
    if not user:
        return False
    if getattr(user, "role_id", None) == 1:
        return True
    try:
        role_obj = user.__dict__.get("role")
        if role_obj and getattr(role_obj, "name", None):
            return role_obj.name.lower() in {"admin", "owner", "superadmin"}
    except Exception:
        pass
    return False


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates distance between two GPS points in meters."""
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def optimize_stop_sequence(stops: List[dict], start_lat: Optional[float] = None, start_lon: Optional[float] = None) -> List[dict]:
    """Nearest-neighbor TSP greedy sequence for ordering route stops."""
    if len(stops) <= 1:
        return stops

    with_gps = [s for s in stops if s.get("latitude") is not None and s.get("longitude") is not None]
    without_gps = [s for s in stops if s.get("latitude") is None or s.get("longitude") is None]

    if not with_gps:
        return stops

    ordered = []
    remaining = list(with_gps)

    curr_lat = start_lat if start_lat is not None else remaining[0]["latitude"]
    curr_lon = start_lon if start_lon is not None else remaining[0]["longitude"]

    while remaining:
        best_idx = 0
        best_dist = float("inf")
        for idx, s in enumerate(remaining):
            d = haversine_distance(curr_lat, curr_lon, s["latitude"], s["longitude"])
            if d < best_dist:
                best_dist = d
                best_idx = idx

        chosen = remaining.pop(best_idx)
        ordered.append(chosen)
        curr_lat = chosen["latitude"]
        curr_lon = chosen["longitude"]

    return ordered + without_gps


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class AssignBeatRequest(BaseModel):
    user_id: int
    plan_date: date
    route_name: str
    locality: Optional[str] = None
    notes: Optional[str] = None
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    customer_keys: Optional[List[str]] = None


class UpdateStopStatusRequest(BaseModel):
    status: str  # "visited", "skipped", "pending"
    skip_reason: Optional[str] = None
    notes: Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/routes")
async def get_available_routes_and_salespersons(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns available routes and localities with customer counts,
    and a list of active users/salespersons for assigning beats.
    """
    # 1. Fetch routes from customer profiles
    profiles_stmt = (
        select(CustomerProfile)
        .where(CustomerProfile.company_id == user.company_id)
    )
    profiles_res = await db.execute(profiles_stmt)
    profiles = profiles_res.scalars().all()

    routes_map = {}
    localities_set = set()

    for p in profiles:
        r = (p.route_name or "").strip()
        loc = (p.locality or "").strip()
        if loc:
            localities_set.add(loc)

        if r:
            if r not in routes_map:
                routes_map[r] = {
                    "route_name": r,
                    "customer_count": 0,
                    "gps_tagged_count": 0,
                    "localities": set()
                }
            routes_map[r]["customer_count"] += 1
            if p.latitude is not None and p.longitude is not None:
                routes_map[r]["gps_tagged_count"] += 1
            if loc:
                routes_map[r]["localities"].add(loc)

    routes_list = [
        {
            "route_name": v["route_name"],
            "customer_count": v["customer_count"],
            "gps_tagged_count": v["gps_tagged_count"],
            "localities": sorted(list(v["localities"]))
        }
        for v in routes_map.values()
    ]
    routes_list.sort(key=lambda x: x["route_name"])

    # 2. Fetch salespersons/users in the company
    users_stmt = (
        select(User)
        .options(selectinload(User.role))
        .where(User.company_id == user.company_id, User.is_active == True)
        .order_by(User.username.asc())
    )
    users_res = await db.execute(users_stmt)
    users_list = []
    for u in users_res.scalars().all():
        role_name = u.role.name if u.role else "User"
        users_list.append({
            "user_id": u.user_id,
            "username": u.username,
            "email": u.email,
            "role": role_name
        })

    return {
        "routes": routes_list,
        "localities": sorted(list(localities_set)),
        "salespersons": users_list
    }


@router.get("/daily")
async def get_daily_beat_plans(
    plan_date: Optional[date] = Query(None, description="Plan date (defaults to today)"),
    user_id: Optional[int] = Query(None, description="Salesperson user_id filter (Admin only)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get beat plans for a specific date:
    - If Salesperson: Returns their assigned beat plan for that date.
    - If Admin: Returns all beat plans for that date (or filtered by user_id).
    """
    target_date = plan_date if isinstance(plan_date, date) else datetime.now().date()
    is_admin = check_is_admin(user)
    filter_user_id = user_id if isinstance(user_id, int) else None

    query = (
        select(BeatPlan)
        .options(
            selectinload(BeatPlan.user),
            selectinload(BeatPlan.creator),
            selectinload(BeatPlan.stops)
        )
        .where(
            BeatPlan.company_id == user.company_id,
            BeatPlan.plan_date == target_date
        )
    )

    if not is_admin:
        query = query.where(BeatPlan.user_id == user.user_id)
    elif filter_user_id:
        query = query.where(BeatPlan.user_id == filter_user_id)

    query = query.order_by(desc(BeatPlan.created_at))
    res = await db.execute(query)
    plans = res.scalars().all()

    result = []
    for plan in plans:
        stops_data = []
        visited_count = 0
        skipped_count = 0
        pending_count = 0

        for stop in plan.stops:
            if stop.status == "visited":
                visited_count += 1
            elif stop.status == "skipped":
                skipped_count += 1
            else:
                pending_count += 1

            stops_data.append({
                "id": stop.id,
                "customer_key": stop.customer_key,
                "customer_profile_id": stop.customer_profile_id,
                "ledger_id": stop.ledger_id,
                "shop_name": stop.shop_name,
                "locality": stop.locality,
                "address": stop.address,
                "latitude": stop.latitude,
                "longitude": stop.longitude,
                "sequence_order": stop.sequence_order,
                "status": stop.status,
                "visit_id": stop.visit_id,
                "visited_at": stop.visited_at.isoformat() if stop.visited_at else None,
                "skip_reason": stop.skip_reason,
                "notes": stop.notes,
            })

        total_stops = len(stops_data)
        completion_rate = round((visited_count / total_stops * 100), 1) if total_stops > 0 else 0.0

        result.append({
            "id": plan.id,
            "user_id": plan.user_id,
            "salesperson_name": plan.user.username if plan.user else "Salesperson",
            "plan_date": plan.plan_date.isoformat(),
            "route_name": plan.route_name,
            "locality": plan.locality,
            "notes": plan.notes,
            "status": plan.status,
            "created_by": plan.creator.username if plan.creator else None,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "total_stops": total_stops,
            "visited_stops": visited_count,
            "skipped_stops": skipped_count,
            "pending_stops": pending_count,
            "completion_rate": completion_rate,
            "stops": stops_data,
        })

    return {
        "date": target_date.isoformat(),
        "total_plans": len(result),
        "plans": result
    }


@router.post("/assign")
async def assign_beat_plan(
    payload: AssignBeatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Admin endpoint to assign a route/beat to a salesperson for a specific date.
    Automatically sequences GPS-tagged stops using nearest-neighbor TSP.
    """
    if not check_is_admin(user):
        raise HTTPException(status_code=403, detail="Only Admins can assign daily beat plans")

    # Verify target salesperson exists in company
    salesperson_res = await db.execute(
        select(User).where(User.company_id == user.company_id, User.user_id == payload.user_id)
    )
    salesperson = salesperson_res.scalars().first()
    if not salesperson:
        raise HTTPException(status_code=404, detail="Salesperson not found in company")

    # Query customer profiles matching route / locality or specific keys
    prof_query = select(CustomerProfile).where(CustomerProfile.company_id == user.company_id)

    if payload.customer_keys and len(payload.customer_keys) > 0:
        # Match keys like 'profile_X' or 'tally_Y'
        profile_ids = []
        ledger_ids = []
        for k in payload.customer_keys:
            if k.startswith("profile_"):
                profile_ids.append(int(k.replace("profile_", "")))
            elif k.startswith("tally_") or k.startswith("ledger_"):
                ledger_ids.append(int(k.replace("tally_", "").replace("ledger_", "")))

        conds = []
        if profile_ids:
            conds.append(CustomerProfile.id.in_(profile_ids))
        if ledger_ids:
            conds.append(CustomerProfile.ledger_id.in_(ledger_ids))
        if conds:
            prof_query = prof_query.where(or_(*conds))
    else:
        filters = []
        if payload.route_name and payload.route_name != "all":
            filters.append(CustomerProfile.route_name == payload.route_name)
        if payload.locality and payload.locality != "all":
            filters.append(CustomerProfile.locality == payload.locality)
        if filters:
            prof_query = prof_query.where(and_(*filters))

    prof_res = await db.execute(prof_query)
    matched_profiles = prof_res.scalars().all()

    # Also check if matching tally ledgers exist without customer_profile
    candidate_stops = []
    seen_keys = set()

    for p in matched_profiles:
        key = f"tally_{p.ledger_id}" if p.ledger_id else f"profile_{p.id}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        # Name fallback
        shop_name = p.custom_name
        if not shop_name and p.ledger_id:
            l_res = await db.execute(select(MstLedger.name).where(MstLedger.ledger_id == p.ledger_id))
            shop_name = l_res.scalar() or "Shop"

        candidate_stops.append({
            "customer_key": key,
            "customer_profile_id": p.id,
            "ledger_id": p.ledger_id,
            "shop_name": shop_name or "Shop",
            "locality": p.locality,
            "address": p.address,
            "latitude": p.latitude,
            "longitude": p.longitude,
        })

    if not candidate_stops:
        raise HTTPException(
            status_code=400,
            detail=f"No customers found for route '{payload.route_name}'" + (f" and locality '{payload.locality}'" if payload.locality else "")
        )

    # Sequence stops via TSP Nearest Neighbor
    ordered_stops = optimize_stop_sequence(
        candidate_stops,
        start_lat=payload.start_latitude,
        start_lon=payload.start_longitude
    )

    # Check if a beat plan already exists for this salesperson on this date
    existing_stmt = (
        select(BeatPlan)
        .where(
            BeatPlan.company_id == user.company_id,
            BeatPlan.user_id == payload.user_id,
            BeatPlan.plan_date == payload.plan_date
        )
    )
    existing_res = await db.execute(existing_stmt)
    existing_plan = existing_res.scalars().first()

    if existing_plan:
        # Delete old stops and update header
        await db.execute(
            BeatPlanStop.__table__.delete().where(BeatPlanStop.beat_plan_id == existing_plan.id)
        )
        existing_plan.route_name = payload.route_name
        existing_plan.locality = payload.locality
        existing_plan.notes = payload.notes
        existing_plan.status = "assigned"
        existing_plan.created_by = user.user_id
        beat_plan = existing_plan
    else:
        beat_plan = BeatPlan(
            company_id=user.company_id,
            user_id=payload.user_id,
            plan_date=payload.plan_date,
            route_name=payload.route_name,
            locality=payload.locality,
            notes=payload.notes,
            status="assigned",
            created_by=user.user_id,
        )
        db.add(beat_plan)
        await db.flush()

    # Add sequenced stops
    for idx, stop_info in enumerate(ordered_stops, start=1):
        stop_record = BeatPlanStop(
            beat_plan_id=beat_plan.id,
            customer_key=stop_info["customer_key"],
            customer_profile_id=stop_info.get("customer_profile_id"),
            ledger_id=stop_info.get("ledger_id"),
            shop_name=stop_info["shop_name"],
            locality=stop_info.get("locality"),
            address=stop_info.get("address"),
            latitude=stop_info.get("latitude"),
            longitude=stop_info.get("longitude"),
            sequence_order=idx,
            status="pending"
        )
        db.add(stop_record)

    await db.commit()

    return {
        "message": f"Beat plan assigned successfully to {salesperson.username} with {len(ordered_stops)} stops",
        "beat_plan_id": beat_plan.id,
        "plan_date": payload.plan_date.isoformat(),
        "total_stops": len(ordered_stops)
    }


@router.patch("/stops/{stop_id}/status")
async def update_beat_stop_status(
    stop_id: int,
    payload: UpdateStopStatusRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a stop status (e.g., mark 'skipped' with reason, or manually 'visited').
    """
    stmt = (
        select(BeatPlanStop, BeatPlan)
        .join(BeatPlan, BeatPlan.id == BeatPlanStop.beat_plan_id)
        .where(
            BeatPlanStop.id == stop_id,
            BeatPlan.company_id == user.company_id
        )
    )
    res = await db.execute(stmt)
    row = res.first()

    if not row:
        raise HTTPException(status_code=404, detail="Beat stop not found")

    stop, plan = row
    if plan.user_id != user.user_id and not check_is_admin(user):
        raise HTTPException(status_code=403, detail="You can only update stops on your own beat plans.")

    stop.status = payload.status
    if payload.status == "skipped":
        stop.skip_reason = payload.skip_reason or "Skipped by salesperson"
    elif payload.status == "visited" and not stop.visited_at:
        stop.visited_at = datetime.now()

    if payload.notes:
        stop.notes = payload.notes

    await db.commit()
    return {"message": "Stop status updated", "id": stop.id, "status": stop.status}


@router.get("/summary")
async def get_end_of_day_summary(
    date_val: Optional[date] = Query(None, alias="date", description="Report date (defaults to today)"),
    user_id: Optional[int] = Query(None, description="Salesperson user_id (Admin can specify; defaults to current user)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    End-of-day summary report:
    - Beat plan execution: planned vs visited vs skipped
    - Check-in visits timeline
    - Orders taken (count, items, total ₹)
    - Payments collected (count, payment modes, total ₹)
    """
    target_date = date_val if isinstance(date_val, date) else datetime.now().date()
    is_admin = check_is_admin(user)
    target_user_id = user_id if (is_admin and isinstance(user_id, int)) else user.user_id

    # Fetch Salesperson info
    sp_res = await db.execute(select(User).options(selectinload(User.role)).where(User.user_id == target_user_id))
    salesperson = sp_res.scalars().first()

    # 1. Beat Plan Metrics
    plan_stmt = (
        select(BeatPlan)
        .options(selectinload(BeatPlan.stops))
        .where(
            BeatPlan.company_id == user.company_id,
            BeatPlan.user_id == target_user_id,
            BeatPlan.plan_date == target_date
        )
    )
    plan_res = await db.execute(plan_stmt)
    plan = plan_res.scalars().first()

    beat_summary = {
        "has_plan": plan is not None,
        "route_name": plan.route_name if plan else "Unassigned",
        "locality": plan.locality if plan else None,
        "total_planned": len(plan.stops) if plan else 0,
        "visited_count": len([s for s in plan.stops if s.status == "visited"]) if plan else 0,
        "skipped_count": len([s for s in plan.stops if s.status == "skipped"]) if plan else 0,
        "pending_count": len([s for s in plan.stops if s.status == "pending"]) if plan else 0,
        "completion_rate": round(len([s for s in plan.stops if s.status == "visited"]) / len(plan.stops) * 100, 1) if (plan and len(plan.stops) > 0) else 0.0,
        "stops": [
            {
                "id": s.id,
                "shop_name": s.shop_name,
                "locality": s.locality,
                "sequence_order": s.sequence_order,
                "status": s.status,
                "visited_at": s.visited_at.isoformat() if s.visited_at else None,
                "skip_reason": s.skip_reason
            }
            for s in (plan.stops if plan else [])
        ]
    }

    # 2. Sales Visits check-ins today
    visit_stmt = (
        select(SalesVisit)
        .where(
            SalesVisit.user_id == target_user_id,
            cast(SalesVisit.created_at, Date) == target_date
        )
        .order_by(SalesVisit.created_at.asc())
    )
    visit_res = await db.execute(visit_stmt)
    visits = visit_res.scalars().all()

    visits_list = []
    for v in visits:
        shop_name = v.custom_shop_name
        if not shop_name and v.ledger_id:
            l_res = await db.execute(select(MstLedger.name).where(MstLedger.ledger_id == v.ledger_id))
            shop_name = l_res.scalar() or "Shop"

        visits_list.append({
            "id": v.id,
            "shop_name": shop_name or "Shop",
            "comments": v.comments,
            "latitude": v.latitude,
            "longitude": v.longitude,
            "photo_url": v.photo_url,
            "status": v.status,
            "time": v.created_at.strftime("%I:%M %p") if v.created_at else None,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        })

    # 3. Temp Orders taken today
    order_stmt = (
        select(TempOrder)
        .options(selectinload(TempOrder.items))
        .where(
            TempOrder.user_id == target_user_id,
            cast(TempOrder.created_at, Date) == target_date
        )
        .order_by(TempOrder.created_at.asc())
    )
    order_res = await db.execute(order_stmt)
    orders = order_res.scalars().all()

    total_order_amount = 0.0
    total_order_items = 0
    orders_list = []

    for o in orders:
        o_items_count = sum(it.quantity or 0 for it in o.items) if o.items else 0
        o_amount = sum(float(it.quantity or 0) * float(it.price or 0) for it in o.items) if o.items else 0.0
        total_order_amount += o_amount
        total_order_items += o_items_count

        cust_name = o.custom_customer_name
        if not cust_name and o.ledger_id:
            l_res = await db.execute(select(MstLedger.name).where(MstLedger.ledger_id == o.ledger_id))
            cust_name = l_res.scalar() or "Customer"

        orders_list.append({
            "id": o.id,
            "customer_name": cust_name or "Customer",
            "status": o.status,
            "items_count": o_items_count,
            "total_amount": round(o_amount, 2),
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "time": o.created_at.strftime("%I:%M %p") if o.created_at else None,
        })

    # 4. Payments collected today
    pay_stmt = (
        select(ShopPayment)
        .where(
            ShopPayment.user_id == target_user_id,
            cast(ShopPayment.created_at, Date) == target_date
        )
        .order_by(ShopPayment.created_at.asc())
    )
    pay_res = await db.execute(pay_stmt)
    payments = pay_res.scalars().all()

    total_collected = 0.0
    modes_breakdown = {}
    payments_list = []

    for p in payments:
        amt = float(p.amount or 0)
        total_collected += amt
        mode = p.payment_mode or "Cash"
        modes_breakdown[mode] = modes_breakdown.get(mode, 0.0) + amt

        l_res = await db.execute(select(MstLedger.name).where(MstLedger.ledger_id == p.ledger_id))
        cust_name = l_res.scalar() or "Shop"

        payments_list.append({
            "id": p.id,
            "customer_name": cust_name,
            "amount": round(amt, 2),
            "payment_mode": p.payment_mode,
            "cheque_date": p.cheque_date.isoformat() if p.cheque_date else None,
            "status": p.status,
            "comments": p.comments,
            "time": p.created_at.strftime("%I:%M %p") if p.created_at else None,
        })

    return {
        "date": target_date.isoformat(),
        "salesperson": {
            "user_id": salesperson.user_id if salesperson else target_user_id,
            "username": salesperson.username if salesperson else "User",
            "role": salesperson.role.name if (salesperson and salesperson.role) else "Salesperson"
        },
        "beat": beat_summary,
        "visits": {
            "count": len(visits_list),
            "items": visits_list
        },
        "orders": {
            "count": len(orders_list),
            "total_items": total_order_items,
            "total_amount": round(total_order_amount, 2),
            "items": orders_list
        },
        "payments": {
            "count": len(payments_list),
            "total_amount": round(total_collected, 2),
            "by_mode": {k: round(v, 2) for k, v in modes_breakdown.items()},
            "items": payments_list
        }
    }
