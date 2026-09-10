"""
aggregator/lock.py - PID-based run lock to prevent overlapping CRON executions.

SEC-02 fix: Uses O_CREAT|O_EXCL for atomic file creation to prevent TOCTOU race.
Falls back to stale-PID detection if the lock holder has died.
"""

import contextlib
import os

from aggregator import config

_lock_path: str = config.LOCK_FILE


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock() -> bool:
    """Atomically create lock file with our PID. Returns True if acquired."""
    # Try atomic create - fails if file already exists (no TOCTOU race)
    try:
        fd = os.open(_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        pass

    # File exists - check if the holder is still alive
    try:
        with open(_lock_path) as f:
            pid = int(f.read().strip())
        if _pid_alive(pid):
            return False  # Another run is genuinely active
    except (ValueError, OSError):
        pass  # Corrupt/unreadable lock file

    # Stale lock - remove and retry once
    try:
        os.remove(_lock_path)
    except OSError:
        return False
    try:
        fd = os.open(_lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False  # Lost the race to another process


def release_lock() -> None:
    try:
        os.remove(_lock_path)
    except FileNotFoundError:
        pass


@contextlib.contextmanager
def run_lock():
    acquired = acquire_lock()
    if not acquired:
        raise RuntimeError("Another aggregator run is already in progress")
    try:
        yield
    finally:
        release_lock()
