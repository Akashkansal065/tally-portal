import time
from typing import Dict, Any, Tuple

# Structure: { (company_id, cache_key): (data, expiry_timestamp) }
_in_memory_cache: Dict[Tuple[int, str], Tuple[Any, float]] = {}

CACHE_TTL = 4 * 60 * 60  # 4 hours in seconds

def get_cached_response(company_id: int, cache_key: str) -> Any:
    now = time.time()
    if (company_id, cache_key) in _in_memory_cache:
        data, expiry = _in_memory_cache[(company_id, cache_key)]
        if now < expiry:
            return data
        else:
            # Expired
            del _in_memory_cache[(company_id, cache_key)]
    return None

def set_cached_response(company_id: int, cache_key: str, data: Any):
    expiry = time.time() + CACHE_TTL
    _in_memory_cache[(company_id, cache_key)] = (data, expiry)

def clear_company_cache(company_id: int):
    keys_to_del = [k for k in _in_memory_cache.keys() if k[0] == company_id]
    for k in keys_to_del:
        del _in_memory_cache[k]
