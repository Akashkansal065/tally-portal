"""Each company has its own currencies: the same code in two companies, neither able to see or change the
other's. And the one-time move that hands the old server-wide list out to the companies."""
from datetime import date

import pytest
from sqlalchemy import delete, select, update

import app.models.portal_core as P
import app.models.tally_core as T
from app.routers import auth, currency_tds
from app.services.currency_ownership import ensure_currencies_per_company
from tests.conftest import bearer, login, run

USD = {"code": "XTS", "symbol": "$", "formal_name": "US Dollar", "decimal_places": 2,
       "rates": [{"rate_date": "2026-04-01", "standard_rate": 83.5}]}


@pytest.fixture(autouse=True)
def no_tally(monkeypatch):
    async def nothing(*args, **kwargs):
        return None
    monkeypatch.setattr(currency_tds, "try_push_currency_realtime", nothing)


@pytest.fixture
def two(harness):
    client = harness.app(auth.router, currency_tds.router)
    role = harness.role("Admin")
    sides = []
    for name in ("Alpha", "Beta"):
        company = harness.company(name)
        user = harness.user(company, role, f"owner{name.lower()}")
        sides.append((company, bearer(login(client, user.email))))
    return client, sides[0], sides[1]


def codes(client, headers):
    return {c["code"]: c for c in client.get("/currency", headers=headers).json()}


def test_two_companies_hold_the_same_code_separately(harness, two):
    client, (alpha, a), (beta, b) = two
    mine = client.post("/currency", json=USD, headers=a)
    assert mine.status_code == 200, mine.text
    assert "XTS" not in codes(client, b)                                 # the other company's list is its own

    theirs = client.post("/currency", json={**USD, "symbol": "US$", "rates": []}, headers=b)
    assert theirs.status_code == 200, theirs.text                        # same code, no clash
    assert client.post("/currency", json=USD, headers=a).status_code == 400   # but once per company

    renamed = client.put(f"/currency/{mine.json()['currency_id']}", json={**USD, "formal_name": "Dollar"}, headers=a)
    assert renamed.status_code == 200, renamed.text
    assert codes(client, a)["XTS"]["formal_name"] == "Dollar"
    assert codes(client, b)["XTS"]["formal_name"] == "US Dollar"
    assert codes(client, b)["XTS"]["symbol"] == "US$"
    assert [float(r["standard_rate"]) for r in codes(client, a)["XTS"]["rates"]] == [83.5]
    assert codes(client, b)["XTS"]["rates"] == []


def test_another_companys_currency_cannot_be_changed_or_deleted(harness, two):
    client, (alpha, a), (beta, b) = two
    currency_id = client.post("/currency", json=USD, headers=a).json()["currency_id"]

    assert client.put(f"/currency/{currency_id}", json={**USD, "formal_name": "Taken"}, headers=b).status_code == 404
    assert client.delete(f"/currency/{currency_id}", headers=b).status_code == 404
    assert codes(client, a)["XTS"]["formal_name"] == "US Dollar"
    assert harness.scalar(select(P.SyncQueue.sync_id).where(P.SyncQueue.company_id == beta.company_id)) is None

    assert client.delete(f"/currency/{currency_id}", headers=a).status_code == 200
    assert "XTS" not in codes(client, a)
    assert harness.query(select(P.ExchangeRate.rate_id)) == []


def test_a_new_company_starts_with_the_world_currencies(harness, two):
    client, (alpha, a), (beta, b) = two
    world = {c["code"] for c in client.get("/currency/iso", headers=a).json()}
    assert {"INR", "USD", "EUR"} <= world
    assert set(codes(client, a)) == world and set(codes(client, b)) == world
    assert codes(client, a)["USD"]["currency_id"] != codes(client, b)["USD"]["currency_id"]   # a copy each

    assert client.post("/currency/seed", headers=a).json()["inserted"] == 0   # nothing to add; repeat-safe
    assert client.delete(f"/currency/{codes(client, a)['OMR']['currency_id']}", headers=a).status_code == 200
    assert "OMR" not in codes(client, a) and "OMR" in codes(client, b)
    assert client.post("/currency/seed", headers=a).json()["inserted"] == 1   # puts back what is missing


def companies_from_before(harness, *names):
    """Companies as they were when currencies were one shared list: with none of their own."""
    made = [harness.company(name) for name in names]
    harness.execute(delete(P.Currency))
    return made


