import pytest
import time


def test_redis_connection(redis_adapter):
    assert redis_adapter._redis.ping()


def test_acquire_release_lock(redis_adapter):
    test_id = f"test_{time.time()}"
    assert redis_adapter.acquire(test_id, ["res1"], ["group1"], 5)
    assert redis_adapter._redis.exists(f"pytest_xdist_lock:{test_id}")
    redis_adapter.release(test_id)
    assert not redis_adapter._redis.exists(f"pytest_xdist_lock:{test_id}")

def test_lock_conflict(redis_adapter):
    test_id1 = f"test1_{time.time()}"
    test_id2 = f"test2_{time.time()}"

    # First worker acquires lock
    assert redis_adapter.acquire(test_id1, [], ["shared_resource"], 5)

    # Second worker should fail
    start = time.time()
    assert not redis_adapter.acquire(test_id2, [], ["shared_resource"], 1)
    assert time.time() - start >= 1  # Should wait full timeout

    # After release, second can acquire
    redis_adapter.release(test_id1)
    assert redis_adapter.acquire(test_id2, [], ["shared_resource"], 1)
    redis_adapter.release(test_id2)

@pytest.mark.parametrize("worker_id", [1, 2])
def test_parallel_execution(redis_adapter, worker_id):
    lock_key = f"parallel_{worker_id}"
    assert redis_adapter.acquire(lock_key, [], [], 5)
    time.sleep(0.5)  # Simulate work
    redis_adapter.release(lock_key)