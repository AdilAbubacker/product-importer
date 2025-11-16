#!/usr/bin/env python
"""Clear Redis queues for Celery and cache"""
import redis

# Clear Celery queue (Redis DB 0)
print("Clearing Celery queue (Redis DB 0)...")
try:
    celery_redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=False)
    celery_redis.flushdb()
    print("✓ Cleared Celery queue (Redis DB 0)")
except Exception as e:
    print(f"✗ Error clearing Celery queue: {e}")

# Clear cache (Redis DB 1) - optional
print("\nClearing cache (Redis DB 1)...")
try:
    cache_redis = redis.Redis(host='localhost', port=6379, db=1, decode_responses=False)
    cache_redis.flushdb()
    print("✓ Cleared cache (Redis DB 1)")
except Exception as e:
    print(f"✗ Error clearing cache: {e}")

print("\nDone! Redis has been reset.")