def hand_out(harness):
    async def go():
        async with harness.engine.begin() as conn:
            return await ensure_currencies_per_company(conn)
    return run(go())


def test_the_old_shared_list_is_handed_to_every_company(harness):
    alpha, beta = companies_from_before(harness, "Alpha", "Beta")
    usd, eur = harness.add(P.Currency(code="USD", symbol="$", formal_name="US Dollar"),
                           P.Currency(code="EUR", symbol="E", formal_name="Euro"))
    for company in (alpha, beta):
        harness.add(P.ExchangeRate(company_id=company.company_id, currency_id=usd.currency_id,
                                   rate_date=date(2026, 4, 1), standard_rate=80 + company.company_id))
        harness.add(T.MstLedger(company_id=company.company_id, name=f"Buyer {company.name}", group_id=1,
                                currency_id=usd.currency_id))
        voucher = harness.add(T.TrnVoucher(company_id=company.company_id, voucher_type_id=1, voucher_number="1",
                                           voucher_date=date(2026, 4, 2), created_by=1))
        harness.add(T.TrnAccounting(voucher_id=voucher.voucher_id, ledger_id=1, forex_currency_id=usd.currency_id))

    assert hand_out(harness) == 2
    assert hand_out(harness) == 0                                       # nothing left to do the second time

    owned = {(c, code): i for i, c, code in harness.query(
        select(P.Currency.currency_id, P.Currency.company_id, P.Currency.code))}
    assert set(owned) == {(alpha.company_id, "USD"), (alpha.company_id, "EUR"),
                          (beta.company_id, "USD"), (beta.company_id, "EUR")}
    assert owned[(alpha.company_id, "USD")] == usd.currency_id           # the first company keeps the original
    for company in (alpha, beta):
        own_usd = owned[(company.company_id, "USD")]
        assert harness.query(select(P.ExchangeRate.currency_id, P.ExchangeRate.standard_rate).where(
            P.ExchangeRate.company_id == company.company_id)) == [(own_usd, 80 + company.company_id)]
        assert harness.scalar(select(T.MstLedger.currency_id).where(
            T.MstLedger.company_id == company.company_id)) == own_usd
        assert harness.scalar(select(T.TrnAccounting.forex_currency_id).join(
            T.TrnVoucher, T.TrnVoucher.voucher_id == T.TrnAccounting.voucher_id).where(
            T.TrnVoucher.company_id == company.company_id)) == own_usd


def test_an_interrupted_hand_out_finishes_without_second_copies(harness):
    alpha, beta = companies_from_before(harness, "Alpha", "Beta")
    usd = harness.add(P.Currency(code="USD", symbol="$"))
    assert hand_out(harness) == 1
    # As if it stopped after copying to Beta but before marking the original as Alpha's
    harness.execute(update(P.Currency).where(P.Currency.currency_id == usd.currency_id).values(company_id=None))

    assert hand_out(harness) == 1
    assert sorted(c for (c,) in harness.query(select(P.Currency.company_id))) == [alpha.company_id, beta.company_id]


def test_a_company_that_already_has_the_code_keeps_its_own(harness):
    alpha, beta = harness.company("Alpha"), harness.company("Beta")      # each starts with its own USD
    shared = harness.add(P.Currency(code="USD", symbol="old"))
    for company in (alpha, beta):
        harness.add(P.ExchangeRate(company_id=company.company_id, currency_id=shared.currency_id,
                                   rate_date=date(2026, 4, 1), standard_rate=83))

    assert hand_out(harness) == 1

    usd = dict(harness.query(select(P.Currency.company_id, P.Currency.currency_id).where(P.Currency.code == "USD")))
    assert set(usd) == {alpha.company_id, beta.company_id} and shared.currency_id not in usd.values()
    assert dict(harness.query(select(P.ExchangeRate.company_id, P.ExchangeRate.currency_id))) == usd


def test_a_server_with_no_company_yet_keeps_the_list_for_later(harness):
    harness.add(P.Currency(code="XTS", symbol="$"))
    assert hand_out(harness) == 0
    company = harness.company("Alpha")
    assert hand_out(harness) == 1
    assert harness.scalar(select(P.Currency.company_id).where(P.Currency.code == "XTS")) == company.company_id
