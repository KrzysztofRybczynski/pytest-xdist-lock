import time
import json
from pytest_xdist_lock.locks.file_lock import FileLockAdapter


def test_file_operations(file_adapter, lock_file):
    test_id = f"test_{time.time()}"
    assert file_adapter.acquire(test_id, ["res1"], ["group1"], 5)

    with open(lock_file) as f:
        locks = json.load(f)
        assert test_id in locks

    file_adapter.release(test_id)
    with open(lock_file) as f:
        locks = json.load(f)
        assert test_id not in locks


def test_file_lock_conflict(file_adapter):
    test_id1 = f"test1_{time.time()}"
    test_id2 = f"test2_{time.time()}"

    assert file_adapter.acquire(test_id1, [test_id2], [], 5)

    start = time.time()
    assert not file_adapter.acquire(test_id2, [test_id1], [], 1)
    assert time.time() - start >= 1

    file_adapter.release(test_id1)
    assert file_adapter.acquire(test_id2, [test_id1], [], 1)
    file_adapter.release(test_id2)


def test_cross_process_lock(tmp_path):
    lock_file = tmp_path / "cross_process.json"
    lock_file.write_text("{}")
    # Process 1
    adapter1 = FileLockAdapter(str(lock_file))
    assert adapter1.acquire("process1", ["process2"], [], 5)

    # Process 2
    adapter2 = FileLockAdapter(str(lock_file))
    assert not adapter2.acquire("process2", ["process1"], [], 1)

    adapter1.release("process1")
    assert adapter2.acquire("process2", ["process1"], [], 1)
    adapter2.release("process2")