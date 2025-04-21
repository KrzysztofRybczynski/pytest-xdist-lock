import pytest
import time


@pytest.mark.xdist_lock(groups=["db.users"], timeout=10)
def test_group_1():
    start = time.monotonic()
    time.sleep(2)
    duration = time.monotonic() - start
    assert 1.9 < duration < 2.1


@pytest.mark.xdist_lock(groups=["db.users"], timeout=10)
def test_group_2():
    start = time.monotonic()
    time.sleep(2)
    duration = time.monotonic() - start
    assert 1.9 < duration < 2.1


@pytest.mark.xdist_lock(groups=["db.system"], timeout=10)
def test_group_3():
    start = time.monotonic()
    time.sleep(2)
    duration = time.monotonic() - start
    assert 1.9 < duration < 2.1


@pytest.mark.xdist_lock(groups=["db.system"], timeout=10)
def test_group_4():
    start = time.monotonic()
    time.sleep(2)
    duration = time.monotonic() - start
    assert 1.9 < duration < 2.1


