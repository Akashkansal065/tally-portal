"""Saving a stock item that has a bill of materials replaces the BOM and still returns the item."""
from decimal import Decimal

from sqlalchemy import select

from app.models.tally_core import MstStockItem, MstUom, StockItemBOM, StockItemBOMComponent
from app.routers import auth, inventory
from tests.conftest import bearer, login


def test_update_stock_item_with_a_bom(harness):
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    cid = company.company_id
    unit = harness.add(MstUom(company_id=cid, name="pcs", symbol="pcs"))
    part = harness.add(MstStockItem(company_id=cid, name="Sensor", unit_id=unit.unit_id))
    made = harness.add(MstStockItem(company_id=cid, name="Tracker", unit_id=unit.unit_id))
    bom = harness.add(StockItemBOM(stock_item_id=made.stock_item_id, bom_name="Standard", unit_of_manufacture=Decimal("1")))
    harness.add(StockItemBOMComponent(bom_id=bom.bom_id, component_item_id=part.stock_item_id, quantity=Decimal("2"), component_type="Component"))
    client = harness.app(auth.router, inventory.router)

    reply = client.put(f"/inventory/items/{made.stock_item_id}", headers=bearer(login(client, admin.email)), json={
        "name": "Tracker", "unit_id": unit.unit_id,
        "boms": [{"bom_name": "Standard", "unit_of_manufacture": 1, "is_active": True,
                  "components": [{"component_item_id": part.stock_item_id, "quantity": 3, "component_type": "Component"}]}],
    })

    assert reply.status_code == 200, reply.text
    assert [len(b["components"]) for b in reply.json()["boms"]] == [1]
    assert harness.scalar(select(StockItemBOMComponent.quantity)) == Decimal("3")
