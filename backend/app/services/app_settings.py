"""Business-wide settings (stored in app_settings), with their defaults and allowed ranges."""
import json
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portal_core import AppSetting

# key -> (default, minimum, maximum)
SETTINGS: Dict[str, tuple] = {
    # Net sales before GST, across all companies, that the business aims for each month
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


async def get_settings(db: AsyncSession) -> Dict[str, Any]:
    """Every known setting, using the default where none is stored."""
    rows = (await db.execute(select(AppSetting.key, AppSetting.value).where(AppSetting.key.in_(list(SETTINGS))))).all()
    stored = {key: value for key, value in rows}
    result = {}
    for key, (default, _, _) in SETTINGS.items():
        try:
            result[key] = _clean(key, json.loads(stored[key])) if key in stored else default
        except (ValueError, TypeError):
            result[key] = default
    return result


async def get_setting(db: AsyncSession, key: str) -> Any:
    return (await get_settings(db))[key]


async def set_setting(db: AsyncSession, key: str, value: Any, user_id: Optional[int]) -> Any:
    """Validate and store one setting (the caller commits). Raises KeyError/ValueError for bad input."""
    if key not in SETTINGS:
        raise KeyError(key)
    value = _clean(key, value)
    row = (await db.execute(select(AppSetting).where(AppSetting.key == key))).scalars().first()
    if row:
        row.value = json.dumps(value)
        row.updated_by_user_id = user_id
    else:
        db.add(AppSetting(key=key, value=json.dumps(value), updated_by_user_id=user_id))
    return value
