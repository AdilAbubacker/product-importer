import redis

def clear_redis():
    """
    Clears Redis databases used by Celery (DB 0) and Django cache (DB 1).
    """
    try:
        # Connect to Redis DB 0 (Celery broker)
        r0 = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)
        print("Clearing Celery queue (Redis DB 0)...")
        r0.flushdb()
        print("✓ Cleared Celery queue (Redis DB 0)")
    except redis.exceptions.ConnectionError as e:
        print(f"✗ Could not connect to Redis DB 0: {e}")

    try:
        # Connect to Redis DB 1 (Django cache)
        r1 = redis.StrictRedis(host='localhost', port=6379, db=1, decode_responses=True)
        print("Clearing cache (Redis DB 1)...")
        r1.flushdb()
        print("✓ Cleared cache (Redis DB 1)")
    except redis.exceptions.ConnectionError as e:
        print(f"✗ Could not connect to Redis DB 1: {e}")

    print("\nDone! Redis has been reset.")

if __name__ == "__main__":
    clear_redis()
