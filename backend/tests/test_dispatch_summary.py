"""
Test Daily Dispatch Summary Endpoint (/temporders/dispatch-summary)
Verifies:
1. Aggregation of items across multiple orders on the same day.
2. Filtering by date and status.
3. Quantities, amounts, and customer breakdowns.
"""
from datetime import datetime, date
import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import auth, orders
from tests.conftest import bearer, login


@pytest.fixture
def dispatch_world(harness):
    h = harness
    company = h.company("SnehDist")
    admin_role = h.role("Admin")
    sales_role = h.role("Salesperson")

    owner = h.user(company, admin_role, "owner")
    sales_rep = h.user(company, sales_role, "sales_rep")

    # Grant orders permissions
    module = h.add(P.Module(code="orders", name="Orders"))
    admin_mod = h.add(P.Module(code="admin", name="Admin"))
    h.add(P.Permission(role_id=sales_role.role_id, module_id=module.module_id, can_read=True, can_create=True, can_update=True))
    h.add(P.Permission(role_id=admin_role.role_id, module_id=module.module_id, can_read=True, can_create=True, can_update=True, can_delete=True))
    h.add(P.Permission(role_id=admin_role.role_id, module_id=admin_mod.module_id, can_read=True, can_create=True, can_update=True, can_delete=True))

    cid = company.company_id
    group = h.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    customer1 = h.add(T.MstLedger(company_id=cid, name="Agarwal Store", group_id=group.group_id, gstin="07AAAAA0000A1Z5"))
    customer2 = h.add(T.MstLedger(company_id=cid, name="Sharma Retailers", group_id=group.group_id, gstin="07BBBBB0000B1Z6"))

    uom = h.add(T.MstUom(company_id=cid, name="Pieces", symbol="PCS"))
    stock_group = h.add(T.MstStockGroup(company_id=cid, name="Biscuits"))
    item1 = h.add(T.MstStockItem(
        company_id=cid, name="Parle-G 100g", stock_group_id=stock_group.stock_group_id, unit_id=uom.unit_id, closing_qty=500
    ))
    item2 = h.add(T.MstStockItem(
        company_id=cid, name="Good Day 120g", stock_group_id=stock_group.stock_group_id, unit_id=uom.unit_id, closing_qty=200
    ))

    client = h.app(auth.router, orders.router)
    owner_token = bearer(login(client, "owner@example.com"))
    sales_token = bearer(login(client, "sales_rep@example.com"))

    return {
        "client": client,
        "owner_token": owner_token,
        "sales_token": sales_token,
        "customer1": customer1,
        "customer2": customer2,
        "item1": item1,
        "item2": item2,
    }


def test_dispatch_summary_aggregation(dispatch_world):
    client = dispatch_world["client"]
    token = dispatch_world["sales_token"]
    owner_token = dispatch_world["owner_token"]
    c1 = dispatch_world["customer1"]
    c2 = dispatch_world["customer2"]
    i1 = dispatch_world["item1"]
    i2 = dispatch_world["item2"]

    # 1. Create Order #1: Agarwal Store orders 50 Parle-G and 20 Good Day
    r1 = client.post("/temporders", json={
        "ledger_id": c1.ledger_id,
        "items": [
            {"stock_item_id": i1.stock_item_id, "qty": 50, "price": 10},
            {"stock_item_id": i2.stock_item_id, "qty": 20, "price": 30},
        ]
    }, headers=token)
    assert r1.status_code == 200, r1.text

    # 2. Create Order #2: Sharma Retailers orders 30 Parle-G and 10 Custom Cake
    r2 = client.post("/temporders", json={
        "ledger_id": c2.ledger_id,
        "items": [
            {"stock_item_id": i1.stock_item_id, "qty": 30, "price": 10},
            {"custom_item_name": "Vanilla Cream Cake", "qty": 10, "price": 50},
        ]
    }, headers=token)
    assert r2.status_code == 200, r2.text

    # 3. Call GET /temporders/dispatch-summary as admin
    today_str = date.today().isoformat()
    res = client.get(f"/temporders/dispatch-summary?date={today_str}&status=active", headers=owner_token)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["total_orders"] == 2
    assert data["total_distinct_items"] == 3  # Parle-G, Good Day, Custom Cake
    # Total quantity: 50 + 20 + 30 + 10 = 110
    assert data["total_quantity"] == 110.0
    # Total amount: (50*10=500) + (20*30=600) + (30*10=300) + (10*50=500) = 1900
    assert data["total_amount"] == 1900.0

    # Verify consolidated item 1: Parle-G should have 80 total qty across 2 orders
    parle_g = next((x for x in data["items"] if x["item_name"] == "Parle-G 100g"), None)
    assert parle_g is not None
    assert parle_g["total_qty"] == 80.0
    assert parle_g["orders_count"] == 2
    assert parle_g["unique_customers_count"] == 2
    assert len(parle_g["order_breakdown"]) == 2

    # Verify custom item
    custom_cake = next((x for x in data["items"] if x["item_name"] == "Vanilla Cream Cake"), None)
    assert custom_cake is not None
    assert custom_cake["total_qty"] == 10.0
    assert custom_cake["is_custom"] is True

    # 4. Filter by status: done should return 0 orders
    res_done = client.get(f"/temporders/dispatch-summary?date={today_str}&status=done", headers=owner_token)
    assert res_done.status_code == 200
    assert res_done.json()["total_orders"] == 0

    # 5. Filter by different date: should return 0 orders
    res_past = client.get("/temporders/dispatch-summary?date=2025-01-01&status=active", headers=owner_token)
    assert res_past.status_code == 200
    assert res_past.json()["total_orders"] == 0
