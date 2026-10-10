"""Release 1 of the reporting review: overdue counted from each customer's credit days, the monthly sales target,
customers buying less, and items about to run out."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import auth, payment, report_insights
from app.services import receivables
from app.services.receivables import receivables_ageing
from tests.conftest import bearer, login, run

TODAY = date(2026, 10, 15)


class Books:
    """A tiny set of Tally books for one company: groups, voucher types, and helpers to post vouchers."""

    def __init__(self, harness, company, owner):
        self.h, self.cid, self.owner = harness, company.company_id, owner
        primary = harness.add(T.MstGroup(company_id=self.cid, name="Primary", nature="Asset"))
        self.debtors = harness.add(T.MstGroup(company_id=self.cid, name="Sundry Debtors", nature="Asset",
                                              parent_group_id=primary.group_id))
        self.sales_group = harness.add(T.MstGroup(company_id=self.cid, name="Sales Accounts", nature="Income",
                                                  parent_group_id=primary.group_id))
        self.sales_ledger = harness.add(T.MstLedger(company_id=self.cid, name="Sales", group_id=self.sales_group.group_id))
        self.types = {name: harness.add(T.MstVoucherType(company_id=self.cid, name=name, parent_type=name))
                      for name in ("Sales", "Credit Note", "Receipt", "Stock Journal")}
        self.n = 0

    def customer(self, name, **extra):
        return self.h.add(T.MstLedger(company_id=self.cid, name=name, group_id=self.debtors.group_id, **extra))

    def voucher(self, kind, day, amount, cancelled=False):
        self.n += 1
        return self.h.add(T.TrnVoucher(company_id=self.cid, voucher_type_id=self.types[kind].voucher_type_id,
                                       voucher_number=f"{kind[:2].upper()}-{self.n}", voucher_date=day,
                                       total_amount=Decimal(str(amount)), is_cancelled=cancelled, is_optional=False,
                                       created_by=self.owner.user_id))

    def sale(self, customer, days_ago, amount, cancelled=False, net=None):
        """Invoice: customer debited the full amount, sales credited the amount before GST."""
        v = self.voucher("Sales", TODAY - timedelta(days=days_ago), amount, cancelled)
        self.h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=customer.ledger_id, debit_amount=Decimal(str(amount)), credit_amount=0),
                   T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=self.sales_ledger.ledger_id, debit_amount=0,
                                   credit_amount=Decimal(str(net if net is not None else amount))))
        return v

    def receipt(self, customer, days_ago, amount):
        v = self.voucher("Receipt", TODAY - timedelta(days=days_ago), amount)
        self.h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=customer.ledger_id, debit_amount=0, credit_amount=Decimal(str(amount))))

    def credit_note(self, customer, days_ago, amount):
        v = self.voucher("Credit Note", TODAY - timedelta(days=days_ago), amount)
        self.h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=self.sales_ledger.ledger_id, debit_amount=Decimal(str(amount)), credit_amount=0),
                   T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=customer.ledger_id, debit_amount=0, credit_amount=Decimal(str(amount))))


@pytest.fixture
def world(harness, monkeypatch):
    monkeypatch.setattr(report_insights, "get_ist_date", lambda: TODAY)
    monkeypatch.setattr(receivables, "get_ist_date", lambda: TODAY)
    alpha = harness.company("Alpha")
    beta = harness.company("Beta")
    admin_role = harness.role("Admin")
    sales_role = harness.role("Sales")
    owner = harness.user(alpha, admin_role, "owner")
    staff = harness.user(alpha, sales_role, "staff")
    # Staff can read reports, payments and outstanding
    for code in ("reports", "payments", "outstanding"):
        module = harness.add(P.Module(code=code, name=code.title()))
        harness.add(P.Permission(role_id=sales_role.role_id, module_id=module.module_id, can_read=True))
    client = harness.app(auth.router, payment.router, report_insights.router)
    return dict(h=harness, alpha=alpha, beta=beta, owner=owner, client=client,
                books=Books(harness, alpha, owner), beta_books=Books(harness, beta, owner))


def ageing(world):
    async def go():
        async with world["h"].Session() as db:
            return {p.name: p for p in await receivables_ageing(db, world["alpha"].company_id, today=TODAY)}
    return run(go())


def test_overdue_counts_from_each_customers_credit_days(world):
    b = world["books"]
    amar = b.customer("Amar")                               # no credit days anywhere: default 30
    jain = b.customer("Jain", credit_period_days=10)        # Tally credit period used when set
    b.sale(amar, days_ago=20, amount=1000)
    b.sale(jain, days_ago=20, amount=500)
    b.sale(amar, days_ago=5, amount=999, cancelled=True)    # cancelled: never counts

    aged = ageing(world)
    assert aged["Amar"].balance == 1000 and aged["Amar"].overdue == 0      # 20 days < 30: not due yet
    assert (aged["Amar"].credit_days, aged["Amar"].credit_days_source) == (30, "default")
    assert aged["Jain"].buckets["1-30 Days"] == 500                         # 10 days late
    assert aged["Jain"].credit_days_source == "tally"

    # Setting the customer's own credit days (admin) overrides both
    client = world["client"]
    owner = login(client, "owner@example.com")
    r = client.put(f"/payment/credit-days/{amar.ledger_id}", json={"credit_days": 7}, headers=bearer(owner))
    assert r.status_code == 200
    aged = ageing(world)
    assert aged["Amar"].buckets["1-30 Days"] == 1000 and aged["Amar"].credit_days_source == "customer"
    bill = aged["Amar"].bills[0]
    assert bill.days_overdue == 13 and bill.due_date == TODAY - timedelta(days=13)

    # Clearing it falls back to the default again; staff can't change credit days
    client.put(f"/payment/credit-days/{amar.ledger_id}", json={"credit_days": None}, headers=bearer(owner))
    assert ageing(world)["Amar"].credit_days_source == "default"
    staff = login(client, "staff@example.com")
    assert client.put(f"/payment/credit-days/{amar.ledger_id}", json={"credit_days": 5}, headers=bearer(staff)).status_code == 403
    assert client.put(f"/payment/credit-days/{amar.ledger_id}", json={"credit_days": 400}, headers=bearer(owner)).status_code == 400


def test_payments_clear_oldest_bills_and_opening_balance_counts(world):
    b = world["books"]
    gupta = b.customer("Gupta", opening_balance=Decimal("300"), opening_balance_type="Dr")
    b.sale(gupta, days_ago=100, amount=400)
    b.sale(gupta, days_ago=45, amount=600)
    b.receipt(gupta, days_ago=10, amount=700)   # clears the opening balance and the oldest invoice first

    p = ageing(world)["Gupta"]
    assert p.balance == 600
    assert [(bill.voucher_number, bill.outstanding, bill.bucket) for bill in p.bills] == [("SA-2", 600.0, "1-30 Days")]


def test_outstanding_screen_uses_the_shared_ageing(world):
    b = world["books"]
    amar = b.customer("Amar")
    b.sale(amar, days_ago=40, amount=1000)
    staff = login(world["client"], "staff@example.com")
    data = world["client"].get("/payment/aging/dashboard", headers=bearer(staff)).json()
    customer = data["customers"][0]
    assert (customer["credit_period_days"], customer["credit_days_source"]) == (30, "default")
    assert customer["days_1_30"] == 1000 and data["kpis"]["total_overdue"] == 1000
    assert data["default_credit_days"] == 30


def test_monthly_target_is_for_the_current_company_only(world):
    a, z = world["books"], world["beta_books"]
    amar, beta_shop = a.customer("Amar"), z.customer("Beta Shop")
    a.sale(amar, days_ago=10, amount=118_000, net=100_000)       # Oct 5: 1 L before GST
    a.credit_note(amar, days_ago=5, amount=10_000)                # returns reduce net sales
    z.sale(beta_shop, days_ago=2, amount=59_000, net=50_000)      # another company: never added in
    a.sale(amar, days_ago=20, amount=1_000_000)                   # September: not this month

    client = world["client"]
    owner, staff = login(client, "owner@example.com"), login(client, "staff@example.com")
    assert client.put("/reports/settings", json={"monthly_sales_target": 1_000_000}, headers=bearer(staff)).status_code == 403
    assert client.put("/reports/settings", json={"monthly_sales_target": -5}, headers=bearer(owner)).status_code == 400
    assert client.put("/reports/settings", json={"monthly_sales_target": 1_000_000}, headers=bearer(owner)).status_code == 200

    t = client.get("/reports/sales-target", headers=bearer(owner)).json()
    assert t["month"] == "2026-10" and t["sales"] == 90_000 and t["target"] == 1_000_000
    assert t["days_elapsed"] == 15 and t["days_left"] == 17           # all 7 days count; today included
    assert t["needed_per_day"] == round(910_000 / 17, 2)
    assert t["projected"] == round(90_000 / 15 * 31, 2) and t["on_track"] is False
    assert "companies" not in t
    assert t["daily"][-1]["cumulative"] == 90_000 and len(t["daily"]) == 15

    # The other company has its own sales and its own target; setting one never moves the other
    in_beta = bearer(owner, {"X-Company-ID": str(world["beta"].company_id)})
    other = client.get("/reports/sales-target", headers=in_beta).json()
    assert other["sales"] == 50_000 and other["target"] == 2_000_000      # the default: Alpha's target is not Beta's
    assert client.put("/reports/settings", json={"monthly_sales_target": 300_000}, headers=in_beta).status_code == 200
    assert client.get("/reports/sales-target", headers=in_beta).json()["target"] == 300_000
    assert client.get("/reports/sales-target", headers=bearer(owner)).json()["target"] == 1_000_000


def test_watchlist_flags_customers_buying_less_or_later(world):
    b = world["books"]
    steady, dropped, late = b.customer("Steady"), b.customer("Dropped", mobile="9810012345"), b.customer("Late")
    for days in range(5, 180, 15):
        b.sale(steady, days, 1000)
    b.sale(dropped, 150, 100_000)
    b.sale(dropped, 20, 20_000)
    for days in (70, 60, 50, 40):                                   # every 10 days, then nothing for 40
        b.sale(late, days, 5000)

    client = world["client"]
    staff = login(client, "staff@example.com")
    rows = {c["name"]: c for c in client.get("/reports/customer-watchlist", headers=bearer(staff)).json()["customers"]}
    assert set(rows) == {"Dropped", "Late"}
    assert rows["Dropped"]["reasons"] == ["dropped"] and rows["Dropped"]["change_pct"] == -80.0
    assert rows["Dropped"]["phone"] == "9810012345" and rows["Dropped"]["outstanding"] == 120_000
    assert rows["Late"]["reasons"] == ["late"] and rows["Late"]["usual_gap_days"] == 10

    # Thresholds are adjustable: only a fall of more than 90% now counts as dropped
    rows = client.get("/reports/customer-watchlist?drop_pct=90", headers=bearer(staff)).json()["customers"]
    assert [c["name"] for c in rows] == ["Late"]


def test_reorder_alerts_use_recent_sales_only(world):
    h, b = world["h"], world["books"]
    cid = world["alpha"].company_id
    unit = h.add(T.MstUom(company_id=cid, name="Pieces", symbol="PCS"))
    group = h.add(T.MstStockGroup(company_id=cid, name="Kitchen"))

    def item(name, stock):
        return h.add(T.MstStockItem(company_id=cid, name=name, stock_group_id=group.stock_group_id, unit_id=unit.unit_id,
                                    closing_qty=Decimal(stock), closing_value=Decimal(stock * 100)))

    def move(it, kind, days_ago, qty):
        v = b.voucher(kind, TODAY - timedelta(days=days_ago), qty * 100)
        h.add(T.TrnInventory(voucher_id=v.voucher_id, stock_item_id=it.stock_item_id, quantity=Decimal(qty),
                             rate=Decimal(100), amount=Decimal(qty * 100), is_inward=False))

    kettle, fan, fryer = item("Kettle", 10), item("Fan", 500), item("Fryer", 0)
    move(kettle, "Sales", 5, 60)            # 2 a day, 10 left: 5 days
    move(fan, "Sales", 5, 30)               # 1 a day, 500 left: plenty
    move(fryer, "Sales", 3, 15)             # sold out
    move(fan, "Stock Journal", 2, 400)      # a transfer is not a sale

    staff = login(world["client"], "staff@example.com")
    items = world["client"].get("/reports/reorder-alerts", headers=bearer(staff)).json()["items"]
    assert [(i["name"], i["days_left"], i["out_of_stock"]) for i in items] == [("Fryer", 0.0, True), ("Kettle", 5.0, False)]
    assert items[1]["suggested_order"] == 50                     # 30 days at 2/day, minus 10 in stock
    items = world["client"].get("/reports/reorder-alerts?cover_days=3", headers=bearer(staff)).json()["items"]
    assert [i["name"] for i in items] == ["Fryer"]


# ─── Release 2: cities, collections, dead stock ──────────────────────────────

def test_city_report_uses_profile_city_then_pincode(world):
    b, h, client = world["books"], world["h"], world["client"]
    meerut = b.customer("Meerut Mart", pincode="250002")
    hapur = b.customer("Hapur Hub", pincode="245101")
    mawana = b.customer("Mawana Store", pincode="250002")         # profile city wins over the pincode
    h.add(P.CustomerProfile(company_id=world["alpha"].company_id, ledger_id=mawana.ledger_id, city="mawana"))
    nowhere = b.customer("No Address")
    h.add(P.CustomerProfile(company_id=world["alpha"].company_id, ledger_id=None, custom_name="New Lead", city="Hapur"))

    b.sale(meerut, days_ago=3, amount=11800, net=10000)            # Oct 12: this month
    b.sale(meerut, days_ago=33, amount=5900, net=5000)             # Sep 12: same days last month
    b.sale(hapur, days_ago=40, amount=5900, net=5000)              # Sep 5: last month only
    b.sale(mawana, days_ago=1, amount=2360, net=2000)

    staff = login(client, "staff@example.com")
    data = client.get("/reports/cities", headers=bearer(staff)).json()
    rows = {r["city"]: r for r in data["cities"]}
    assert set(rows) == {"Meerut", "Hapur", "Mawana", "City not set"}
    assert rows["Meerut"]["sales"] == 10000 and rows["Meerut"]["sales_previous"] == 5000 and rows["Meerut"]["change_pct"] == 100.0
    assert rows["Hapur"]["buying"] == 0 and rows["Hapur"]["customers"] == 1 and rows["Hapur"]["leads"] == 1
    assert rows["Hapur"]["sales_previous"] == 5000 and rows["Hapur"]["not_buying"] == 1
    assert rows["Mawana"]["sales"] == 2000 and rows["City not set"]["customers"] == 1
    assert data["compared_with"] == {"from": "2026-09-01", "to": "2026-09-15"}

    # Admin corrections: a pincode's city, and a customer's own city
    owner = login(client, "owner@example.com")
    assert client.put("/reports/city-mapping/245101", json={"city": "garhmukteshwar"}, headers=bearer(staff)).status_code == 403
    assert client.put("/reports/city-mapping/245101", json={"city": "garhmukteshwar"}, headers=bearer(owner)).status_code == 200
    assert client.put(f"/reports/customer-city/{nowhere.ledger_id}", json={"city": "Sardhana"}, headers=bearer(owner)).status_code == 200
    rows = {r["city"]: r for r in client.get("/reports/cities", headers=bearer(staff)).json()["cities"]}
    assert "Garhmukteshwar" in rows and "Sardhana" in rows and "City not set" not in rows

    mapping = client.get("/reports/city-mapping", headers=bearer(staff)).json()
    pins = {p["pincode"]: (p["city"], p["source"], p["customers"]) for p in mapping["pincodes"]}
    assert pins == {"250002": ("Meerut", "proposed", 2), "245101": ("Garhmukteshwar", "set", 1)}
    assert mapping["customers_without_city"] == []
    # Clearing the correction goes back to the proposal
    client.put("/reports/city-mapping/245101", json={"city": None}, headers=bearer(owner))
    pins = {p["pincode"]: p["city"] for p in client.get("/reports/city-mapping", headers=bearer(staff)).json()["pincodes"]}
    assert pins["245101"] == "Hapur"


def test_collections_ranks_by_amount_and_lateness(world):
    b, client = world["books"], world["client"]
    big_recent, small_old, current = b.customer("Big Recent"), b.customer("Small Old"), b.customer("On Time")
    b.sale(big_recent, days_ago=40, amount=100_000)        # 10 days late
    b.sale(small_old, days_ago=150, amount=60_000)         # 120 days late
    b.sale(current, days_ago=5, amount=50_000)             # not due

    staff = login(client, "staff@example.com")
    data = client.get("/reports/collections", headers=bearer(staff)).json()
    assert [c["name"] for c in data["chase"]] == ["Small Old", "Big Recent"]   # 60k × (1+120/30) beats 100k × (1+10/30)
    assert data["chase"][0]["average_days_late"] == 120 and data["overdue"] == 160_000
    assert data["receivables"] == 210_000
    # DSO today: 2.1 L owed ÷ 1.5 L billed in the last 90 days × 90
    assert data["dso"] == 126.0 and len(data["dso_trend"]) == 7
    assert data["overdue_trend"] == [{"day": "2026-10-15", "overdue": 160_000, "receivables": 210_000}]

    # Today's figures are saved once, however often the report is opened
    client.get("/reports/collections", headers=bearer(staff))
    assert world["h"].scalar(select_count(P.ReportSnapshot)) == 2   # receivables + dead stock


def test_dead_stock_clearance_by_age_with_past_buyers(world):
    h, b, client = world["h"], world["books"], world["client"]
    cid = world["alpha"].company_id
    unit = h.add(T.MstUom(company_id=cid, name="Pieces", symbol="PCS"))
    buyer = b.customer("Jain Bros", mobile="9876543210")

    def item(name, stock, value):
        return h.add(T.MstStockItem(company_id=cid, name=name, unit_id=unit.unit_id,
                                    closing_qty=Decimal(stock), closing_value=Decimal(value)))

    def move(it, kind, days_ago, qty, inward, party=None):
        v = b.voucher(kind, TODAY - timedelta(days=days_ago), qty * 100)
        h.add(T.TrnInventory(voucher_id=v.voucher_id, stock_item_id=it.stock_item_id, quantity=Decimal(qty),
                             rate=Decimal(100), amount=Decimal(qty * 100), is_inward=inward))
        if party:
            h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=party.ledger_id, debit_amount=Decimal(qty * 100), credit_amount=0))

    never, stale, fresh, gone = item("Never Sold", 5, 5000), item("Stale", 3, 900), item("Fresh", 9, 2700), item("Gone", 0, 0)
    move(never, "Stock Journal", 400, 5, True)
    move(stale, "Sales", 200, 2, False, party=buyer)
    move(fresh, "Sales", 10, 1, False, party=buyer)
    move(gone, "Sales", 300, 4, False, party=buyer)

    staff = login(client, "staff@example.com")
    data = client.get("/reports/dead-stock", headers=bearer(staff)).json()
    assert [(i["name"], i["band"]) for i in data["items"]] == [("Never Sold", "Never sold"), ("Stale", "180–365 days")]
    assert data["total_value"] == 5900 and data["count"] == 2
    assert data["items"][1]["buyers"] == [{"ledger_id": buyer.ledger_id, "name": "Jain Bros", "phone": "9876543210",
                                           "quantity": 2.0, "last_bought": "2026-03-29"}]
    assert {b_["band"]: b_["value"] for b_ in data["bands"]}["Never sold"] == 5000
    assert data["trend"] == [{"day": "2026-10-15", "value": 5900, "count": 2}]
    # A longer threshold: the item sold 200 days ago no longer counts
    assert [i["name"] for i in client.get("/reports/dead-stock?days=300", headers=bearer(staff)).json()["items"]] == ["Never Sold"]


def select_count(model):
    from sqlalchemy import func, select
    return select(func.count()).select_from(model)
