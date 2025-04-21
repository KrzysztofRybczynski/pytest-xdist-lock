import pytest
import os
from pytest_xdist_lock.locks.redis_lock import RedisLockAdapter
from pytest_xdist_lock.locks.file_lock import FileLockAdapter


@pytest.fixture
def lock_file(tmp_path):
    file = tmp_path / "test_locks.json"
    file.write_text("{}")
    return str(file)

@pytest.fixture
def file_adapter(lock_file):
    return FileLockAdapter(lock_file)

@pytest.fixture(scope="module")
def redis_adapter():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    adapter = RedisLockAdapter(redis_url)
    yield adapter
    adapter._redis.flushdb()