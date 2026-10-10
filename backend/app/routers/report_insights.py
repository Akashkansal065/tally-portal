"""Goal-tracking reports: monthly sales target, customers buying less, items about to run out, and the business
settings they use. Kept apart from reports.py and written with portable SQL so they're covered by tests."""
import calendar
import math
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import clear_all_cache
from app.core.database import get_db
from app.core.datetime_utils import get_ist_date
from app.core.permissions import accessible_company_ids, require_permission
from app.models.portal_core import Company, CustomerProfile, Role, User
from app.models.tally_core import (
    MstLedger, MstStockGroup, MstStockItem, MstUom, MstVoucherType, TrnAccounting, TrnInventory, TrnVoucher,
)
from app.routers.admin import require_admin
from app.services import app_settings
from app.services.receivables import group_ids_under, live_voucher, receivables_ageing, sales_voucher_type

router = APIRouter(prefix="/reports", tags=["Reports"])


# ─── Settings ────────────────────────────────────────────────────────────────

class ReportSettingsUpdate(BaseModel):
    monthly_sales_target: Optional[float] = None
    default_credit_days: Optional[int] = None


@router.get("/settings")
async def get_report_settings(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Monthly sales target and default credit days."""
    return await app_settings.get_settings(db, user.account_id)


@router.put("/settings")
async def update_report_settings(
    req: ReportSettingsUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Change the monthly sales target and/or default credit days. Admin only."""
    try:
        for key, value in req.model_dump(exclude_none=True).items():
            await app_settings.set_setting(db, key, value, user.user_id, user.account_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.commit()
    # Default credit days change every company's ageing
    clear_all_cache()
    return await app_settings.get_settings(db, user.account_id)


# ─── Monthly sales target ────────────────────────────────────────────────────

async def _companies_for(db: AsyncSession, user: User) -> Dict[int, str]:
    role_name = (await db.execute(select(Role.name).where(Role.role_id == user.role_id))).scalar()
    ids = await accessible_company_ids(db, user.user_id, user.company_id, role_name)
    rows = await db.execute(select(Company.company_id, Company.name).where(Company.company_id.in_(ids)))
    return dict(rows.all())


async def net_sales_by_day(db: AsyncSession, company_ids: List[int], start: date, end: date) -> Dict[int, Dict[date, float]]:
    """Net sales before GST: credits minus debits on ledgers under Sales Accounts (any depth), so credit notes
    reduce it. Returns {company_id: {day: amount}}."""
    sales_groups = set()
    for cid in company_ids:
        sales_groups |= await group_ids_under(db, cid, "Sales Accounts")
    if not sales_groups:
        return {}
    rows = await db.execute(
        select(TrnVoucher.company_id, TrnVoucher.voucher_date,
               func.sum(TrnAccounting.credit_amount - TrnAccounting.debit_amount))
        .join(TrnAccounting, TrnAccounting.voucher_id == TrnVoucher.voucher_id)
        .join(MstLedger, MstLedger.ledger_id == TrnAccounting.ledger_id)
        .where(TrnVoucher.company_id.in_(company_ids), MstLedger.group_id.in_(sales_groups), live_voucher(),
               TrnVoucher.voucher_date >= start, TrnVoucher.voucher_date <= end)
        .group_by(TrnVoucher.company_id, TrnVoucher.voucher_date)
    )
    result: Dict[int, Dict[date, float]] = defaultdict(dict)
    for cid, day, amount in rows.all():
        result[cid][day] = float(amount or 0)
    return result


@router.get("/sales-target")
async def sales_target_progress(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM; this month if omitted"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Net sales before GST across all the user's companies against the monthly target, with what's needed per
    remaining day and where the month will end at the current pace. Every day of the week counts."""
    today = get_ist_date()
    year, mon = (int(month[:4]), int(month[5:])) if month else (today.year, today.month)
    if not 1 <= mon <= 12:
        raise HTTPException(status_code=400, detail="Invalid month")
    days_in_month = calendar.monthrange(year, mon)[1]
    start, end = date(year, mon, 1), date(year, mon, days_in_month)
    if today < start:
        days_elapsed = 0
    elif today > end:
        days_elapsed = days_in_month
    else:
        days_elapsed = today.day
    days_left = days_in_month - days_elapsed + (1 if start <= today <= end else 0)  # today still counts

    target = float(await app_settings.get_setting(db, "monthly_sales_target", user.account_id))
    companies = await _companies_for(db, user)
    by_company = await net_sales_by_day(db, list(companies), start, min(end, today))

    daily_totals: Dict[date, float] = defaultdict(float)
    for days in by_company.values():
        for day, amount in days.items():
            daily_totals[day] += amount
    sales = round(sum(daily_totals.values()), 2)

    daily, running = [], 0.0
    for n in range(days_elapsed):
        day = start + timedelta(days=n)
        running += daily_totals.get(day, 0.0)
        daily.append({
            "date": day.isoformat(),
            "sales": round(daily_totals.get(day, 0.0), 2),
            "cumulative": round(running, 2),
            "target_cumulative": round(target * (n + 1) / days_in_month, 2),
        })

    projected = round(sales / days_elapsed * days_in_month, 2) if days_elapsed else 0.0
    remaining = max(0.0, target - sales)
    return {
        "month": f"{year:04d}-{mon:02d}",
        "as_of": today.isoformat(),
        "target": target,
        "sales": sales,
        "achieved_pct": round(sales / target * 100, 1) if target else None,
        "remaining": round(remaining, 2),
        "days_in_month": days_in_month,
        "days_elapsed": days_elapsed,
        "days_left": days_left,
        "needed_per_day": round(remaining / days_left, 2) if days_left and remaining else 0.0,
        "projected": projected,
        "on_track": projected >= target if days_elapsed else None,
        "daily": daily,
        "companies": sorted(
            ({"company_id": cid, "name": name, "sales": round(sum(by_company.get(cid, {}).values()), 2)}
             for cid, name in companies.items()),
            key=lambda c: c["sales"], reverse=True,
        ),
    }


# ─── Customers buying less ───────────────────────────────────────────────────

@router.get("/customer-watchlist")
async def customer_watchlist(
    drop_pct: float = Query(50, ge=1, le=100, description="Flag when sales fell by more than this % vs the previous window"),
    gap_multiplier: float = Query(2, ge=1, le=10, description="Flag when the wait since the last invoice is this many times their usual gap"),
    window_days: int = Query(90, ge=7, le=365, description="Length of the recent and previous windows compared"),
    min_gap_days: int = Query(30, ge=1, le=365, description="Never flag a wait shorter than this"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Customers of the current company who are buying less than before (sales dropped) or later than usual
    (longer since their last invoice than their usual gap), with what they owe. Largest loss first."""
    today = get_ist_date()
    debtor_groups = await group_ids_under(db, user.company_id, "Sundry Debtors")
    if not debtor_groups:
        return {"as_of": today.isoformat(), "customers": [], "checked": 0}

    # Every sales invoice per customer: the amount billed to them (incl. GST) and its date
    rows = await db.execute(
        select(MstLedger.ledger_id, TrnVoucher.voucher_date, func.sum(TrnAccounting.debit_amount - TrnAccounting.credit_amount))
        .join(TrnAccounting, TrnAccounting.ledger_id == MstLedger.ledger_id)
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .where(MstLedger.company_id == user.company_id, MstLedger.group_id.in_(debtor_groups),
               sales_voucher_type(), live_voucher())
        .group_by(MstLedger.ledger_id, TrnVoucher.voucher_id, TrnVoucher.voucher_date)
    )
    invoices: Dict[int, List[tuple]] = defaultdict(list)
    for ledger_id, day, amount in rows.all():
        invoices[ledger_id].append((day, float(amount or 0)))

    recent_from = today - timedelta(days=window_days)
    previous_from = today - timedelta(days=window_days * 2)
    flagged = []
    for ledger_id, items in invoices.items():
        recent = sum(a for d, a in items if d > recent_from)
        previous = sum(a for d, a in items if previous_from < d <= recent_from)
        days = sorted({d for d, _ in items})
        gaps = [(b - a).days for a, b in zip(days, days[1:])]
        usual_gap = statistics.median(gaps) if len(gaps) >= 2 else None
        since_last = (today - days[-1]).days
        # Too few invoices to know their rhythm: compare against the window instead
        allowed_wait = max(min_gap_days, usual_gap * gap_multiplier) if usual_gap else max(min_gap_days, window_days)

        reasons = []
        if previous > 0 and recent < previous * (1 - drop_pct / 100):
            reasons.append("dropped")
        if since_last > allowed_wait:
            reasons.append("late")
        if not reasons:
            continue
        flagged.append({
            "ledger_id": ledger_id,
            "recent_sales": round(recent, 2),
            "previous_sales": round(previous, 2),
            "change_pct": round((recent - previous) / previous * 100, 1) if previous else None,
            "last_invoice": days[-1].isoformat(),
            "days_since_last": since_last,
            "usual_gap_days": round(usual_gap, 1) if usual_gap is not None else None,
            "invoices": len(days),
            "reasons": reasons,
            "lost": round(max(0.0, previous - recent), 2),
        })

    if flagged:
        ids = [f["ledger_id"] for f in flagged]
        ledgers = {r.ledger_id: r for r in (await db.execute(
            select(MstLedger.ledger_id, MstLedger.name, MstLedger.mobile, MstLedger.phone, MstLedger.pincode)
            .where(MstLedger.ledger_id.in_(ids)))).all()}
        cities = dict((await db.execute(
            select(CustomerProfile.ledger_id, CustomerProfile.city)
            .where(CustomerProfile.company_id == user.company_id, CustomerProfile.ledger_id.in_(ids)))).all())
        owed = {p.ledger_id: p for p in await receivables_ageing(db, user.company_id, today=today)}
        for f in flagged:
            led = ledgers[f["ledger_id"]]
            f.update(
                name=led.name,
                phone=led.mobile or led.phone,
                city=(cities.get(f["ledger_id"]) or "").strip() or None,
                pincode=led.pincode,
                outstanding=owed[f["ledger_id"]].balance if f["ledger_id"] in owed else 0.0,
                overdue=round(owed[f["ledger_id"]].overdue, 2) if f["ledger_id"] in owed else 0.0,
            )
    flagged.sort(key=lambda f: (f["lost"], f["days_since_last"]), reverse=True)
    return {
        "as_of": today.isoformat(),
        "checked": len(invoices),
        "criteria": {"drop_pct": drop_pct, "gap_multiplier": gap_multiplier,
                     "window_days": window_days, "min_gap_days": min_gap_days},
        "customers": flagged,
    }


# ─── Items about to run out ──────────────────────────────────────────────────

@router.get("/reorder-alerts")
async def reorder_alerts(
    cover_days: int = Query(14, ge=1, le=365, description="Alert when stock lasts fewer days than this"),
    lookback_days: int = Query(30, ge=7, le=365, description="Days of sales used for the daily average"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Items that are selling and will run out within cover_days at their recent daily sales rate (or already
    have), with a suggested quantity to order for 30 days of sales. Soonest first."""
    today = get_ist_date()
    since = today - timedelta(days=lookback_days)
    sold_rows = await db.execute(
        select(TrnInventory.stock_item_id, func.sum(TrnInventory.quantity))
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnInventory.voucher_id)
        .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .where(TrnVoucher.company_id == user.company_id, sales_voucher_type(), live_voucher(),
               TrnInventory.is_inward == False, TrnVoucher.voucher_date > since)  # noqa: E712
        .group_by(TrnInventory.stock_item_id)
    )
    sold = {item_id: float(qty or 0) for item_id, qty in sold_rows.all() if qty and float(qty) > 0}
    if not sold:
        return {"as_of": today.isoformat(), "criteria": {"cover_days": cover_days, "lookback_days": lookback_days}, "items": []}

    items = []
    rows = await db.execute(
        select(MstStockItem.stock_item_id, MstStockItem.name, MstStockItem.closing_qty, MstStockItem.closing_value,
               MstStockGroup.name.label("group_name"), MstUom.symbol)
        .outerjoin(MstStockGroup, MstStockGroup.stock_group_id == MstStockItem.stock_group_id)
        .outerjoin(MstUom, MstUom.unit_id == MstStockItem.unit_id)
        .where(MstStockItem.company_id == user.company_id, MstStockItem.stock_item_id.in_(list(sold)))
    )
    for r in rows.all():
        per_day = sold[r.stock_item_id] / lookback_days
        stock = float(r.closing_qty or 0)
        days_left = max(0.0, stock / per_day)
        if days_left >= cover_days:
            continue
        items.append({
            "stock_item_id": r.stock_item_id,
            "name": r.name,
            "group": r.group_name,
            "unit": r.symbol or "PCS",
            "stock": round(stock, 3),
            "sold_recently": round(sold[r.stock_item_id], 3),
            "per_day": round(per_day, 3),
            "days_left": round(days_left, 1),
            "out_of_stock": stock <= 0,
            "suggested_order": max(0, math.ceil(per_day * 30 - max(stock, 0))),
        })
    items.sort(key=lambda i: (i["days_left"], -i["per_day"]))
    return {"as_of": today.isoformat(), "criteria": {"cover_days": cover_days, "lookback_days": lookback_days}, "items": items}


# ─── Cities and territory ────────────────────────────────────────────────────

def _month_bounds(month: Optional[str], today: date):
    year, mon = (int(month[:4]), int(month[5:])) if month else (today.year, today.month)
    if not 1 <= mon <= 12:
        raise HTTPException(status_code=400, detail="Invalid month")
    start = date(year, mon, 1)
    end = date(year, mon, calendar.monthrange(year, mon)[1])
    return start, end


@router.get("/cities")
async def city_performance(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$", description="YYYY-MM; this month if omitted"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Sales, customers and money owed per city across the user's companies. This month (to date) is compared
    with the same days of last month. Leads are directory customers not yet in Tally."""
    from app.services.cities import NOT_SET, cities_for_ledgers, clean_pincode, normalise_city, pincode_cities
    from app.services.sales import net_sales_by_customer

    today = get_ist_date()
    start, end = _month_bounds(month, today)
    end = min(end, today) if start <= today else end
    prev_end_full = start - timedelta(days=1)
    prev_start = prev_end_full.replace(day=1)
    # Same number of days into last month, for a fair comparison
    prev_end = min(prev_start + timedelta(days=(end - start).days), prev_end_full)

    by_pin = await pincode_cities(db)
    cities: Dict[str, dict] = defaultdict(lambda: {
        "customers": 0, "leads": 0, "buying": 0, "sales": 0.0, "sales_previous": 0.0,
        "invoices": 0, "outstanding": 0.0, "overdue": 0.0,
    })
    cash_sales = 0.0
    for cid in (await _companies_for(db, user)):
        debtor_groups = await group_ids_under(db, cid, "Sundry Debtors")
        ledgers = (await db.execute(select(MstLedger.ledger_id, MstLedger.pincode).where(
            MstLedger.company_id == cid, MstLedger.group_id.in_(debtor_groups or {0})))).all() if debtor_groups else []
        city_of = await cities_for_ledgers(db, cid, [(r.ledger_id, r.pincode) for r in ledgers])
        sales, invoices, unattributed = await net_sales_by_customer(db, cid, start, end)
        previous, _, prev_unattributed = await net_sales_by_customer(db, cid, prev_start, prev_end)
        cash_sales += unattributed
        owed = {p.ledger_id: p for p in await receivables_ageing(db, cid, today=today)}
        for r in ledgers:
            city = cities[city_of[r.ledger_id][0]]
            city["customers"] += 1
            city["sales"] += sales.get(r.ledger_id, 0.0)
            city["sales_previous"] += previous.get(r.ledger_id, 0.0)
            city["invoices"] += invoices.get(r.ledger_id, 0)
            if sales.get(r.ledger_id, 0) > 0:
                city["buying"] += 1
            if r.ledger_id in owed:
                city["outstanding"] += owed[r.ledger_id].balance
                city["overdue"] += owed[r.ledger_id].overdue
        # Leads: directory entries without a Tally ledger
        leads = (await db.execute(select(CustomerProfile.city, CustomerProfile.pincode).where(
            CustomerProfile.company_id == cid, CustomerProfile.ledger_id.is_(None)))).all()
        for city_name, pincode in leads:
            name = normalise_city(city_name) or (by_pin.get(clean_pincode(pincode) or "", (None,))[0]) or NOT_SET
            cities[name]["leads"] += 1

    total_sales = sum(c["sales"] for c in cities.values()) + cash_sales
    rows = []
    for name, c in cities.items():
        rows.append({
            "city": name,
            **{k: round(v, 2) if isinstance(v, float) else v for k, v in c.items()},
            "change_pct": round((c["sales"] - c["sales_previous"]) / c["sales_previous"] * 100, 1) if c["sales_previous"] > 0 else None,
            "share_pct": round(c["sales"] / total_sales * 100, 1) if total_sales else 0.0,
            "average_invoice": round(c["sales"] / c["invoices"], 2) if c["invoices"] else None,
            "sales_per_buying_customer": round(c["sales"] / c["buying"], 2) if c["buying"] else None,
            # Room to grow: customers who didn't buy this month plus leads not yet in Tally
            "not_buying": c["customers"] - c["buying"],
            "buying_pct": round(c["buying"] / c["customers"] * 100, 1) if c["customers"] else 0.0,
        })
    rows.sort(key=lambda r: r["sales"], reverse=True)
    return {
        "month": start.strftime("%Y-%m"),
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "compared_with": {"from": prev_start.isoformat(), "to": prev_end.isoformat()},
        "total_sales": round(total_sales, 2),
        "cash_sales": round(cash_sales, 2),
        "cities": rows,
    }


class CityUpdate(BaseModel):
    city: Optional[str] = None


@router.get("/city-mapping")
async def city_mapping(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Every customer pincode in use with its city (an admin's choice or the proposal), and the customers whose
    city can't be worked out, for the Cities settings screen."""
    from app.services.cities import NOT_SET, cities_for_ledgers, clean_pincode, pincode_cities

    by_pin = await pincode_cities(db)
    pins: Dict[str, int] = defaultdict(int)
    unset = []
    companies = await _companies_for(db, user)
    for cid, company_name in companies.items():
        debtor_groups = await group_ids_under(db, cid, "Sundry Debtors")
        if not debtor_groups:
            continue
        ledgers = (await db.execute(select(MstLedger.ledger_id, MstLedger.name, MstLedger.pincode, MstLedger.address).where(
            MstLedger.company_id == cid, MstLedger.group_id.in_(debtor_groups)))).all()
        city_of = await cities_for_ledgers(db, cid, [(r.ledger_id, r.pincode) for r in ledgers])
        for r in ledgers:
            pin = clean_pincode(r.pincode)
            if pin:
                pins[pin] += 1
            if city_of[r.ledger_id][0] == NOT_SET:
                unset.append({"ledger_id": r.ledger_id, "company_id": cid, "company": company_name, "name": r.name,
                              "pincode": pin, "address": (r.address or "").strip()[:200] or None})
    return {
        "pincodes": sorted(
            ({"pincode": pin, "customers": n, "city": by_pin.get(pin, (None, None))[0], "source": by_pin.get(pin, (None, None))[1]}
             for pin, n in pins.items()),
            key=lambda p: (-p["customers"], p["pincode"]),
        ),
        "customers_without_city": sorted(unset, key=lambda c: c["name"].lower()),
    }


@router.put("/city-mapping/{pincode}")
async def set_pincode_city(
    pincode: str,
    req: CityUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set the city for a pincode, or with null go back to the proposed name. Admin only."""
    from app.models.portal_core import PincodeCity
    from app.services.cities import clean_pincode, normalise_city

    pin = clean_pincode(pincode)
    if not pin or pin != pincode:
        raise HTTPException(status_code=400, detail="Pincode must be 6 digits")
    row = (await db.execute(select(PincodeCity).where(PincodeCity.pincode == pin))).scalars().first()
    city = normalise_city(req.city)
    if city is None:
        if row:
            await db.delete(row)
    elif row:
        row.city, row.updated_by_user_id = city[:100], user.user_id
    else:
        db.add(PincodeCity(pincode=pin, city=city[:100], updated_by_user_id=user.user_id))
    await db.commit()
    return {"pincode": pin, "city": city}


@router.put("/customer-city/{ledger_id}")
async def set_customer_city(
    ledger_id: int,
    req: CityUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set a customer's city on their MyTally profile (creating the profile if needed). Admin only."""
    from app.services.cities import normalise_city

    ledger = (await db.execute(select(MstLedger.ledger_id, MstLedger.company_id).where(MstLedger.ledger_id == ledger_id))).first()
    companies = await _companies_for(db, user)
    if not ledger or ledger.company_id not in companies:
        raise HTTPException(status_code=404, detail="Customer not found")
    city = normalise_city(req.city)
    profile = (await db.execute(select(CustomerProfile).where(
        CustomerProfile.company_id == ledger.company_id, CustomerProfile.ledger_id == ledger_id))).scalars().first()
    if profile:
        profile.city = city
    elif city:
        db.add(CustomerProfile(company_id=ledger.company_id, ledger_id=ledger_id, city=city, created_by=user.user_id))
    await db.commit()
    return {"ledger_id": ledger_id, "city": city}


# ─── Collections priority ────────────────────────────────────────────────────

async def receivables_as_of(db: AsyncSession, company_id: int, day: date) -> float:
    """Total customers owe at the end of a day: opening balances plus all entries up to that day."""
    debtor_groups = await group_ids_under(db, company_id, "Sundry Debtors")
    if not debtor_groups:
        return 0.0
    opening = (await db.execute(
        select(MstLedger.opening_balance, MstLedger.opening_balance_type)
        .where(MstLedger.company_id == company_id, MstLedger.group_id.in_(debtor_groups))
    )).all()
    total = sum(float(o or 0) * (-1 if (t or "Dr").lower() == "cr" else 1) for o, t in opening)
    moved = (await db.execute(
        select(func.coalesce(func.sum(TrnAccounting.debit_amount - TrnAccounting.credit_amount), 0))
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .join(MstLedger, MstLedger.ledger_id == TrnAccounting.ledger_id)
        .where(MstLedger.company_id == company_id, MstLedger.group_id.in_(debtor_groups),
               live_voucher(), TrnVoucher.voucher_date <= day)
    )).scalar()
    return round(total + float(moved or 0), 2)


async def billed_between(db: AsyncSession, company_id: int, start: date, end: date) -> float:
    """What customers were billed, including GST, after returns: sales invoices minus credit notes."""
    debtor_groups = await group_ids_under(db, company_id, "Sundry Debtors")
    if not debtor_groups:
        return 0.0
    amount = (await db.execute(
        select(func.coalesce(func.sum(TrnAccounting.debit_amount - TrnAccounting.credit_amount), 0))
        .join(TrnVoucher, TrnVoucher.voucher_id == TrnAccounting.voucher_id)
        .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
        .join(MstLedger, MstLedger.ledger_id == TrnAccounting.ledger_id)
        .where(MstLedger.company_id == company_id, MstLedger.group_id.in_(debtor_groups), live_voucher(),
               TrnVoucher.voucher_date >= start, TrnVoucher.voucher_date <= end,
               (MstVoucherType.name.in_(("Sales", "Credit Note"))) | (MstVoucherType.parent_type.in_(("Sales", "Credit Note"))))
    )).scalar()
    return float(amount or 0)


async def days_sales_outstanding(db: AsyncSession, company_id: int, day: date) -> Optional[float]:
    """Days of sales customers owe: receivables at the day's end ÷ the last 90 days' billing × 90."""
    billed = await billed_between(db, company_id, day - timedelta(days=89), day)
    if billed <= 0:
        return None
    return round(await receivables_as_of(db, company_id, day) / billed * 90, 1)


@router.get("/collections")
async def collections_priority(
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Who to chase first (overdue amount weighted by how late it is), days sales outstanding by month-end, and
    the daily overdue history."""
    from app.services import snapshots

    today = get_ist_date()
    ageing = await receivables_ageing(db, user.company_id, today=today)
    await record_daily_snapshots(db, user.company_id, today, ageing=ageing)

    chase = []
    for p in ageing:
        overdue_bills = [b for b in p.bills if b.days_overdue > 0]
        if not overdue_bills or p.overdue <= 0:
            continue
        weighted_days = sum(b.outstanding * b.days_overdue for b in overdue_bills) / p.overdue
        chase.append({
            "ledger_id": p.ledger_id,
            "name": p.name,
            "phone": p.phone,
            "overdue": round(p.overdue, 2),
            "outstanding": p.balance,
            "average_days_late": round(weighted_days),
            "oldest_days_late": max(b.days_overdue for b in overdue_bills),
            "overdue_bills": len(overdue_bills),
            "credit_days": p.credit_days,
            "priority": round(p.overdue * (1 + weighted_days / 30), 2),
        })
    chase.sort(key=lambda c: c["priority"], reverse=True)

    dso_trend = []
    for day in snapshots.month_ends(today, 6):
        dso_trend.append({"day": day.isoformat(), "dso": await days_sales_outstanding(db, user.company_id, day)})

    return {
        "as_of": today.isoformat(),
        "receivables": round(sum(p.balance for p in ageing), 2),
        "overdue": round(sum(p.overdue for p in ageing), 2),
        "overdue_customers": len(chase),
        "dso": dso_trend[-1]["dso"],
        "dso_last_month_end": dso_trend[-2]["dso"] if len(dso_trend) > 1 else None,
        "dso_trend": dso_trend,
        "overdue_trend": [
            {"day": s["day"], "overdue": s.get("overdue"), "receivables": s.get("receivables")}
            for s in await snapshots.history(db, user.company_id, "receivables", today - timedelta(days=180))
        ],
        "chase": chase,
    }


# ─── Dead stock clearance ────────────────────────────────────────────────────

DEAD_STOCK_TREND_DAYS = 90  # the daily saved total always uses 90 days, so the trend stays comparable


async def dead_stock(db: AsyncSession, company_id: int, today: date, days: int, with_buyers: bool = True) -> dict:
    """Items in stock with no sale in the last `days` days, or never sold, grouped by how long they've sat."""
    stock_rows = (await db.execute(
        select(MstStockItem.stock_item_id, MstStockItem.name, MstStockItem.closing_qty, MstStockItem.closing_value,
               MstStockGroup.name.label("group_name"), MstUom.symbol)
        .outerjoin(MstStockGroup, MstStockGroup.stock_group_id == MstStockItem.stock_group_id)
        .outerjoin(MstUom, MstUom.unit_id == MstStockItem.unit_id)
        .where(MstStockItem.company_id == company_id, MstStockItem.closing_qty > 0)
    )).all()
    if not stock_rows:
        return {"total_value": 0.0, "count": 0, "bands": [], "items": []}
    item_ids = [r.stock_item_id for r in stock_rows]

    def movement(inward: bool, sales_only: bool, agg):
        stmt = (select(TrnInventory.stock_item_id, agg(TrnVoucher.voucher_date))
                .join(TrnVoucher, TrnVoucher.voucher_id == TrnInventory.voucher_id)
                .where(TrnInventory.stock_item_id.in_(item_ids), TrnInventory.is_inward == inward, live_voucher()))
        if sales_only:
            stmt = stmt.join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id).where(sales_voucher_type())
        return stmt.group_by(TrnInventory.stock_item_id)

    last_sale = dict((await db.execute(movement(False, True, func.max))).all())
    first_in = dict((await db.execute(movement(True, False, func.min))).all())
    cutoff = today - timedelta(days=days)

    bands = {name: {"band": name, "value": 0.0, "count": 0}
             for name in ("Under 180 days", "180–365 days", "Over 365 days", "Never sold")}
    items = []
    for r in stock_rows:
        sold = last_sale.get(r.stock_item_id)
        if sold and sold >= cutoff:
            continue
        since = sold or first_in.get(r.stock_item_id)
        age = (today - since).days if since else None
        band = "Never sold" if not sold else ("Over 365 days" if age > 365 else "180–365 days" if age >= 180 else "Under 180 days")
        value = float(r.closing_value or 0)
        bands[band]["value"] += value
        bands[band]["count"] += 1
        items.append({
            "stock_item_id": r.stock_item_id, "name": r.name, "group": r.group_name, "unit": r.symbol or "PCS",
            "stock": round(float(r.closing_qty or 0), 3), "value": round(value, 2), "band": band,
            "last_sold": sold.isoformat() if sold else None, "days_since_sale": (today - sold).days if sold else None,
            "in_stock_since": since.isoformat() if since else None, "buyers": [],
        })
    items.sort(key=lambda i: i["value"], reverse=True)

    if with_buyers and items:
        debtor_groups = await group_ids_under(db, company_id, "Sundry Debtors")
        dead_ids = [i["stock_item_id"] for i in items]
        if debtor_groups:
            rows = (await db.execute(
                select(TrnInventory.stock_item_id, TrnAccounting.ledger_id, func.sum(TrnInventory.quantity),
                       func.max(TrnVoucher.voucher_date))
                .join(TrnVoucher, TrnVoucher.voucher_id == TrnInventory.voucher_id)
                .join(MstVoucherType, MstVoucherType.voucher_type_id == TrnVoucher.voucher_type_id)
                .join(TrnAccounting, TrnAccounting.voucher_id == TrnVoucher.voucher_id)
                .join(MstLedger, MstLedger.ledger_id == TrnAccounting.ledger_id)
                .where(TrnInventory.stock_item_id.in_(dead_ids), TrnInventory.is_inward == False,  # noqa: E712
                       sales_voucher_type(), live_voucher(), MstLedger.group_id.in_(debtor_groups))
                .group_by(TrnInventory.stock_item_id, TrnAccounting.ledger_id)
            )).all()
            names = {}
            if rows:
                names = {r.ledger_id: r for r in (await db.execute(
                    select(MstLedger.ledger_id, MstLedger.name, MstLedger.mobile, MstLedger.phone)
                    .where(MstLedger.ledger_id.in_({row[1] for row in rows})))).all()}
            buyers: Dict[int, List[dict]] = defaultdict(list)
            for item_id, ledger_id, qty, last in rows:
                led = names[ledger_id]
                buyers[item_id].append({"ledger_id": ledger_id, "name": led.name, "phone": led.mobile or led.phone,
                                        "quantity": round(float(qty or 0), 3), "last_bought": last.isoformat() if last else None})
            for item in items:
                item["buyers"] = sorted(buyers[item["stock_item_id"]], key=lambda b: b["quantity"], reverse=True)[:3]

    return {
        "total_value": round(sum(b["value"] for b in bands.values()), 2),
        "count": len(items),
        "bands": [{**b, "value": round(b["value"], 2)} for b in bands.values()],
        "items": items,
    }


@router.get("/dead-stock")
async def dead_stock_clearance(
    days: int = Query(90, ge=1, le=3650, description="No sale for this many days"),
    user: User = Depends(require_permission("reports", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Dead stock to clear: every item in stock not sold for `days` days (or never), by age, with the customers
    who bought it before, and the daily trend of money locked (always measured at 90 days)."""
    from app.services import snapshots

    today = get_ist_date()
    await record_daily_snapshots(db, user.company_id, today)
    result = await dead_stock(db, user.company_id, today, days)
    trend = await snapshots.history(db, user.company_id, "dead_stock", today - timedelta(days=180))
    return {"as_of": today.isoformat(), "days": days, **result,
            "trend": [{"day": s["day"], "value": s.get("value"), "count": s.get("count")} for s in trend],
            "trend_days": DEAD_STOCK_TREND_DAYS}


async def record_daily_snapshots(db: AsyncSession, company_id: int, today: Optional[date] = None, ageing=None) -> None:
    """Save today's overdue and dead-stock totals for one company if not saved yet (daily job or first visit)."""
    from app.services import snapshots
    from app.services.receivables import BUCKETS

    today = today or get_ist_date()
    if not await snapshots.has_snapshot(db, company_id, "receivables", today):
        ageing = ageing if ageing is not None else await receivables_ageing(db, company_id, today=today)
        await snapshots.save_snapshot(db, company_id, "receivables", today, {
            "receivables": round(sum(p.balance for p in ageing), 2),
            "overdue": round(sum(p.overdue for p in ageing), 2),
            "buckets": {b: round(sum(p.buckets[b] for p in ageing), 2) for b in BUCKETS},
        })
    if not await snapshots.has_snapshot(db, company_id, "dead_stock", today):
        dead = await dead_stock(db, company_id, today, DEAD_STOCK_TREND_DAYS, with_buyers=False)
        await snapshots.save_snapshot(db, company_id, "dead_stock", today, {"value": dead["total_value"], "count": dead["count"]})
