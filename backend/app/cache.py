import logging
import os
import json
from typing import Any, Optional

log = logging.getLogger("indra.cache")

_REDIS_URL = os.getenv("REDIS_URL", "")
_redis_client = None
_in_memory_cache = {}

def get_redis():
    global _redis_client
    if not _REDIS_URL:
        return None
        
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.from_url(_REDIS_URL, decode_responses=True)
            _redis_client.ping()
            log.info("Redis connected at %s", _REDIS_URL)
        except Exception as exc:
            log.error("Redis connection failed: %s", exc)
            _redis_client = None
            
    return _redis_client

def set_val(key: str, value: Any, ttl_seconds: int = 3600):
    client = get_redis()
    try:
        val_str = json.dumps(value)
        if client:
            client.setex(key, ttl_seconds, val_str)
        else:
            _in_memory_cache[key] = val_str
    except Exception as exc:
        log.warning("Cache set failed for %s: %s", key, exc)

def get_val(key: str) -> Optional[Any]:
    client = get_redis()
    try:
        val_str = None
        if client:
            val_str = client.get(key)
        else:
            val_str = _in_memory_cache.get(key)
            
        if val_str:
            return json.loads(val_str)
    except Exception as exc:
        log.warning("Cache get failed for %s: %s", key, exc)
        
    return None
