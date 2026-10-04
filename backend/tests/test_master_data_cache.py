"""Master data lists are cached per company and cleared when their tables change."""
import pytest
from sqlalchemy import select

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import auth, currency_tds, inventory, ledgers, masters, voucher_types, vouchers
from tests.conftest import bearer, login

# (endpoint, how to add one more row for the company, field that names a row)
MASTERS = [
    ("/ledgers/groups", lambda cid: T.MstGroup(company_id=cid, name="Branch Divisions", nature="Liability"), "name"),
    ("/inventory/uoms", lambda cid: T.MstUom(company_id=cid, name="Box", symbol="box"), "symbol"),
    ("/inventory/groups", lambda cid: T.MstStockGroup(company_id=cid, name="Biscuits"), "name"),
    ("/inventory/categories", lambda cid: T.MstStockCategory(company_id=cid, name="Premium"), "name"),
    ("/inventory/godowns", lambda cid: T.MstGodown(company_id=cid, name="Okhla Store"), "name"),
    ("/inventory/price-levels", lambda cid: T.MstPriceLevel(company_id=cid, name="Wholesale"), "name"),
    ("/masters/cost-categories", lambda cid: T.MstCostCategory(company_id=cid, name="Projects"), "name"),
    ("/tds/sections", lambda cid: P.TdsSection(company_id=cid, section_code="194C", description="Contractors",
                                               default_rate_percent=1), "section_code"),
]


@pytest.fixture
def books(harness):
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    client = harness.app(auth.router, ledgers.router, inventory.router, masters.router, currency_tds.router,
                         vouchers.router, (voucher_types.router, "/voucher-types"))
    return harness, client, bearer(login(client, admin.email)), company


@pytest.mark.parametrize("endpoint, make_row, name_field", MASTERS, ids=[m[0] for m in MASTERS])
def test_master_list_is_cached_and_cleared_by_a_new_row(books, endpoint, make_row, name_field):
    harness, client, headers, company = books
    first = client.get(endpoint, headers=headers)
    assert first.status_code == 200, first.text

    with harness.count_queries() as statements:
        assert client.get(endpoint, headers=headers).json() == first.json()
    assert statements == []

    row = make_row(company.company_id)
    harness.add(row)
    names = [item[name_field] for item in client.get(endpoint, headers=headers).json()]
    assert getattr(row, name_field) in names


def test_cost_centre_tree_follows_a_renamed_category(books):
    harness, client, headers, company = books
    category = harness.add(T.MstCostCategory(company_id=company.company_id, name="Primary Cost Category"))
    harness.add(T.MstCostCentre(company_id=company.company_id, category_id=category.category_id, name="Delhi Office"))
    tree = client.get("/masters/cost-centres/tree", headers=headers).json()
    assert tree[0]["category_name"] == "Primary Cost Category"

    category.name = "Regions"
    harness.add(category)

    assert client.get("/masters/cost-centres/tree", headers=headers).json()[0]["category_name"] == "Regions"
    assert client.get("/masters/cost-centres", headers=headers).json()[0]["category_name"] == "Regions"


def test_voucher_types_respect_each_users_scope(books):
    harness, client, headers, company = books
    sales = harness.add(T.MstVoucherType(company_id=company.company_id, name="Sales", parent_type="Sales"))
    harness.add(T.MstVoucherType(company_id=company.company_id, name="Receipt", parent_type="Receipt"))
    admin_role = harness.scalar(select(P.Role).where(P.Role.name == "Admin"))
    clerk = harness.user(company, admin_role, "sales.clerk")
    harness.add(P.UserDataScope(user_id=clerk.user_id, scope_type="VoucherType", scope_ref_id=sales.voucher_type_id))
    clerk_headers = bearer(login(client, clerk.email))

    everything = [vt["name"] for vt in client.get("/voucher-types", headers=headers).json()]
    scoped = [vt["name"] for vt in client.get("/voucher-types", headers=clerk_headers).json()]
    searched = [vt["name"] for vt in client.get("/voucher-types", headers=headers, params={"search": "rec"}).json()]

    assert everything == ["Receipt", "Sales"]
    assert scoped == ["Sales"]
    assert searched == ["Receipt"]


def test_new_voucher_type_clears_both_voucher_type_caches(books):
    harness, client, headers, company = books
    harness.add(T.MstVoucherType(company_id=company.company_id, name="Sales", parent_type="Sales"))
    client.get("/voucher-types", headers=headers)
    client.get("/vouchers/types", headers=headers)

    harness.add(T.MstVoucherType(company_id=company.company_id, name="Credit Note", parent_type="Credit Note"))

    assert "Credit Note" in [vt["name"] for vt in client.get("/voucher-types", headers=headers).json()]
    assert "Credit Note" in [vt["name"] for vt in client.get("/vouchers/types", headers=headers).json()]
