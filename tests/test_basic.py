import types
import pytest
from pytest_xdist_lock.plugin import _normalize_test_id, _process_timeout_action


def test_normalize_test_id():

    class MockItem:
        def __init__(self):
            module = types.ModuleType("test_module")
            self.module = module
            self.nodeid = "test_module.py::test_func"

    mock_item = MockItem()

    assert _normalize_test_id(mock_item, "path/to/test.py::test_func") == "path.to.test::test_func"

    assert _normalize_test_id(mock_item, "test_func") == "test_module::test_func"

def test_process_timeout_action_skip():
    with pytest.raises(pytest.skip.Exception):
        _process_timeout_action("skip", "test message")

def test_process_timeout_action_fail():
    with pytest.raises(pytest.fail.Exception):
        _process_timeout_action("fail", "test message")

def test_process_timeout_action_xfail():
    with pytest.raises(pytest.xfail.Exception):
        _process_timeout_action("xfail", "test message")

def test_process_timeout_action_custom():
    called = False

    def custom_handler():
        nonlocal called
        called = True
        pytest.skip("custom skip")

    with pytest.raises(pytest.skip.Exception):
        _process_timeout_action(custom_handler, "test message")

    assert called

def test_process_timeout_action_custom_error():
    def failing_handler():
        raise ValueError("test error")

    with pytest.raises(pytest.skip.Exception):
        _process_timeout_action(failing_handler, "test message")

def test_process_timeout_action_invalid():
    with pytest.raises(ValueError):
        _process_timeout_action(123, "test message")
