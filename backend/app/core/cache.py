import time
import threading
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("uvicorn.error")
# Hits, misses and stores log at DEBUG (they happen on most requests); clears that evict something log at INFO

# Structure: { (company_id, cache_key): (data, expiry_timestamp) }
_in_memory_cache: Dict[Tuple[int, str], Tuple[Any, float]] = {}
_cache_lock = threading.Lock()

# Default TTL: 2 hours in seconds (7200 seconds)
DEFAULT_CACHE_TTL = 2 * 60 * 60

def get_cached_response(company_id: int, cache_key: str) -> Optional[Any]:
    """Retrieve cached data if valid and not expired, logging hits and misses."""
    now = time.time()
    key = (company_id, cache_key)
    with _cache_lock:
        if key in _in_memory_cache:
            data, expiry = _in_memory_cache[key]
            if now < expiry:
                remaining_sec = int(expiry - now)
                logger.debug(f"⚡ [CACHE HIT] Company #{company_id} | Key: '{cache_key}' (Serving from in-memory cache, expires in {remaining_sec // 60}m {remaining_sec % 60}s)")
                return data
            else:
                # Expired -> Evict key
                logger.debug(f"⌛ [CACHE EXPIRED] Company #{company_id} | Key: '{cache_key}' (Expired, evicting entry)")
                del _in_memory_cache[key]
        else:
            logger.debug(f"🔍 [CACHE MISS] Company #{company_id} | Key: '{cache_key}' (Fetching fresh data from Database)")
    return None

def set_cached_response(company_id: int, cache_key: str, data: Any, ttl_seconds: int = DEFAULT_CACHE_TTL):
    """Store data in memory with a given TTL (default: 2 hours) and log the operation."""
    expiry = time.time() + ttl_seconds
    key = (company_id, cache_key)
    with _cache_lock:
        _in_memory_cache[key] = (data, expiry)
        ttl_display = f"{ttl_seconds // 3600}h" if ttl_seconds >= 3600 else f"{ttl_seconds // 60}m"
        logger.debug(f"💾 [CACHE STORE] Company #{company_id} | Key: '{cache_key}' (Stored in memory with {ttl_display} TTL)")

def clear_company_cache(company_id: int, key_prefix: Optional[str] = None) -> int:
    """
    Clear cached entries for a specific company. Returns count of evicted entries.
    If key_prefix is provided, only evicts entries whose cache_key starts with that prefix.
    """
    with _cache_lock:
        keys_to_del = [
            k for k in _in_memory_cache.keys()
            if k[0] == company_id and (key_prefix is None or k[1].startswith(key_prefix))
        ]
        for k in keys_to_del:
            del _in_memory_cache[k]
        evicted_count = len(keys_to_del)
        if evicted_count:
            prefix_info = f" with prefix '{key_prefix}'" if key_prefix else ""
            logger.info(f"🧹 [CACHE CLEAR] Company #{company_id}{prefix_info} | Evicted {evicted_count} cached entries")
        return evicted_count

def clear_cache_prefix(key_prefix: str) -> int:
    """Clear entries whose cache_key starts with key_prefix, for every company. Returns count of evicted entries."""
    with _cache_lock:
        keys_to_del = [k for k in _in_memory_cache.keys() if k[1].startswith(key_prefix)]
        for k in keys_to_del:
            del _in_memory_cache[k]
    if keys_to_del:
        logger.info(f"🧹 [CACHE CLEAR] All companies with prefix '{key_prefix}' | Evicted {len(keys_to_del)} cached entries")
    return len(keys_to_del)

def clear_all_cache() -> int:
    """Clear the entire in-memory cache across all companies. Returns count of evicted entries."""
    with _cache_lock:
        count = len(_in_memory_cache)
        _in_memory_cache.clear()
        logger.info(f"🧹 [CACHE CLEAR ALL] Evicted all {count} cached entries across all companies")
        return count

def get_cache_stats() -> dict:
    """Return current cache statistics."""
    now = time.time()
    with _cache_lock:
        active_keys = 0
        expired_keys = 0
        for _, (_, expiry) in _in_memory_cache.items():
            if now < expiry:
                active_keys += 1
            else:
                expired_keys += 1
        return {
            "total_entries": len(_in_memory_cache),
            "active_entries": active_keys,
            "expired_entries": expired_keys,
            "default_ttl_seconds": DEFAULT_CACHE_TTL
        }
