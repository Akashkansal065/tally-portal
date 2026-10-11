"""Replacing a stock group's aliases, and putting them back when Tally refuses the change. The old aliases are
removed in one DELETE; on SQLite the new ones get the same ids, which must not collide with the old objects still
held by the session (pytest.ini turns that SAWarning into an error)."""
import pytest
from sqlalchemy import select

import app.models.tally_core as T
from app.routers import auth, inventory, sync
from tests.conftest import bearer, login


@pytest.fixture
def world(harness):
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    group = harness.add(T.MstStockGroup(company_id=company.company_id, name="Biscuits"))
    harness.add(T.StockGroupAlias(stock_group_id=group.stock_group_id, alias="BIS"),
                T.StockGroupAlias(stock_group_id=group.stock_group_id, alias="Cookies"))
    client = harness.app(auth.router, inventory.router)
    return dict(harness=harness, client=client, headers=bearer(login(client, admin.email)), group=group)


def aliases(world):
    return sorted(a for (a,) in world["harness"].query(
        select(T.StockGroupAlias.alias).where(T.StockGroupAlias.stock_group_id == world["group"].stock_group_id)))


def test_aliases_can_be_replaced_again_and_again(world):
    c, url = world["client"], f"/inventory/groups/{world['group'].stock_group_id}"
    for wanted in (["Rusk", "Toast"], ["Wafers"], ["Rusk", "Toast", "Wafers"]):
        response = c.put(url, headers=world["headers"], json={"name": "Biscuits", "aliases": wanted})
        assert response.status_code == 200, response.text
        returned = sorted(a["alias"] if isinstance(a, dict) else a for a in response.json()["aliases"])
        assert returned == wanted == aliases(world)


def test_aliases_are_put_back_when_tally_refuses_the_change(world, monkeypatch):
    async def refused(group_id, sync_id, action, db):
        return False, "REJECTED", "Group 'Biscuits' does not exist"
    monkeypatch.setattr(sync, "try_push_stock_group_realtime", refused)

    response = world["client"].put(f"/inventory/groups/{world['group'].stock_group_id}", headers=world["headers"],
                                   json={"name": "Biscuits & Rusk", "aliases": ["Rusk"]})

    assert response.status_code == 400 and "did not accept" in response.json()["detail"]
    assert aliases(world) == ["BIS", "Cookies"]
