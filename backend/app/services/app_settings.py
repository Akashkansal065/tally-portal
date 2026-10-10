"""A business's own settings (stored in app_settings), with their defaults and allowed ranges. Each account has
its own values: one customer changing its credit days changes nothing for another. The sales target is kept per
company, because companies never share a view."""
import json
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portal_core import AppSetting, Company

# key -> (default, minimum, maximum)
SETTINGS: Dict[str, tuple] = {
    # Net sales before GST that one company aims for each month
    "monthly_sales_target": (2_000_000, 0, 10_000_000_000),
    # Credit days for customers without their own (see customer_credit_terms)
    "default_credit_days": (30, 0, 365),
}


def _clean(key: str, value: Any) -> Any:
    default, low, high = SETTINGS[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{key} must be a number")
    if value < low or value > high:
        raise ValueError(f"{key} must be between {low} and {high}")
    return type(default)(value)


# Settings each company has its own value of. A company that has never set one uses its account's value (what
# the business had before the setting became per company), then the default.
PER_COMPANY = {"monthly_sales_target"}


def stored_key(key: str, account_id: Optional[int]) -> str:
    """Where an account's value of a setting is kept. Without an account (data from before accounts) it is the
    bare key, as it always was."""
    return key if account_id is None else f"a{account_id}:{key}"


def company_key(key: str, company_id: int) -> str:
    """Where one company's value of a per-company setting is kept."""
    return f"c{company_id}:{key}"


async def account_of_company(db: AsyncSession, company_id: int) -> Optional[int]:
    return (await db.execute(select(Company.account_id).where(Company.company_id == company_id))).scalar()


async def get_settings(db: AsyncSession, account_id: Optional[int] = None, company_id: Optional[int] = None) -> Dict[str, Any]:
    """Every known setting for the account, using the default where none is stored. With a company, its own
    value of a per-company setting comes first."""
    keys = {stored_key(key, account_id): key for key in SETTINGS}
    own = {company_key(key, company_id): key for key in PER_COMPANY} if company_id is not None else {}
    rows = (await db.execute(select(AppSetting.key, AppSetting.value).where(AppSetting.key.in_(list(keys) + list(own))))).all()
    stored = {keys[key]: value for key, value in rows if key in keys}
    stored.update({own[key]: value for key, value in rows if key in own})
    result = {}
    for key, (default, _, _) in SETTINGS.items():
        try:
            result[key] = _clean(key, json.loads(stored[key])) if key in stored else default
        except (ValueError, TypeError):
            result[key] = default
    return result


async def get_setting(db: AsyncSession, key: str, account_id: Optional[int] = None, company_id: Optional[int] = None) -> Any:
    return (await get_settings(db, account_id, company_id))[key]


async def set_setting(db: AsyncSession, key: str, value: Any, user_id: Optional[int], account_id: Optional[int] = None,
                      company_id: Optional[int] = None) -> Any:
    """Validate and store one setting (the caller commits): for the company when the setting is per company and
    one is given, else for the account. Raises KeyError/ValueError for bad input."""
    if key not in SETTINGS:
        raise KeyError(key)
    value = _clean(key, value)
    where = company_key(key, company_id) if key in PER_COMPANY and company_id is not None else stored_key(key, account_id)
    row = (await db.execute(select(AppSetting).where(AppSetting.key == where))).scalars().first()
    if row:
        row.value = json.dumps(value)
        row.updated_by_user_id = user_id
    else:
        db.add(AppSetting(key=where, value=json.dumps(value), updated_by_user_id=user_id))
    return value
