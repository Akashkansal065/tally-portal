"""
Customer Health Score & Visit Intelligence Service
Computes composite account health (0-100) and visit recency categorization.
Guaranteed zero accounting alteration.
"""
from datetime import datetime, date
from typing import Optional, Dict, Any


def calculate_visit_recency(last_visit_at: Optional[datetime], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Calculate days since last visit and categorization badge."""
    if not now:
        now = datetime.now()

    if not last_visit_at:
        return {
            "days": None,
            "category": "never",
            "label": "Never Visited",
            "color": "rose",
        }

    days = max(0, (now - last_visit_at).days)
    if days == 0:
        return {
            "days": 0,
            "category": "today",
            "label": "Visited Today",
            "color": "emerald",
        }
    elif days <= 7:
        return {
            "days": days,
            "category": "recent",
            "label": f"{days}d ago",
            "color": "emerald",
        }
    elif days <= 14:
        return {
            "days": days,
            "category": "due_soon",
            "label": f"{days}d ago",
            "color": "amber",
        }
    elif days <= 30:
        return {
            "days": days,
            "category": "overdue",
            "label": f"{days}d ago",
            "color": "orange",
        }
    else:
        return {
            "days": days,
            "category": "critical",
            "label": f"{days}d ago",
            "color": "rose",
        }


def calculate_customer_health(
    last_visit_at: Optional[datetime],
    visit_frequency: Optional[str],
    last_voucher_date: Optional[date],
    voucher_count: int = 0,
    has_verified_location: bool = False,
    has_contact: bool = False,
    has_photos: bool = False,
    now: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Compute 100-point composite customer health score:
    1. Visit Cadence & Adherence: 25 pts
    2. Order & Sales Recency: 35 pts
    3. Transaction Depth & Volume: 25 pts
    4. Profile & Verification Completeness: 15 pts
    """
    if not now:
        now = datetime.now()
    today_date = now.date()

    # 1. Visit Cadence Score (Max 25 pts)
    freq = (visit_frequency or "weekly").lower()
    target_days = 7 if "week" in freq else (14 if "bi" in freq else 30)

    visit_score = 0
    visit_label = "Never Visited"
    if last_visit_at:
        days_since_visit = max(0, (now - last_visit_at).days)
        if days_since_visit <= target_days:
            visit_score = 25
            visit_label = f"On Schedule ({days_since_visit}d ago)"
        elif days_since_visit <= target_days * 2:
            visit_score = 16
            visit_label = f"Slightly Overdue ({days_since_visit}d ago)"
        elif days_since_visit <= 45:
            visit_score = 8
            visit_label = f"Overdue ({days_since_visit}d ago)"
        else:
            visit_score = 0
            visit_label = f"Neglected ({days_since_visit}d ago)"

    # 2. Order & Sales Recency (Max 35 pts)
    order_score = 0
    order_label = "No Orders"
    if last_voucher_date:
        days_since_voucher = max(0, (today_date - last_voucher_date).days)
        if days_since_voucher <= 15:
            order_score = 35
            order_label = f"Active ({days_since_voucher}d ago)"
        elif days_since_voucher <= 30:
            order_score = 27
            order_label = f"Recent ({days_since_voucher}d ago)"
        elif days_since_voucher <= 60:
            order_score = 18
            order_label = f"Moderate ({days_since_voucher}d ago)"
        elif days_since_voucher <= 90:
            order_score = 9
            order_label = f"Dormant ({days_since_voucher}d ago)"
        else:
            order_score = 0
            order_label = f"Inactive (>90d ago)"

    # 3. Transaction Depth / Volume (Max 25 pts)
    volume_score = 0
    volume_label = "New / Prospect"
    if voucher_count >= 20:
        volume_score = 25
        volume_label = f"High Velocity ({voucher_count}+ txns)"
    elif voucher_count >= 8:
        volume_score = 18
        volume_label = f"Steady Volume ({voucher_count} txns)"
    elif voucher_count >= 2:
        volume_score = 10
        volume_label = f"Occasional ({voucher_count} txns)"
    elif voucher_count >= 1:
        volume_score = 5
        volume_label = "1 Transaction"

    # 4. Profile & Verification Completeness (Max 15 pts)
    profile_score = 0
    if has_verified_location:
        profile_score += 6
    if has_contact:
        profile_score += 5
    if has_photos:
        profile_score += 4

    total_score = min(100, max(0, visit_score + order_score + volume_score + profile_score))

    if total_score >= 80:
        grade = "HEALTHY"
        status_label = "Healthy Account"
        color = "emerald"
    elif total_score >= 50:
        grade = "FAIR"
        status_label = "Fair Standing"
        color = "amber"
    else:
        grade = "AT_RISK"
        status_label = "At Risk / Inactive"
        color = "rose"

    return {
        "score": total_score,
        "grade": grade,
        "status_label": status_label,
        "color": color,
        "breakdown": {
            "visit_score": visit_score,
            "visit_label": visit_label,
            "order_score": order_score,
            "order_label": order_label,
            "volume_score": volume_score,
            "volume_label": volume_label,
            "profile_score": profile_score,
            "total": total_score
        }
    }
