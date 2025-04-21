import logging
import time
import json
from typing import Dict, List, Set
import redis
from pytest_xdist_lock.locks.base_lock import BaseLock


class RedisLockAdapter(BaseLock):
    """Redis-based lock implementation with guaranteed reliability."""

    def __init__(self, redis_url: str) -> None:
        """
        Initialize Redis-based locking system.

        :param redis_url: Redis connection URL
        """
        self._redis = redis.Redis.from_url(
            redis_url,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            decode_responses=True
        )
        self._lock_prefix = "pytest_xdist_lock:"
        self._owned_keys: Set[str] = set()

        # Test connection
        try:
            if not self._redis.ping():
                raise ConnectionError("Could not connect to Redis")
        except redis.ConnectionError as e:
            logging.error(f"Redis connection failed: {e}")
            raise

    def _get_lock_key(self, test_id: str) -> str:
        """Get full Redis key for a test lock."""
        return f"{self._lock_prefix}{test_id}"

    def _get_resource_key(self, resource: str) -> str:
        """Get Redis key for a resource."""
        return f"{self._lock_prefix}resource:{resource}"

    def acquire(self, test_id: str, tests: List[str], groups: List[str], timeout: float, check_interval: float = 1) -> bool:
        """
        Acquire lock for given key.
        """
        lock_key = self._get_lock_key(test_id)
        all_resources = tests + groups
        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                # Check for existing locks on required resources
                resource_keys = [self._get_resource_key(r) for r in all_resources]
                if not resource_keys:
                    if self._redis.set(self._get_lock_key(test_id), json.dumps({"tests": [], "groups": []}),
                                       px=int(timeout * 1000 * 1.1)):
                        self._owned_keys.add(test_id)
                        logging.debug(f"Test [{test_id}] - Acquired without resources.")
                        return True
                    else:
                        return False
                existing_locks = self._redis.mget(resource_keys)

                if any(lock is not None for lock in existing_locks):
                    time.sleep(check_interval)
                    continue

                # Try to acquire all resource locks atomically
                with self._redis.pipeline() as pipe:
                    try:
                        pipe.watch(*resource_keys)

                        # Double check if resources are still available
                        if any(pipe.exists(key) for key in resource_keys):
                            pipe.unwatch()
                            time.sleep(check_interval)
                            continue

                        # Set all resource locks and main lock
                        pipe.multi()
                        for resource in all_resources:
                            pipe.set(
                                self._get_resource_key(resource),
                                test_id,
                                px=int(timeout * 1000 * 1.1)  # Slightly longer than timeout
                            )
                        pipe.set(
                            lock_key,
                            json.dumps({"tests": tests, "groups": groups}),
                            px=int(timeout * 1000 * 1.1)
                        )
                        pipe.execute()

                        self._owned_keys.add(test_id)
                        logging.debug(f"Test [{test_id}] - Acquired. Blocking tests: {tests} and groups: {groups}")
                        return True

                    except redis.WatchError:
                        # Resources were modified - retry
                        continue
                    except redis.RedisError as e:
                        logging.error(f"Redis error during acquire: {e}")
                        return False

            except redis.RedisError as e:
                logging.error(f"Redis operation failed: {e}")
                time.sleep(check_interval)

        return False

    def release(self, test_id: str) -> None:
        """Release lock with guaranteed cleanup."""
        if test_id not in self._owned_keys:
            return

        lock_key = self._get_lock_key(test_id)

        try:
            # Get resources this test locked
            lock_data: str = self._redis.get(lock_key)
            if lock_data:
                try:
                    data = json.loads(lock_data)
                    resources = data.get("tests", []) + data.get("groups", [])
                    # Release resource locks
                    self._redis.delete(*[self._get_resource_key(r) for r in resources])
                except json.JSONDecodeError:
                    pass

            # Release main lock
            self._redis.delete(lock_key)
            self._owned_keys.discard(test_id)
            logging.debug(f"Test[{test_id}] - Lock released")

        except redis.RedisError as e:
            logging.error(f"Redis error during release: {e}")
            # Lock will auto-expire

    def _release_all_locks(self) -> None:
        """Clean up all locks owned by this instance."""
        for test_id in list(self._owned_keys):
            self.release(test_id)

    def __del__(self):
        """Destructor to ensure cleanup."""
        self._release_all_locks()