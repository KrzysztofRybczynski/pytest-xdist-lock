# pytest-xdist-lock

[![Python Version](https://img.shields.io/pypi/pyversions/pytest-xdist-lock)](https://pypi.org/project/pytest-xdist-lock/)
[![PyPI Version](https://img.shields.io/pypi/v/pytest-xdist-lock)](https://pypi.org/project/pytest-xdist-lock/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Plugin for distributed test synchronization in pytest-xdist using resource locks.

## Features

- 🛠 **Multiple Backends**: File-based (local) and Redis (distributed)
- ⏱ **Configurable Timeouts**: Set per-test or globally (default: 600s)
- 🔒 **Flexible Locking**: Lock by test IDs or resource groups
- 🚦 **Timeout Handling**: Skip, fail, xfail or custom callback
- 🧩 **Seamless Integration**: Works with existing pytest-xdist setup

## Installation

```bash
pip install pytest-xdist-lock
```

## Configuration

Add to pytest.ini:

```ini
[pytest]
xdist-lock-backend = redis  # or 'file'
xdist-lock-redis_url = redis://localhost:6379/0
xdist-lock-file = /tmp/pytest_locks.json  # for file backend
xdist-lock-default-timeout = 60  # seconds
xdist-lock-check-interval = 0.1  # seconds
```
## Backend Comparison

| Backend | Pros | Cons |
|--------|------|------|
| File   | ✅ No external dependencies<br>✅ Simple setup<br>✅ Good for CI pipelines | ⚠️ Requires shared filesystem<br>⚠️ Not for distributed environments<br>⚠️ Slower with many workers |
| Redis  | ✅ Distributed locking<br>✅ Better performance<br>✅ Atomic operations | ⚠️ Requires Redis server<br>⚠️ Network dependency<br>⚠️ Additional setup needed |


## Basic Usage
1. Using Marker
```python
@pytest.mark.xdist_lock(
    tests=["test_db.py::TestClass"],
    groups=["db_users"],
    timeout=10,
    on_timeout="skip"
)
def test_critical_operation():
    # Exclusive access to resources
    pass
```
2. Using Fixture
```python
def test_with_fixture(xdist_lock):
    with xdist_lock(
        tests=["test_resource.py"],
        groups=["shared_resource"],
        timeout=5,
        on_timeout=lambda: pytest.fail("Resource busy")
    ):
        # Critical section
        pass
```


## Advanced Patterns

Custom Timeout Handler
```python
def handle_timeout():
    logger.warning("Test skipped due to lock timeout")
    pytest.skip("Resource unavailable")

@pytest.mark.xdist_lock(on_timeout=handle_timeout)
def test_with_custom_handler():
    pass
```

## How It Works
```
Test Worker 1           Lock Agent            Test Worker 2
------------------      -----------      ------------------
1. |                         |                         |
   |----- acquire(T1) ------>|                         |
   | blocks=["T2"]           |<----- acquire(T2) ------|
   | groups=["db"]           | blocks=["T1"]           |
2. |<------- granted --------| groups=["db"]           |
3. |                         | -------- busy --------- |
   |                         | retry <check_interval>  |
   |                         |                         |
4. |----- release(T1) ------>|                         |
5. |                         |-------- granted ------->|
6. |----- acquire(T3) ------>|                         |
   | retry <check_interval>  |                         |
   |                         |                         |
7. |<------- timeout --------|                         |
   |                         |                         |
8. |                         |<----- release(T2) ------|

```

## API Reference

| Parameter    | Type              | Default | Description                                        |
|:-------------|:------------------|:--------|:---------------------------------------------------|
| tests        | str/List[str]     | None    | Test IDs to block                                  |
| groups       | str/List[str]     | None    | Resource groups to block                           |
| timeout      | float             | 600     | ini setting	Max wait time (seconds)                |
| on_timeout   | str/callable      | "skip"  | Action: "skip", "fail", "xfail" or custom function |

### Marker @pytest.mark.xdist_lock ###
```python 
@pytest.mark.xdist_lock(tests=["tests/test_examples.pl::test_example_2"], groups=[], timeout=60, on_timeout='skip')
def test_example_1():
    # Critical test code

@pytest.mark.xdist_lock(tests=["tests/test_examples.pl::test_example_1"], groups=[], timeout=60, on_timeout='skip')
def test_example_2():
    # Critical test code
```

### Fixture xdist_lock ###
```python
def test_example_1(xdist_lock):
    # safe test code
    with xdist_lock(group="db_users"):
        # Critical test code
    
    # safe test code


def test_example_2(xdist_lock):
    # safe test code
    with xdist_lock(group="db_users"):
        # Critical test code

    # safe test code
```


## Development Setup
```bash
# Install with all dependencies
pip install pytest-xdist-lock
```
# Configure pytest-xdist-lock plugin in pytest.ini
```pytests.ini
[pytest]
xdist-lock-backend = file
xdist-lock-file = /tmp/xdist-lock.json
xdist-lock-default-timeout = 60
xdist-lock-check-interval = 0.1

```

# Run tests
```
pytest -n auto tests/ --xdist-lock-backend=file --xdist-lock-file=/tmp/xdist-lock.json
```
or 
```
pytest -n auto tests/ --xdist-lock-backend=redis --xdist-lock-redis_url=redis://localhost:6379/0
```
## Best Practices
- Use descriptive group names: "db_primary" vs "database",
- Set reasonable timeouts,
- Add xdist WORKER_ID to logging format while debugging lock issues: 


## FAQ

Q: Can I use both markers and fixtures together?<br>
A: Yes, they'll combine their lock requirements.

Q: How to debug lock issues?<br>
A: Set log level to DEBUG:
```python
logging.basicConfig(
    level=logging.DEBUG,
    format=f'%(asctime)s {os.environ.get("PYTEST_XDIST_WORKER", "%(name)s")} %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
```

```bash
pytest --log-level=DEBUG
```
Q: Is there a performance overhead?<br>
A: Minimal with Redis, file backend may slow down with many workers.

## Changelog
0.1.0 (Current)
- Initial stable release
- File and Redis backends
- Marker and fixture support
- Custom timeout handlers

## License
MIT - See LICENSE for details.


