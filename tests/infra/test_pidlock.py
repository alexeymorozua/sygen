"""Tests for PID lockfile management."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestIsProcessAlive:
    """Test process liveness detection."""

    def test_current_process_is_alive(self) -> None:
        from sygen_bot.infra.pidlock import _is_process_alive

        assert _is_process_alive(os.getpid()) is True

    def test_nonexistent_pid_is_dead(self) -> None:
        from sygen_bot.infra.pidlock import _is_process_alive

        # PID 2^30 is extremely unlikely to exist
        assert _is_process_alive(2**30) is False

    def test_permission_error_means_alive(self) -> None:
        from sygen_bot.infra.pidlock import _is_process_alive

        with patch("os.kill", side_effect=PermissionError):
            assert _is_process_alive(999) is True


class TestAcquireLock:
    """Test PID lock acquisition."""

    def test_creates_pid_file(self, tmp_path: Path) -> None:
        from sygen_bot.infra.pidlock import acquire_lock, release_lock

        pid_file = tmp_path / "bot.pid"
        acquire_lock(pid_file=pid_file)
        try:
            assert pid_file.exists()
            assert pid_file.read_text(encoding="utf-8").strip() == str(os.getpid())
        finally:
            release_lock(pid_file=pid_file)

    def test_stale_pid_file_overwritten(self, tmp_path: Path) -> None:
        from sygen_bot.infra.pidlock import acquire_lock, release_lock

        pid_file = tmp_path / "bot.pid"
        # Write a PID that doesn't exist (no flock held → lock is free)
        pid_file.write_text("999999999", encoding="utf-8")

        acquire_lock(pid_file=pid_file)
        try:
            assert pid_file.read_text(encoding="utf-8").strip() == str(os.getpid())
        finally:
            release_lock(pid_file=pid_file)

    def test_corrupt_pid_file_overwritten(self, tmp_path: Path) -> None:
        from sygen_bot.infra.pidlock import acquire_lock, release_lock

        pid_file = tmp_path / "bot.pid"
        pid_file.write_text("not-a-number", encoding="utf-8")

        acquire_lock(pid_file=pid_file)
        try:
            assert pid_file.exists()
        finally:
            release_lock(pid_file=pid_file)

    def test_active_lock_without_kill_raises_system_exit(self, tmp_path: Path) -> None:
        from sygen_bot.infra.pidlock import acquire_lock

        pid_file = tmp_path / "bot.pid"
        # Simulate another process holding the flock
        fd = os.open(str(pid_file), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, str(os.getpid()).encode())

        try:
            with pytest.raises(SystemExit):
                acquire_lock(pid_file=pid_file)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def test_active_pid_with_kill_kills_and_acquires(self, tmp_path: Path) -> None:
        from sygen_bot.infra.pidlock import acquire_lock, release_lock

        pid_file = tmp_path / "bot.pid"
        fake_pid = 999999999

        # Hold a flock, then release in _kill_and_wait mock to simulate process death
        holder_fd = os.open(str(pid_file), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(holder_fd, fcntl.LOCK_EX)
        os.write(holder_fd, str(fake_pid).encode())

        def fake_kill_and_wait(pid: int) -> None:
            # Simulate the other process dying — release the lock
            fcntl.flock(holder_fd, fcntl.LOCK_UN)
            os.close(holder_fd)

        with patch("sygen_bot.infra.pidlock._kill_and_wait", side_effect=fake_kill_and_wait):
            acquire_lock(pid_file=pid_file, kill_existing=True)

        try:
            assert pid_file.read_text(encoding="utf-8").strip() == str(os.getpid())
        finally:
            release_lock(pid_file=pid_file)

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        from sygen_bot.infra.pidlock import acquire_lock, release_lock

        pid_file = tmp_path / "deep" / "nested" / "bot.pid"
        acquire_lock(pid_file=pid_file)
        try:
            assert pid_file.exists()
        finally:
            release_lock(pid_file=pid_file)


class TestReleaseLock:
    """Test PID lock release."""

    def test_removes_pid_file(self, tmp_path: Path) -> None:
        from sygen_bot.infra.pidlock import acquire_lock, release_lock

        pid_file = tmp_path / "bot.pid"
        acquire_lock(pid_file=pid_file)
        release_lock(pid_file=pid_file)
        assert not pid_file.exists()

    def test_noop_when_no_file(self, tmp_path: Path) -> None:
        from sygen_bot.infra.pidlock import release_lock

        pid_file = tmp_path / "bot.pid"
        release_lock(pid_file=pid_file)  # No error
