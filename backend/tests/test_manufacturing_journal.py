"""A manufacturing journal consumes BOM components and produces the finished item."""
from decimal import Decimal

from sqlalchemy import select

from app.models.tally_core import (
    MstStockItem, MstUom, MstVoucherType, StockItemBOM, StockItemBOMComponent, TrnInventory, TrnVoucher,
)
from app.routers import auth, inventory
from tests.conftest import bearer, login


def test_manufacturing_journal_is_created_from_bom(harness):
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    pcs = harness.add(MstUom(company_id=company.company_id, name="Pieces", symbol="PCS"))
    flour = harness.add(MstStockItem(company_id=company.company_id, name="Flour", unit_id=pcs.unit_id,
                                     standard_cost_price=Decimal("5.00")))
    bread = harness.add(MstStockItem(company_id=company.company_id, name="Bread", unit_id=pcs.unit_id))
    bom = harness.add(StockItemBOM(stock_item_id=bread.stock_item_id, bom_name="Standard", unit_of_manufacture=Decimal("1")))
    harness.add(StockItemBOMComponent(bom_id=bom.bom_id, component_item_id=flour.stock_item_id, quantity=Decimal("2")))
    harness.add(MstVoucherType(company_id=company.company_id, name="Stock Journal", parent_type="Stock Journal"))
    client = harness.app(auth.router, inventory.router)

    reply = client.post("/inventory/manufacturing-journal", headers=bearer(login(client, admin.email)), json={
        "stock_item_id": bread.stock_item_id,
        "bom_id": bom.bom_id,
        "quantity_to_produce": 3,
        "voucher_date": "2026-10-01",
    })

    assert reply.status_code == 200, reply.text
    body = reply.json()
    # 3 loaves x 2 flour each x 5.00
    assert body["total_cost"] == 30.0
    assert body["unit_cost"] == 10.0
    assert body["components_consumed"][0]["quantity"] == 6.0
    assert harness.scalar(select(TrnVoucher.total_amount).where(TrnVoucher.voucher_id == body["voucher_id"])) == Decimal("30.00")
    flows = {row[0]: row[1] for row in harness.query(
        select(TrnInventory.flow_type, TrnInventory.quantity).where(TrnInventory.voucher_id == body["voucher_id"]))}
    assert flows == {"source": Decimal("6.000"), "destination": Decimal("3.000")}
