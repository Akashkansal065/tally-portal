"""
Test item-level partial dispatch and remaining order amount decrease.
"""
import pytest
from app.routers import auth, orders
import app.models.portal_core as P
import app.models.tally_core as T
from tests.conftest import bearer, login


@pytest.fixture
def partial_dispatch_world(harness):
    h = harness
    company = h.company("SnehDist")
    admin_role = h.role("Admin")
    sales_role = h.role("Salesperson")

    owner = h.user(company, admin_role, "owner")
    sales_rep = h.user(company, sales_role, "sales_rep")
    sales_rep2 = h.user(company, sales_role, "sales_rep2")

    # Grant orders permissions
    module = h.add(P.Module(code="orders", name="Orders"))
    admin_mod = h.add(P.Module(code="admin", name="Admin"))
    h.add(P.Permission(role_id=sales_role.role_id, module_id=module.module_id, can_read=True, can_create=True, can_update=True))
    h.add(P.Permission(role_id=admin_role.role_id, module_id=module.module_id, can_read=True, can_create=True, can_update=True, can_delete=True))
    h.add(P.Permission(role_id=admin_role.role_id, module_id=admin_mod.module_id, can_read=True, can_create=True, can_update=True, can_delete=True))

    cid = company.company_id
    group = h.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    customer = h.add(T.MstLedger(company_id=cid, name="Agarwal Crockery", group_id=group.group_id, gstin="09BAAPA7681Q1Z6"))

    uom = h.add(T.MstUom(company_id=cid, name="Pieces", symbol="PCS"))
    stock_group = h.add(T.MstStockGroup(company_id=cid, name="Plates"))
    item1 = h.add(T.MstStockItem(
        company_id=cid, name="Dinner Plate 10in", stock_group_id=stock_group.stock_group_id, unit_id=uom.unit_id, closing_qty=100
    ))
    item2 = h.add(T.MstStockItem(
        company_id=cid, name="Bowl 6in", stock_group_id=stock_group.stock_group_id, unit_id=uom.unit_id, closing_qty=100
    ))

    client = h.app(auth.router, orders.router)
    owner_token = bearer(login(client, "owner@example.com"))
    sales_token = bearer(login(client, "sales_rep@example.com"))
    sales_token2 = bearer(login(client, "sales_rep2@example.com"))

    return {
        "client": client,
        "owner_token": owner_token,
        "sales_token": sales_token,
        "sales_token2": sales_token2,
        "customer": customer,
        "item1": item1,
        "item2": item2,
    }


