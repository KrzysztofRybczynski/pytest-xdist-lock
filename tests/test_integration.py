import os
import sys
import pytest
import tempfile
from subprocess import run


@pytest.fixture
def lock_file(tmp_path):
    lock_file = tmp_path / "test_locks.json"
    lock_file.write_text("{}")
    return str(lock_file)

def test_plugin_registration(pytestconfig):
    assert pytestconfig.pluginmanager.hasplugin('pytest-xdist-lock')


def test_marker_registration(pytestconfig):
    markers = pytestconfig.getini("markers")
    assert any("xdist_lock(" in m for m in markers)


def run_pytest_test(test_content, lock_file):
    """Pomocnicza funkcja do uruchamiania testów w subprocessie"""
    test_dir = os.path.abspath(os.path.dirname(__file__))
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.dirname(test_dir)

    # Tworzymy tymczasowy plik z testami
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py') as f:
        f.write(test_content)
        f.flush()

        cmd = [
            sys.executable,
            "-m", "pytest",
            "-v",
            "--xdist-lock-file", lock_file,
            "--xdist-lock-backend", "file",
            "-n2",
            f.name  # Używamy nazwy pliku zamiast stdin
        ]

        result = run(cmd, env=env, capture_output=True, text=True)
        print("\n=== STDOUT ===\n", result.stdout)
        print("\n=== STDERR ===\n", result.stderr, file=sys.stderr)
        return result.returncode


def test_lock_marker_usage(lock_file):
    test_content = """
import pytest
import time

@pytest.mark.xdist_lock(tests=["test_second"], timeout=5)
def test_first():
    time.sleep(0.5)
    assert True

@pytest.mark.xdist_lock(tests=["test_first"], timeout=5)
def test_second():
    assert True
"""
    assert run_pytest_test(test_content, lock_file) == 0


def test_lock_fixture_usage(lock_file):
    test_content = """
import pytest
import time

def test_first(xdist_lock):
    with xdist_lock(tests=["test_second"], timeout=5):
        time.sleep(0.5)
        assert True

def test_second(xdist_lock):
    with xdist_lock(tests=["test_first"], timeout=5):
        assert True
"""
    assert run_pytest_test(test_content, lock_file) == 0


def test_group_locking(lock_file):
    test_content = """
import pytest
import time

@pytest.mark.xdist_lock(groups=["db"], timeout=5)
def test_db_access1():
    time.sleep(0.5)
    assert True

@pytest.mark.xdist_lock(groups=["db"], timeout=5)
def test_db_access2():
    assert True
"""
    assert run_pytest_test(test_content, lock_file) == 0