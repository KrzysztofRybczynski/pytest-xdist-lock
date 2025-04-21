# import logging
# import os
import tempfile
import pytest
from contextlib import contextmanager
from pathlib import Path
from typing import Union
from pytest_xdist_lock.locks.file_lock import FileLockAdapter
from pytest_xdist_lock.locks.redis_lock import RedisLockAdapter

#
# logging.basicConfig(
#     level=logging.INFO,
#     format=f'%(asctime)s {os.environ.get("PYTEST_XDIST_WORKER", "%(name)s")} %(levelname)s - %(message)s',
#     handlers=[logging.StreamHandler()]
# )

def pytest_addoption(parser):
    default_lock_file = str(Path(tempfile.gettempdir()) / "pytest_xdist_locks.json")
    parser.addini("xdist-lock-backend", help="Backend for locks (file/redis)", default="file")
    parser.addini("xdist-lock-file", help="Path to lock file", default=default_lock_file)
    parser.addini("xdist-lock-redis-url", help="Redis URL if backend=redis", default=None)
    parser.addini("xdist-lock-default-timeout", help="Default test lock timeout (seconds)", default="600")
    parser.addini("xdist-lock-check-interval", help="Lock check interval (seconds)", default="1")
    parser.addoption("--xdist-lock-backend", help="Lock backend to use")
    parser.addoption("--xdist-lock-file", help="Path to lock file")
    parser.addoption("--xdist-lock-redis-url", help="Redis URL if backend=redis")
    parser.addoption("--xdist-lock-default-timeout", help="Default test lock timeout (seconds)")
    parser.addoption("--xdist-lock-check-interval", help="Lock check interval (seconds)")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        """xdist_lock(tests=None, groups=None, timeout=None, on_timeout=None): 
        Synchronize tests using distributed locks.
        
        Args:
            tests: Str or List of test IDs that will be blocked by this lock
            groups: Str or List of resource groups of tests to lock
            timeout: Custom lock timeout (overrides default)
            on_timeout: Action on lock timeout ('skip', 'fail', 'xfail' or callable custom method)
        
        Example:
            @pytest.mark.xdist_lock(
                tests=["test_db.py::TestClass"],
                groups=["database"],
                timeout=10
            )
        """
    )


    backend = config.getoption("--xdist-lock-backend") or config.getini("xdist-lock-backend")
    lock_file = config.getoption("--xdist-lock-file") or config.getini("xdist-lock-file")
    if not hasattr(config, 'workerinput'):
        config.xdist_lock_enabled = False
        if backend == "file":
            Path(lock_file).write_text("{}")
        return

    if backend == "redis":
        url = config.getoption("--xdist-lock-redis-url") or config.getini("xdist-lock-redis-url")
        if not url:
            raise ValueError("Redis backend requires 'xdist_lock_redis_url'")
        config.lock_adapter = RedisLockAdapter(url)
    else:
        #lock_file = config.getoption("--xdist-lock-file") or config.getini("xdist-lock-file")
        config.lock_adapter = FileLockAdapter(lock_file)

    config.xdist_lock_enabled = True
    config.lock_default_timeout = int(config.getoption("--xdist-lock-default-timeout") or  config.getini("xdist-lock-default-timeout"))
    config.lock_check_interval = float(config.getoption("--xdist-lock-check-interval") or config.getini("xdist-lock-check-interval"))

def _normalize_test_id(item, name: str) -> str:
    if "::" in name:
        return name.replace(".py", "").replace("/", ".")
    module_name = getattr(item, "module", None)
    if module_name is None:
        return f"module::{name}"
    return f"{module_name.__name__}::{name}"

def _process_timeout_action(on_timeout, message):
    if on_timeout is None:
        raise ValueError("on_timeout cannot be None")

    if callable(on_timeout):
        try:
            on_timeout()
        except Exception:
            #logging.error(f"Custom timeout handler failed: {str(e)}")
            pytest.skip(f"{message} (custom handler failed)")

    elif isinstance(on_timeout, str):
        if on_timeout == "skip":
            pytest.skip(message)
        elif on_timeout == "fail":
            pytest.fail(message)
        elif on_timeout == "xfail":
            pytest.xfail(message)
        else:
             raise ValueError(f"Unsupported on_timeout value: {on_timeout}")
    else:
        raise ValueError(f"Unsupported on_timeout value: {on_timeout}")


