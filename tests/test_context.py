import time
import logging
import pytest

@pytest.mark.parametrize("group,test_id", [
    ("group1", "test_1"),
    ("group1", "test_2"),
    ("group2", "test_3"),
    ("group2", "test_4"),
    ("group3", "test_5"),
    ("group3", "test_6")
])
def test_group_locking(xdist_lock, group, test_id):
    with xdist_lock(groups=[group]):
        logging.info(f"start {test_id}")
        time.sleep(2)
        logging.info(f"end {test_id}")
        assert True