"""Everyone's orders need the Order dispatch permission; the Orders module alone covers only one's own.

A salesperson (the default Sales role: full Orders access) places orders, sees and edits only their own and only
for 30 minutes, and can never mark items sent or set an order done: that is dispatch work. A role with Order
dispatch sees, edits and dispatches every salesperson's orders. Admins have it without being given it.
"""
from datetime import timedelta

import pytest
from sqlalchemy import select, update

import app.models.portal_core as P
import app.models.tally_core as T
from app.core.datetime_utils import get_ist_now
from app.routers import auth, orders
from tests.conftest import bearer, login


@pytest.fixture
def world(harness):
    h = harness
    company = h.company("SnehDist")
    admin_role, sales_role, dispatch_role = h.role("Admin"), h.role("Sales"), h.role("Dispatch")
    h.user(company, admin_role, "owner")
    h.user(company, sales_role, "vishal")
    h.user(company, sales_role, "ravi")
    h.user(company, dispatch_role, "store")

    orders_mod = h.add(P.Module(code="orders", name="Orders"))
    dispatch_mod = h.add(P.Module(code="order_dispatch", name="Order Dispatch"))
    full = dict(can_create=True, can_read=True, can_update=True, can_delete=True)
    # The default Sales role: everything on Orders, nothing on Order dispatch
    h.add(P.Permission(role_id=sales_role.role_id, module_id=orders_mod.module_id, **full))
    # A dispatch desk: reads orders, and holds Order dispatch
    h.add(P.Permission(role_id=dispatch_role.role_id, module_id=orders_mod.module_id, can_read=True))
    h.add(P.Permission(role_id=dispatch_role.role_id, module_id=dispatch_mod.module_id, can_read=True, can_update=True))

    cid = company.company_id
    group = h.add(T.MstGroup(company_id=cid, name="Sundry Debtors", nature="Asset"))
    customer = h.add(T.MstLedger(company_id=cid, name="Agarwal Crockery", group_id=group.group_id))
    uom = h.add(T.MstUom(company_id=cid, name="Pieces", symbol="PCS"))
    item = h.add(T.MstStockItem(company_id=cid, name="Dinner Plate", unit_id=uom.unit_id, closing_qty=100))

    client = h.app(auth.router, orders.router)
    tokens = {name: bearer(login(client, f"{name}@example.com")) for name in ("owner", "vishal", "ravi", "store")}
    order_body = {"ledger_id": customer.ledger_id, "items": [{"stock_item_id": item.stock_item_id, "qty": 4, "price": 100.0}]}

    def place(name):
        res = client.post("/temporders", json=order_body, headers=tokens[name])
        assert res.status_code == 200, res.text
        return client.get(f"/temporders/{res.json()['id']}", headers=tokens[name]).json()   # with its items

    def age(order_id, minutes):
        h.execute(update(orders.TempOrder).where(orders.TempOrder.id == order_id)
                  .values(created_at=get_ist_now() - timedelta(minutes=minutes)))

    def status_of(order_id):
        return h.scalar(select(orders.TempOrder.status).where(orders.TempOrder.id == order_id))

    return {"client": client, "tokens": tokens, "body": order_body, "place": place, "age": age, "status_of": status_of}


def test_salesperson_cannot_dispatch_or_complete_even_their_own_order(world):
    client, sales = world["client"], world["tokens"]["vishal"]
    order = world["place"]("vishal")
    item_id = order["items"][0]["id"]

    assert client.put(f"/temporders/{order['id']}/items/{item_id}/dispatch", json={"is_sent": True}, headers=sales).status_code == 403
    assert client.put(f"/temporders/{order['id']}/items-dispatch",
                      json={"items": [{"item_id": item_id, "is_sent": True}]}, headers=sales).status_code == 403
    assert client.put(f"/temporders/{order['id']}/status", json={"status": "done"}, headers=sales).status_code == 403
    assert world["status_of"](order["id"]) == "pending"


def test_salesperson_sees_and_edits_only_their_own_orders_for_30_minutes(world):
    client, tokens = world["client"], world["tokens"]
    mine, theirs = world["place"]("vishal"), world["place"]("ravi")
    sales = tokens["vishal"]

    assert client.get(f"/temporders/{mine['id']}", headers=sales).status_code == 200
    assert client.get(f"/temporders/{theirs['id']}", headers=sales).status_code == 403
    assert client.get("/temporders/all", headers=sales).status_code == 403
    summary = client.get("/temporders/dispatch-summary?status=all", headers=sales)
    assert summary.status_code == 200 and summary.json()["is_manager"] is False

    assert client.put(f"/temporders/{theirs['id']}", json=world["body"], headers=sales).status_code == 403
    assert client.put(f"/temporders/{mine['id']}", json=world["body"], headers=sales).status_code == 200
    world["age"](mine["id"], 45)
    late = client.put(f"/temporders/{mine['id']}", json=world["body"], headers=sales)
    assert late.status_code == 400 and "30-minute" in late.json()["detail"]


@pytest.mark.parametrize("dispatcher", ["store", "owner"])
def test_order_dispatch_sees_edits_and_dispatches_everyones_orders(world, dispatcher):
    """A role given Order dispatch, and an Admin (who has it without being given it)."""
    client, token = world["client"], world["tokens"][dispatcher]
    order = world["place"]("vishal")
    world["age"](order["id"], 45)
    item_id = order["items"][0]["id"]

    assert client.get(f"/temporders/{order['id']}", headers=token).status_code == 200
    assert client.get("/temporders/all", headers=token).status_code == 200
    assert client.get("/temporders/dispatch-summary?status=all", headers=token).json()["is_manager"] is True
    assert client.put(f"/temporders/{order['id']}", json=world["body"], headers=token).status_code == 200

    sent = client.put(f"/temporders/{order['id']}/items/{item_id}/dispatch", json={"is_sent": True}, headers=token)
    assert sent.status_code == 200, sent.text
    assert world["status_of"](order["id"]) == "done"
    assert client.put(f"/temporders/{order['id']}/status", json={"status": "pending"}, headers=token).status_code == 200


def test_customer_page_lists_only_the_salespersons_own_orders(world, harness):
    """The customer profile's recent orders follow the same rule: own orders, unless Order dispatch."""
    from app.routers import customers
    customers_mod = harness.add(P.Module(code="customers", name="Customers"))
    for role_id in {r for (r,) in harness.query(select(P.User.role_id).where(P.User.username.in_(["vishal", "store"])))}:
        harness.add(P.Permission(role_id=role_id, module_id=customers_mod.module_id, can_read=True))
    mine, theirs = world["place"]("vishal"), world["place"]("ravi")
    client = harness.app(auth.router, orders.router, customers.router)
    ledger_id = world["body"]["ledger_id"]

    def recent_ids(name):
        res = client.get(f"/customers/ledger_{ledger_id}", headers=bearer(login(client, f"{name}@example.com")))
        assert res.status_code == 200, res.text
        return {o["id"] for o in res.json()["recent_orders"]}

    assert recent_ids("vishal") == {mine["id"]}
    assert recent_ids("store") == {mine["id"], theirs["id"]}
