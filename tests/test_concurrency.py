import pytest
import time

@pytest.mark.xdist_lock(tests=["test_3"], timeout=10, on_timeout='xfail')
def test_1():
    start = time.monotonic()
    time.sleep(2)
    duration = time.monotonic() - start
    assert 1.9 < duration < 2.1


def custom_callback(x, y , z):
    pytest.skip(reason=f"x:{x}, y:{y}, z:{z}")

@pytest.mark.xdist_lock(tests=["tests.test_groups::test_3", "test_3"], timeout=10, on_timeout=lambda: custom_callback("x", "y", "z"))
def test_2():
    start = time.monotonic()
    time.sleep(2)
    duration = time.monotonic() - start
    assert 1.9 < duration < 2.1

# test_3 blocks test_1 and test_2
@pytest.mark.xdist_lock(tests=["test_1", "test_2"], timeout=10, on_timeout="xfail")
def test_3():
    start = time.monotonic()
    time.sleep(2)
    duration = time.monotonic() - start
    assert 1.9 < duration < 2.1
