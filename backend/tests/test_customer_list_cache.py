"""GET /customers: one cached list per company, per-request filters and distance, cleared by writes."""
from datetime import datetime

import pytest
from sqlalchemy import update

import app.models.portal_core as P
from app.models.tally_core import MstGroup, MstLedger
from app.routers import auth, customers
from tests.conftest import bearer, login

SHOP = (28.6315, 77.2167)


@pytest.fixture
def shop(harness):
    company = harness.company()
    admin = harness.user(company, harness.role("Admin"), "owner")
    debtors = harness.add(MstGroup(company_id=company.company_id, name="Sundry Debtors", nature="Asset"))
    expenses = harness.add(MstGroup(company_id=company.company_id, name="Indirect Expenses", nature="Expense"))
    amar = harness.add(MstLedger(company_id=company.company_id, name="Amar Enterprises", group_id=debtors.group_id))
    harness.add(MstLedger(company_id=company.company_id, name="Zenith Traders", group_id=debtors.group_id))
    harness.add(MstLedger(company_id=company.company_id, name="Electricity", group_id=expenses.group_id))
    amar_profile = harness.add(P.CustomerProfile(company_id=company.company_id, ledger_id=amar.ledger_id,
                                                 latitude=SHOP[0], longitude=SHOP[1]))
    kirana = harness.add(P.CustomerProfile(company_id=company.company_id, custom_name="Bharat Kirana",
                                           latitude=SHOP[0] + 0.01, longitude=SHOP[1]))

    def log(profile, source, status, when):
        harness.add(P.CustomerLocationLog(company_id=company.company_id, customer_profile_id=profile.id,
                                          user_id=admin.user_id, latitude=SHOP[0], longitude=SHOP[1],
                                          source=source, verification_status=status, created_at=when))
    # Amar: an older on-site check-in, then a newer admin edit. The check-in wins.
    log(amar_profile, "check_in", "VERIFIED_ON_SITE", datetime(2026, 9, 1, 10, 0))
    log(amar_profile, "admin_edit", "UNVERIFIED", datetime(2026, 9, 5, 10, 0))
    # Kirana: only admin edits; the newest one wins
    log(kirana, "admin_edit", "MISMATCH_FAR", datetime(2026, 9, 2, 10, 0))
    log(kirana, "admin_edit", "NEARBY", datetime(2026, 9, 3, 10, 0))

    client = harness.app(auth.router, customers.router)
    headers = bearer(login(client, admin.email))
    return harness, client, headers, company, amar_profile, kirana


def names(reply):
    return [c["name"] for c in reply["customers"]]


def by_name(reply):
    return {c["name"]: c for c in reply["customers"]}


def test_list_has_debtors_and_field_profiles_with_latest_logs(shop):
    _, client, headers, *_ = shop

    reply = client.get("/customers", headers=headers).json()

    assert names(reply) == ["Amar Enterprises", "Bharat Kirana", "Zenith Traders"]
    rows = by_name(reply)
    assert rows["Amar Enterprises"]["latest_verification_status"] == "VERIFIED_ON_SITE"
    assert rows["Amar Enterprises"]["latest_checkin_at"].startswith("2026-09-01")
    assert rows["Bharat Kirana"]["latest_verification_status"] == "NEARBY"
    assert rows["Zenith Traders"]["latest_verification_status"] == "NO_BASE_COORDINATE"
    assert reply["metrics"]["total"] == 3 and reply["metrics"]["tagged"] == 2


def test_filters_sorting_and_distance_reuse_the_cached_list(shop):
    harness, client, headers, *_ = shop
    client.get("/customers", headers=headers)

    with harness.count_queries() as statements:
        nearest = client.get("/customers", headers=headers,
                             params={"sort_by": "nearest", "my_lat": SHOP[0], "my_lon": SHOP[1]}).json()
        searched = client.get("/customers", headers=headers, params={"search": "kirana"}).json()
        reverse = client.get("/customers", headers=headers, params={"sort_by": "name_desc"}).json()
        plain = client.get("/customers", headers=headers).json()
    assert statements == []

    assert names(nearest) == ["Amar Enterprises", "Bharat Kirana", "Zenith Traders"]
    assert by_name(nearest)["Amar Enterprises"]["distance_from_me_meters"] == pytest.approx(0, abs=1)
    assert 1000 < by_name(nearest)["Bharat Kirana"]["distance_from_me_meters"] < 1200
    assert names(searched) == ["Bharat Kirana"]
    assert names(reverse) == ["Zenith Traders", "Bharat Kirana", "Amar Enterprises"]
    # Earlier requests didn't change the cached rows or their order
    assert names(plain) == ["Amar Enterprises", "Bharat Kirana", "Zenith Traders"]
    assert all(c["distance_from_me_meters"] is None for c in plain["customers"])


def test_saved_change_clears_the_cache(shop):
    harness, client, headers, company, *_ = shop
    client.get("/customers", headers=headers)

    harness.add(P.CustomerProfile(company_id=company.company_id, custom_name="Chawla Stores"))
    assert "Chawla Stores" in names(client.get("/customers", headers=headers).json())


def test_bulk_update_clears_the_cache(shop):
    harness, client, headers, company, amar_profile, _ = shop
    client.get("/customers", headers=headers)

    harness.execute(update(P.CustomerProfile).where(P.CustomerProfile.id == amar_profile.id).values(route_name="Route 9"))
    assert by_name(client.get("/customers", headers=headers).json())["Amar Enterprises"]["route_name"] == "Route 9"


def test_adding_an_owner_saves_and_shows_in_the_list(shop):
    _, client, headers, _, _, kirana = shop
    client.get("/customers", headers=headers)

    response = client.post(f"/customers/profile_{kirana.id}/owners", headers=headers,
                           json={"name": "Ramesh Chawla", "phone": "9810000000", "is_primary": True})

    assert response.status_code == 200, response.text
    row = by_name(client.get("/customers", headers=headers).json())["Bharat Kirana"]
    assert row["owners_count"] == 1
    assert row["contact_person"] == "Ramesh Chawla"