def test_item_level_partial_dispatch_and_amounts(partial_dispatch_world):
    client = partial_dispatch_world["client"]
    owner_token = partial_dispatch_world["owner_token"]
    sales_token = partial_dispatch_world["sales_token"]
    sales_token2 = partial_dispatch_world["sales_token2"]
    cust = partial_dispatch_world["customer"]
    i1 = partial_dispatch_world["item1"]
    i2 = partial_dispatch_world["item2"]

    # 1. Create order with 2 items:
    # Item 1: 10 qty @ 200 = 2000
    # Item 2: 5 qty @ 100 = 500
    # Custom item: 2 qty @ 500 = 1000
    # Total = 3500
    create_res = client.post("/temporders", json={
        "ledger_id": cust.ledger_id,
        "items": [
            {"stock_item_id": i1.stock_item_id, "qty": 10, "price": 200.0},
            {"stock_item_id": i2.stock_item_id, "qty": 5, "price": 100.0},
            {"custom_item_name": "Custom Serving Spoon", "qty": 2, "price": 500.0},
        ]
    }, headers=sales_token)
    assert create_res.status_code == 200
    order_id = create_res.json()["id"]

    # 2. Get order details initially
    res = client.get(f"/temporders/{order_id}", headers=owner_token)
    assert res.status_code == 200
    ord_data = res.json()
    assert ord_data["status"] == "pending"
    assert ord_data["total"] == 3500.0
    assert ord_data["sent_total"] == 0.0
    assert ord_data["remaining_total"] == 3500.0
    assert ord_data["sent_items_count"] == 0
    assert ord_data["total_items_count"] == 3
    items = ord_data["items"]
    assert len(items) == 3

    item1_id = items[0]["id"]
    item2_id = items[1]["id"]
    item3_id = items[2]["id"]

    # 3. Mark item 1 as sent (10 qty @ 200 = 2000)
    dispatch_res1 = client.put(f"/temporders/{order_id}/items/{item1_id}/dispatch", json={
        "is_sent": True
    }, headers=owner_token)
    assert dispatch_res1.status_code == 200
    d1 = dispatch_res1.json()
    assert d1["status"] == "partial"
    assert d1["total"] == 3500.0
    assert d1["sent_total"] == 2000.0
    assert d1["remaining_total"] == 1500.0
    assert d1["sent_items_count"] == 1

    # Verify item-level details in response
    it1 = next(it for it in d1["items"] if it["id"] == item1_id)
    assert it1["is_sent"] is True
    assert it1["sent_qty"] == 10.0
    assert it1["sent_subtotal"] == 2000.0
    assert it1["remaining_subtotal"] == 0.0

    # 4. Mark item 2 as sent (5 qty @ 100 = 500)
    dispatch_res2 = client.put(f"/temporders/{order_id}/items/{item2_id}/dispatch", json={
        "is_sent": True
    }, headers=owner_token)
    assert dispatch_res2.status_code == 200
    d2 = dispatch_res2.json()
    assert d2["status"] == "partial"
    assert d2["sent_total"] == 2500.0
    assert d2["remaining_total"] == 1000.0
    assert d2["sent_items_count"] == 2

    # 5. Mark item 3 as sent (all items now sent)
    dispatch_res3 = client.put(f"/temporders/{order_id}/items/{item3_id}/dispatch", json={
        "is_sent": True
    }, headers=owner_token)
    assert dispatch_res3.status_code == 200
    d3 = dispatch_res3.json()
    assert d3["status"] == "done"  # All items sent -> automatically done!
    assert d3["sent_total"] == 3500.0
    assert d3["remaining_total"] == 0.0
    assert d3["sent_items_count"] == 3

    # 6. Unmark item 2 (undo)
    undo_res = client.put(f"/temporders/{order_id}/items/{item2_id}/dispatch", json={
        "is_sent": False
    }, headers=owner_token)
    assert undo_res.status_code == 200
    u = undo_res.json()
    assert u["status"] == "partial"  # Reverts from done to partial!
    assert u["sent_total"] == 3000.0
    assert u["remaining_total"] == 500.0
    assert u["sent_items_count"] == 2

    # 7. Batch dispatch: unmark all items
    batch_res = client.put(f"/temporders/{order_id}/items-dispatch", json={
        "items": [
            {"item_id": item1_id, "is_sent": False},
            {"item_id": item3_id, "is_sent": False},
        ]
    }, headers=owner_token)
    assert batch_res.status_code == 200
    b = batch_res.json()
    assert b["status"] == "pending"  # Reverts to pending
    assert b["sent_total"] == 0.0
    assert b["remaining_total"] == 3500.0
    assert b["sent_items_count"] == 0

    # 8. Non-owner regular salesperson cannot dispatch someone else's order
    sales_dispatch = client.put(f"/temporders/{order_id}/items/{item1_id}/dispatch", json={
        "is_sent": True
    }, headers=sales_token2)
    assert sales_dispatch.status_code == 403
    assert "Not authorized" in sales_dispatch.json()["detail"]

    # 9. Cancel the order
    cancel_res = client.put(f"/temporders/{order_id}/status", json={
        "status": "cancelled",
        "reason": "Customer cancelled"
    }, headers=owner_token)
    assert cancel_res.status_code == 200
    c_data = cancel_res.json()
    assert c_data["status"] == "cancelled"
    assert c_data["success"] is True

    # 10. Dispatching on a cancelled order must be blocked (single item & batch)
    dis_cancelled = client.put(f"/temporders/{order_id}/items/{item1_id}/dispatch", json={
        "is_sent": True
    }, headers=owner_token)
    assert dis_cancelled.status_code == 400
    assert "cancelled" in dis_cancelled.json()["detail"].lower()

    batch_cancelled = client.put(f"/temporders/{order_id}/items-dispatch", json={
        "items": [{"item_id": item1_id, "is_sent": True}]
    }, headers=owner_token)
    assert batch_cancelled.status_code == 400
    assert "cancelled" in batch_cancelled.json()["detail"].lower()
