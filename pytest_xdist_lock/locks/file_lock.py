import atexit
import fcntl
import json
import logging
import os
import time
from typing import Dict, Set, List
from pathlib import Path
from pytest_xdist_lock.locks.base_lock import BaseLock

class FileLockAdapter(BaseLock):
    """File-based lock implementation using flock.

    Features:
    - Atomic operations via file locking
    - Process-safe cleanup
    - Timeout support

    Note: Not thread-safe (designed for process-level synchronization)
    """
    FILE_ACQUIRE_TIMEOUT = 5.0
    FILE_ACQUIRE_CHECK_INTERVAL = 0.1

    def __init__(self, lock_file: str) -> None:
        """
        Initialize file-based locking system.

        :param lock_file: Path to lock file. If None, uses a temp file.
        """
        self._lock_file = Path(lock_file)
        self._file_handle = None
        self._owned_keys: Set[str] = set()
        atexit.register(self._release_all_locks)

    def _acquire_file_lock(self) -> bool:
        """Acquire exclusive lock on the file."""
        if self._file_handle is None:
            try:
                self._file_handle = open(self._lock_file, 'r+')
            except IOError as e:
                logging.error(f"Failed to open lock file: {e}")
                return False

        start_time = time.time()
        while time.time() - start_time < self.FILE_ACQUIRE_TIMEOUT:
            try:
                fcntl.flock(self._file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._file_handle.seek(0)
                return True
            except BlockingIOError:
                time.sleep(self.FILE_ACQUIRE_CHECK_INTERVAL)
        return False

    def _release_file_lock(self) -> None:
        """Release exclusive lock on the file."""
        if self._file_handle:
            try:
                fcntl.flock(self._file_handle, fcntl.LOCK_UN)
            except (AttributeError, OSError):
                pass

    def _read_locks(self) -> Dict[str, List[str]]:
        """Read current locks states.

        Raises:
            IOError: If file operations fail
        """

        if not self._file_handle:
            raise IOError("Lock file handle not initialized")
        try:
            self._file_handle.seek(0)
            content = self._file_handle.read()
            return json.loads(content) if content else {}
        except json.JSONDecodeError:
            return {}

    def _write_locks(self, locks: Dict[str, List[str]]) -> None:
        """Write locks state.

        Raises:
            IOError: If file operations fail
        """
        if not self._file_handle:
            raise IOError("Lock file handle not initialized")
        try:
            self._file_handle.seek(0)
            self._file_handle.truncate()
            json.dump({lock_key: list(locked_resources) for lock_key, locked_resources in locks.items()}, self._file_handle)
            self._file_handle.flush()
            os.fsync(self._file_handle.fileno())  # Ensure physical write
        except (OSError, IOError) as e:
            logging.error(f"Error writing locks: {e}")
            raise

    def acquire(self, test_id: str, tests: List[str], groups: List[str], timeout: float, check_interval: float = 1) -> bool:
        """
        Acquire lock for given key.

        Args:
            test_id: Test identifier to lock
            tests: List[str] Test IDs that will be blocked by this lock
            groups: List[str] Group IDs that will be blocked by this lock
            timeout: Maximum wait time in seconds
            check_interval: Time between lock attempts

        Returns:
            bool: True if lock acquired, False if timeout
        """
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self._acquire_file_lock():
                locks = self._read_locks()
                active_locks = [
                    blocked_test for blocked_test, locked_resources in locks.items()
                    if test_id in locked_resources or any(group in locked_resources for group in groups)
                ]

                if active_locks:
                    logging.debug(f"Test[{test_id}] - Blocked by: {active_locks}")
                    self._release_file_lock()
                    time.sleep(check_interval)
                    continue

                current_owners = set(locks.get(test_id, []))
                new_tests = set(tests)
                new_groups = set(groups)
                locks[test_id] = list(current_owners | new_tests | new_groups)
                self._write_locks(locks)
                self._owned_keys.add(test_id)
                self._release_file_lock()
                logging.debug(f"Test [{test_id}] - Acquired. Blocking tests: {tests} and groups:{groups}")
                return True
        self._release_file_lock()
        return False

    def release(self, test_id: str) -> None:
        """Release lock with guaranteed cleanup."""
        if not self._acquire_file_lock():
            raise BlockingIOError(f"Unable to flock file: {self._lock_file}")

        try:
            locks = self._read_locks()
            if test_id in locks:
                del locks[test_id]
                self._write_locks(locks)
                self._owned_keys.discard(test_id)
                logging.debug(f"Test[{test_id}] - Lock released")
        finally:
            self._release_file_lock()

    def _release_all_locks(self) -> None:
        """Clean up file handles and locks."""
        if getattr(self, '_is_cleaned', False) or not self._owned_keys:
            return

        try:
            if not self._acquire_file_lock():
                logging.warning("Cleanup failed - could not acquire lock")
                return
            try:
                locks = self._read_locks()
                for key in list(self._owned_keys):
                    if key in locks:
                        del locks[key]

                self._write_locks(locks)
                self._owned_keys.clear()
                self._is_cleaned = True
            finally:
                self._release_file_lock()
        finally:
            if self._file_handle:
                try:
                    self._file_handle.close()
                except Exception:
                    pass
                self._file_handle = None

    def __del__(self):
        """Destructor to ensure cleanup."""
        self._release_all_locks()
