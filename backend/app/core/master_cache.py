"""Per-company cache for master data lists: account and stock groups, units, godowns, cost centres and so on.

These lists back the dropdowns on most screens but only change on a Tally sync or an edit in the portal. Each
cache key below is registered with the tables it is built from, so any ORM write to them clears it after commit
(app/core/cache_invalidation.py), and the Tally sync clears the whole company cache when it finishes. The cache
sits after each endpoint's permission check, so it never widens access.
"""
import hashlib
from typing import Any, Awaitable, Callable, Iterable, List, Optional

from pydantic import TypeAdapter

from app.core.cache import get_cached_response, set_cached_response
from app.core.cache_invalidation import watch
from app.models import portal_core as P
from app.models import tally_core as T

MASTER_DATA_TTL_SECONDS = 30 * 60

ACCOUNT_GROUPS = "master_account_groups"
STOCK_GROUPS = "master_stock_groups"
STOCK_CATEGORIES = "master_stock_categories"
GODOWNS = "master_godowns"
PRICE_LEVELS = "master_price_levels"
UNITS = "master_units"
COST_CATEGORIES = "master_cost_categories"
COST_CENTRES = "master_cost_centres"
COST_CENTRE_CLASSES = "master_cost_centre_classes"
CURRENCIES = "master_currencies"
TDS_SECTIONS = "master_tds_sections"
VOUCHER_TYPES = "master_voucher_types"
# Older cache in routers/vouchers.py (GET /vouchers/types), cleared by the same writes
LEGACY_VOUCHER_TYPES = "voucher_types_"

watch(ACCOUNT_GROUPS, T.MstGroup, T.MstGroupGstDetails)
watch(STOCK_GROUPS, T.MstStockGroup, T.StockGroupAlias)
watch(STOCK_CATEGORIES, T.MstStockCategory)
watch(GODOWNS, T.MstGodown)
watch(PRICE_LEVELS, T.MstPriceLevel)
watch(UNITS, T.MstUom)
watch(COST_CATEGORIES, T.MstCostCategory)
watch(COST_CENTRES, T.MstCostCentre, T.MstCostCategory)
watch(COST_CENTRE_CLASSES, T.MstCostCentreClass, T.MstCostCentreClassAllocation, T.MstCostCategory, T.MstCostCentre)
watch(CURRENCIES, P.Currency, P.ExchangeRate)
watch(TDS_SECTIONS, P.TdsSection)
for _prefix in (VOUCHER_TYPES, LEGACY_VOUCHER_TYPES):
    watch(_prefix, T.MstVoucherType, T.MstVoucherTypePrefix, T.MstVoucherTypeSuffix, T.MstVoucherTypeRestart,
          T.MstVoucherTypeClass, T.MstVoucherTypeClassGroup, P.UserDataScope)


async def cached_master(company_id: int, cache_key: str, load: Callable[[], Awaitable[Any]]) -> Any:
    """The cached list for this company and key, or the result of load() after caching it."""
    cached = get_cached_response(company_id, cache_key)
    if cached is not None:
        return cached
    data = await load()
    set_cached_response(company_id, cache_key, data, ttl_seconds=MASTER_DATA_TTL_SECONDS)
    return data


def as_schema_list(schema: type, rows: Iterable[Any]) -> List[Any]:
    """Convert ORM rows to response models while the session is open, so the cache never holds ORM objects."""
    return TypeAdapter(List[schema]).validate_python(list(rows), from_attributes=True)


def scope_suffix(allowed_ids: Optional[List[int]]) -> str:
    """Cache-key part for a user limited to certain records. Users with the same scope share an entry, and a
    changed scope gets a new key instead of reading the old list."""
    if allowed_ids is None:
        return ""
    digest = hashlib.sha1(",".join(map(str, sorted(allowed_ids))).encode()).hexdigest()[:12]
    return f"_scope_{digest}"
