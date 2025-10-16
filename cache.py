import redis
import json
from config import REDIS_URL

try:
    cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    cache.ping()  # Test Redis connection
    print("✅ Redis connected successfully!")
except redis.ConnectionError as e:
    print(f"❌ Redis connection failed: {e}")

def cache_data(key, data, expiry=86400):
    """Caches data in Redis with a 24-hour expiry."""
    try:
        cache.set(key, json.dumps(data))
        cache.expire(key, expiry)
    except Exception as e:
        print(f"❌ Error caching data: {e}")

def get_cached_data(key):
    """Retrieves data from Redis cache."""
    try:
        data = cache.get(key)
        return json.loads(data) if data else None
    except Exception as e:
        print(f"❌ Error retrieving cache data: {e}")
        return None
