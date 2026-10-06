"""Phase 5 reports: cash & bank book, cost centres, stock by godown and batch."""
from datetime import date, timedelta
from decimal import Decimal

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import auth, books
from tests.conftest import bearer, login

TODAY = date(2026, 10, 6)


def test_books(harness, monkeypatch):
    monkeypatch.setattr(books, "get_ist_date", lambda: TODAY)
    h = harness
    alpha = h.company("Alpha")
    owner = h.user(alpha, h.role("Admin"), "owner")
    cid = alpha.company_id
    primary = h.add(T.MstGroup(company_id=cid, name="Primary", nature="Asset"))
    cash_g = h.add(T.MstGroup(company_id=cid, name="Cash-in-Hand", nature="Asset", parent_group_id=primary.group_id))
    bank_g = h.add(T.MstGroup(company_id=cid, name="Bank Accounts", nature="Asset", parent_group_id=primary.group_id))
    cash = h.add(T.MstLedger(company_id=cid, name="Cash", group_id=cash_g.group_id, opening_balance=Decimal("1000"), opening_balance_type="Dr"))
    bank = h.add(T.MstLedger(company_id=cid, name="PNB Current", group_id=bank_g.group_id, opening_balance=Decimal("500"), opening_balance_type="Cr"))
    sales = h.add(T.MstLedger(company_id=cid, name="Sales", group_id=primary.group_id))
    vt = h.add(T.MstVoucherType(company_id=cid, name="Receipt", parent_type="Receipt"))
    unit = h.add(T.MstUom(company_id=cid, name="Pieces", symbol="PCS"))
    item = h.add(T.MstStockItem(company_id=cid, name="Kettle", unit_id=unit.unit_id))
    godown = h.add(T.MstGodown(company_id=cid, name="Back Store"))
    category = h.add(T.MstCostCategory(company_id=cid, name="Primary Cost Category"))
    centre = h.add(T.MstCostCentre(company_id=cid, category_id=category.category_id, name="Meerut Branch"))
    n = [0]

    def voucher(day, entries, cancelled=False):
        n[0] += 1
        v = h.add(T.TrnVoucher(company_id=cid, voucher_type_id=vt.voucher_type_id, voucher_number=str(n[0]), voucher_date=day,
                               total_amount=Decimal("1"), is_cancelled=cancelled, is_optional=False, created_by=owner.user_id))
        rows = [h.add(T.TrnAccounting(voucher_id=v.voucher_id, ledger_id=l.ledger_id, debit_amount=Decimal(str(dr)), credit_amount=Decimal(str(cr))))
                for l, dr, cr in entries]
        return v, rows

    voucher(date(2026, 3, 1), [(cash, 200, 0)])               # before the period: into the opening
    _, rows = voucher(date(2026, 5, 1), [(cash, 300, 0), (sales, 0, 300)])
    h.add(T.TrnCostCentreAllocation(entry_id=rows[1].entry_id, cost_centre_id=centre.cost_centre_id, amount=Decimal("300")))
    voucher(date(2026, 6, 1), [(cash, 0, 50), (bank, 50, 0)])
    voucher(date(2026, 6, 2), [(cash, 999, 0)], cancelled=True)  # never counts
    v, _ = voucher(date(2026, 7, 1), [])
    h.add(T.TrnInventory(voucher_id=v.voucher_id, stock_item_id=item.stock_item_id, godown_id=godown.godown_id, quantity=Decimal(10),
                         rate=Decimal(1), amount=Decimal(10), is_inward=True),
          T.TrnInventory(voucher_id=v.voucher_id, stock_item_id=item.stock_item_id, quantity=Decimal(4), rate=Decimal(1),
                         amount=Decimal(4), is_inward=False))
    h.add(T.Batch(company_id=cid, stock_item_id=item.stock_item_id, batch_number="B-1", expiry_date=TODAY + timedelta(days=30),
                  quantity_received=Decimal(10), quantity_available=Decimal(6)),
          T.Batch(company_id=cid, stock_item_id=item.stock_item_id, batch_number="B-0", quantity_received=Decimal(5), quantity_available=Decimal(0)))

    client = h.app(auth.router, books.router)
    headers = bearer(login(client, "owner@example.com"))

    book = client.get("/reports/cash-bank-book?from=2026-04-01&to=2026-10-06", headers=headers).json()
    by_name = {r["name"]: r for r in book["ledgers"]}
    assert by_name["Cash"] == {**by_name["Cash"], "kind": "Cash", "opening": 1200.0, "money_in": 300.0, "money_out": 50.0, "closing": 1450.0}
    assert by_name["PNB Current"]["opening"] == -500.0 and by_name["PNB Current"]["closing"] == -450.0
    assert book["totals"]["closing"] == 1000.0

    centres = client.get("/reports/cost-centres?from=2026-04-01", headers=headers).json()
    assert centres["rows"] == [{"cost_centre_id": centre.cost_centre_id, "name": "Meerut Branch", "debit": 0.0, "credit": 300.0, "net": -300.0, "vouchers": 1}]

    stock = client.get("/reports/stock-by-godown?from=2026-04-01", headers=headers).json()
    assert {g["godown"]: (g["qty_in"], g["qty_out"]) for g in stock["godowns"]} == {"Back Store": (10.0, 0.0), "Main Location": (0.0, 4.0)}

    batches = client.get("/reports/stock-by-batch", headers=headers).json()["batches"]
    assert [(b["batch"], b["available"], b["days_to_expiry"]) for b in batches] == [("B-1", 6.0, 30)]
    assert client.get("/reports/cash-bank-book?from=2026-10-07&to=2026-10-01", headers=headers).status_code == 422