@pytest.fixture
def xdist_lock(request):
    """Context manager for acquiring distributed locks in pytest-xdist.
        Usage:
        with xdist_lock(locking_deps=["test_example"], locking_groups=["db.example"], timeout=60, on_timeout="skip"):
            # critical section
        """
    @contextmanager
    def create_lock(tests: Union[str, list] = None, groups: Union[str, list] = None, timeout: int = None, on_timeout: Union[str,callable] = "skip"):

        if tests is not None and not isinstance(tests, (str, list)):
            raise TypeError("tests must be string or list")

        if groups is not None and not isinstance(groups, (str, list)):
            raise TypeError("groups must be string or list")

        if timeout is not None and (not isinstance(timeout, (int, float)) or timeout <= 0):
            raise ValueError("timeout must be positive number")

        if not (isinstance(on_timeout, str) or callable(on_timeout)):
            raise TypeError("on_timeout must be string or callable")

        tests = [tests] if isinstance(tests, str) else tests or []
        groups = [groups] if isinstance(groups, str) else groups or []

        test_id = _normalize_test_id(request.node, request.node.nodeid)
        default_timeout = request.config.lock_default_timeout
        check_interval = request.config.lock_check_interval
        timeout = timeout if timeout else default_timeout
        if not request.config.lock_adapter.acquire(
                test_id=test_id,
                tests=tests,
                groups=groups,
                timeout=timeout,
                check_interval=check_interval
        ):
            _process_timeout_action(on_timeout, f"Could not acquire lock for {test_id}")
        try:
            yield
        finally:
            request.config.lock_adapter.release(test_id)

    return create_lock

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    if not item.config.xdist_lock_enabled:
        yield
        return

    lock_marker = item.get_closest_marker("xdist_lock")

    if lock_marker:
        if not isinstance(lock_marker.kwargs, dict):
            raise ValueError("xdist_lock marker kwargs must be a dictionary")

        test_id = _normalize_test_id(item, item.nodeid)
        default_timeout = item.config.lock_default_timeout
        check_interval = item.config.lock_check_interval

        tests = lock_marker.kwargs.get("tests", [])
        groups = lock_marker.kwargs.get("groups", [])
        timeout = lock_marker.kwargs.get("timeout", default_timeout)
        on_timeout = lock_marker.kwargs.get("on_timeout", "skip")

        if not isinstance(tests, (str, list)):
            raise TypeError("'tests' must be string or list")
        if not isinstance(groups, (str, list)):
            raise TypeError("'groups' must be string or list")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("'timeout' must be positive number")
        if not (isinstance(on_timeout, str) or callable(on_timeout)):
            raise TypeError("'on_timeout' must be string or callable")

        tests  = [tests] if isinstance(tests , str) else tests or []
        groups = [groups] if isinstance(groups, str) else groups or []

        if not isinstance(tests, list) or not all(isinstance(t, str) and t.strip() for t in tests):
            raise ValueError("All test names must be non-empty strings")
        if not isinstance(groups, list) or not all(isinstance(g, str) and g.strip() for g in groups):
            raise ValueError("All group names must be non-empty strings")

            # Walidacja wartości on_timeout
        valid_timeout_actions = {"skip", "fail", "xfail"}
        if isinstance(on_timeout, str) and on_timeout not in valid_timeout_actions:
            raise ValueError(f"Invalid on_timeout value. Allowed: {valid_timeout_actions}")

        try:
            tests = [_normalize_test_id(item, test) for test in tests]
        except Exception as e:
            raise ValueError(f"Failed to normalize test IDs: {str(e)}")

        if not item.config.lock_adapter.acquire(
                test_id=test_id,
                tests=tests,
                groups=groups,
                timeout=timeout,
                check_interval=check_interval):
            _process_timeout_action(on_timeout, f"Could not acquire lock for {test_id}")

    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    yield
    if hasattr(item.config, 'lock_adapter'):
        item.config.lock_adapter.release(_normalize_test_id(item, item.nodeid))