"""Which city each customer belongs to, for the city and territory reports.

Order: the city on the customer's MyTally profile, else the city for their Tally pincode (an admin's choice in
pincode_cities, else the proposal below), else none ("City not set"). Proposals cover the pincodes in use when
the reporting review was done (October 2026); admins correct or add pincodes on the Cities screen.
"""
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portal_core import CustomerProfile, PincodeCity

PROPOSED_CITIES: Dict[str, str] = {
    "250001": "Meerut", "250002": "Meerut", "250004": "Meerut", "250103": "Meerut",
    "250104": "Meerut", "250110": "Modipuram", "250502": "Meerut",
    "250401": "Mawana", "250404": "Hastinapur", "250342": "Sardhana",
    "250611": "Baraut", "250601": "Baghpat",
    "245101": "Hapur",
    "247776": "Shamli", "247554": "Deoband", "247001": "Saharanpur",
    "251001": "Muzaffarnagar", "251002": "Muzaffarnagar", "251314": "Muzaffarnagar",
    "201204": "Modinagar", "201206": "Muradnagar",
    "248198": "Vikasnagar", "249201": "Rishikesh",
}

NOT_SET = "City not set"


def clean_pincode(value: Optional[str]) -> Optional[str]:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    return digits[:6] if len(digits) >= 6 else None


def normalise_city(value: Optional[str]) -> Optional[str]:
    text = " ".join((value or "").split())
    return text.title() if text else None


async def pincode_cities(db: AsyncSession) -> Dict[str, Tuple[str, str]]:
    """pincode -> (city, 'set' | 'proposed')."""
    result = {pin: (city, "proposed") for pin, city in PROPOSED_CITIES.items()}
    rows = await db.execute(select(PincodeCity.pincode, PincodeCity.city))
    for pin, city in rows.all():
        result[pin] = (city, "set")
    return result


async def cities_for_ledgers(
    db: AsyncSession, company_id: int, ledgers: Iterable[Tuple[int, Optional[str]]]
) -> Dict[int, Tuple[str, str]]:
    """ledger_id -> (city, source) for (ledger_id, pincode) pairs. Source: 'profile', 'pincode' or 'none'."""
    ledgers = list(ledgers)
    if not ledgers:
        return {}
    profile_rows = await db.execute(
        select(CustomerProfile.ledger_id, CustomerProfile.city)
        .where(CustomerProfile.company_id == company_id, CustomerProfile.ledger_id.in_([lid for lid, _ in ledgers]))
    )
    from_profile = {lid: normalise_city(city) for lid, city in profile_rows.all() if normalise_city(city)}
    by_pincode = await pincode_cities(db)
    result = {}
    for ledger_id, pincode in ledgers:
        if ledger_id in from_profile:
            result[ledger_id] = (from_profile[ledger_id], "profile")
        elif clean_pincode(pincode) in by_pincode:
            result[ledger_id] = (by_pincode[clean_pincode(pincode)][0], "pincode")
        else:
            result[ledger_id] = (NOT_SET, "none")
    return result
