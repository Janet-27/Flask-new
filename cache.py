# cache.py
import os
import time
import pickle

# Try to import redis; if it's not installed this file will still work using the in-memory fallback.
try:
    import redis
except Exception:
    redis = None

# Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", str(60 * 60)))  # default 1 hour

# Local in-memory fallback cache: { key: (expiry_ts, value) }
_local_cache = {}

_redis_client = None
_redis_available = False

if redis is not None:
    try:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            socket_connect_timeout=2,  # short timeout so app doesn't hang
            socket_timeout=2
        )
        # Test connection
        _redis_client.ping()
        _redis_available = True
        # print("Redis connected")
    except Exception:
        _redis_client = None
        _redis_available = False
        # print("Redis not available, using in-memory cache")


def cache_data(key: str, data, ttl_seconds: int = None):
    """Store Python object in cache. Uses Redis if available; otherwise uses in-memory cache."""
    ttl = ttl_seconds if ttl_seconds is not None else CACHE_TTL_SECONDS
    try:
        if _redis_available and _redis_client is not None:
            # store pickled value
            _redis_client.set(key, pickle.dumps(data), ex=ttl)
            return True
        else:
            expiry = time.time() + ttl if ttl > 0 else None
            _local_cache[key] = (expiry, data)
            return True
    except Exception as e:
        # fallback to local cache if Redis set fails
        expiry = time.time() + ttl if ttl > 0 else None
        _local_cache[key] = (expiry, data)
        return True


def get_cached_data(key: str):
    """Retrieve Python object from cache. Returns None if not found or expired."""
    try:
        if _redis_available and _redis_client is not None:
            raw = _redis_client.get(key)
            if raw is None:
                return None
            try:
                return pickle.loads(raw)
            except Exception:
                # if unpickle fails, return raw decoded if possible
                try:
                    return raw.decode()
                except Exception:
                    return raw
        else:
            item = _local_cache.get(key)
            if not item:
                return None
            expiry, value = item
            if expiry is not None and time.time() > expiry:
                # expired
                _local_cache.pop(key, None)
                return None
            return value
    except Exception:
        # On any unexpected error, return None so caller continues gracefully
        return None

