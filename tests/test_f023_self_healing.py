"""Tests for F023: Pipeline Self-Healing.

Lock-age auto-cleanup, truncation detection, fix-hash cycle detection.
"""
import os
import sys
import time
import fcntl
import hashlib
import pytest
from unittest.mock import patch, Mock


# ── Task 1+5: Lock-age auto-cleanup in acquire_lock ─────────────────────

def test_lock_age_old_lock_with_live_pid_removed(panel, tmpdir_path, monkeypatch):
    """Lock file >12h old with live PID + owner verified → removed, retried, acquired.

    Simulates SIGKILL + PID recycling: a stale lock file whose PID now
    belongs to a different dokima process. The age check catches this.
    """
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path()

    # Write our PID to the lock file
    with open(lp, "w") as f:
        f.write(f"{os.getpid()}\n")

    # Set mtime to 13 hours ago (exceeds 12h default threshold)
    old_mtime = time.time() - (13 * 3600)
    os.utime(lp, (old_mtime, old_mtime))

    # Mock: fcntl.flock raises on first call (simulating contention),
    # then succeeds on retry (after lock file removed + recreated)
    call_count = [0]

    def mock_flock(fd, op):
        call_count[0] += 1
        if call_count[0] == 1:
            # First attempt: restore PID to file (was truncated by open("w"))
            # and raise contention error
            fd.write(f"{os.getpid()}\n")
            fd.flush()
            raise BlockingIOError(11, "Resource temporarily unavailable")
        # Subsequent calls succeed (after lock removal + recreation)
        return

    # Mock _check_pid and _verify_pid_owner to return True
    # (simulating PID recycled to another dokima process)
    with patch.object(panel, 'fcntl') as mock_fcntl:
        mock_fcntl.flock = mock_flock
        mock_fcntl.LOCK_EX = fcntl.LOCK_EX
        mock_fcntl.LOCK_NB = fcntl.LOCK_NB

        held, fd = panel.acquire_lock()
        assert held is True
        assert fd is not None
        fd.close()

    try:
        os.remove(lp)
    except OSError:
        pass


def test_lock_age_fresh_lock_with_live_pid_exits(panel, tmpdir_path, monkeypatch):
    """Lock file <12h old with live PID → exits (preserved, not removed)."""
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path()

    # Write our PID to the lock file
    with open(lp, "w") as f:
        f.write(f"{os.getpid()}\n")

    # Fresh mtime (now)
    os.utime(lp, (time.time(), time.time()))

    # Mock fcntl.flock to raise (simulating contention)
    call_count = [0]

    def mock_flock(fd, op):
        call_count[0] += 1
        if call_count[0] == 1:
            # Restore PID to file (was truncated by open("w"))
            fd.write(f"{os.getpid()}\n")
            fd.flush()
            raise BlockingIOError(11, "Resource temporarily unavailable")
        return

    # Intercept sys.exit
    old_exit = panel.sys.exit
    exit_codes = []
    def fake_exit(code=0):
        exit_codes.append(code)
        raise SystemExit(code)
    panel.sys.exit = fake_exit

    try:
        with patch.object(panel._utils, 'fcntl') as mock_fcntl:
            mock_fcntl.flock = mock_flock
            mock_fcntl.LOCK_EX = fcntl.LOCK_EX
            mock_fcntl.LOCK_NB = fcntl.LOCK_NB

            try:
                panel.acquire_lock()
            except SystemExit:
                pass
    finally:
        panel.sys.exit = old_exit

    try:
        os.remove(lp)
    except OSError:
        pass

    assert len(exit_codes) > 0
    assert exit_codes[0] == 1


def test_lock_age_env_var_threshold(panel, tmpdir_path, monkeypatch):
    """PANEL_LOCK_MAX_AGE_SECS env var controls the threshold."""
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path()

    # Set threshold to 2 seconds via env var
    monkeypatch.setenv("PANEL_LOCK_MAX_AGE_SECS", "2")

    # Write our PID to the lock file
    with open(lp, "w") as f:
        f.write(f"{os.getpid()}\n")

    # Set mtime to 3 seconds ago (exceeds 2s threshold)
    old_mtime = time.time() - 3
    os.utime(lp, (old_mtime, old_mtime))

    call_count = [0]

    def mock_flock(fd, op):
        call_count[0] += 1
        if call_count[0] == 1:
            # Restore PID to file (was truncated by open("w"))
            fd.write(f"{os.getpid()}\n")
            fd.flush()
            raise BlockingIOError(11, "Resource temporarily unavailable")
        return

    with patch.object(panel, 'fcntl') as mock_fcntl:
        mock_fcntl.flock = mock_flock
        mock_fcntl.LOCK_EX = fcntl.LOCK_EX
        mock_fcntl.LOCK_NB = fcntl.LOCK_NB

        held, fd = panel.acquire_lock()
        assert held is True
        fd.close()

    try:
        os.remove(lp)
    except OSError:
        pass


def test_lock_age_dead_pid_still_cleaned(panel, tmpdir_path, monkeypatch):
    """Lock file with dead PID is cleaned up regardless of age (existing behavior)."""
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path()

    # Write dead PID to the lock file
    with open(lp, "w") as f:
        f.write("99999999\n")

    # Recent mtime
    os.utime(lp, (time.time(), time.time()))

    call_count = [0]

    def mock_flock(fd, op):
        call_count[0] += 1
        if call_count[0] == 1:
            # Restore PID to file (was truncated by open("w"))
            fd.write("99999999\n")
            fd.flush()
            raise BlockingIOError(11, "Resource temporarily unavailable")
        return

    with patch.object(panel, 'fcntl') as mock_fcntl:
        mock_fcntl.flock = mock_flock
        mock_fcntl.LOCK_EX = fcntl.LOCK_EX
        mock_fcntl.LOCK_NB = fcntl.LOCK_NB

        held, fd = panel.acquire_lock()
        assert held is True
        fd.close()

    try:
        os.remove(lp)
    except OSError:
        pass


# ── Task 2+6: Truncation detection ────────────────────────────────────

def test_detect_truncation_no_report_marker_mid_sentence(panel):
    """Output missing Report: line + ends mid-sentence → truncated."""
    output = "I have implemented the feature and added tests.\nThe code is ready"
    assert panel._detect_truncation(output) is True


def test_detect_truncation_has_report_line(panel):
    """Output with Report: line → not truncated."""
    output = "Implemented feature\n\nReport: all tests pass, build clean\n\nDone."
    assert panel._detect_truncation(output) is False


def test_detect_truncation_ends_with_terminal_punctuation(panel):
    """Output ends with . ! or ? → not truncated (even without Report: line)."""
    output = "The feature is complete and all tests pass."
    assert panel._detect_truncation(output) is False


def test_detect_truncation_empty_output(panel):
    """Empty output → truncated (coder crashed)."""
    assert panel._detect_truncation("") is True


def test_detect_truncation_none_input(panel):
    """None input → not truncated (safety)."""
    assert panel._detect_truncation(None) is False


def test_detect_truncation_short_without_report(panel):
    """Short output (< 200 chars) without Report: line → truncated."""
    output = "Just a few words"
    assert panel._detect_truncation(output) is True


def test_detect_truncation_whitespace_only(panel):
    """Whitespace-only output → truncated."""
    assert panel._detect_truncation("   \n  \n  ") is True


def test_detect_truncation_ends_with_exclamation(panel):
    """Output ending with ! → not truncated."""
    output = "Everything is working!"
    assert panel._detect_truncation(output) is False


def test_detect_truncation_ends_with_question(panel):
    """Output ending with ? → not truncated."""
    output = "Is everything working?"
    assert panel._detect_truncation(output) is False


# ── Task 3+7: Hash cycle detection ──────────────────────────────────────

def test_hash_output_returns_md5_hex(panel):
    """_hash_output returns an md5 hex digest."""
    result = panel._hash_output("hello world")
    assert isinstance(result, str)
    assert len(result) == 32  # MD5 hex digest is 32 chars
    assert result == hashlib.md5(b"hello world").hexdigest()


def test_hash_output_different_text_different_hash(panel):
    """Different text produces different hash."""
    h1 = panel._hash_output("output A")
    h2 = panel._hash_output("output B")
    assert h1 != h2


def test_hash_output_same_text_same_hash(panel):
    """Same text produces same hash."""
    h1 = panel._hash_output("identical text")
    h2 = panel._hash_output("identical text")
    assert h1 == h2


def test_hash_output_empty_string(panel):
    """Empty string produces a valid hash."""
    result = panel._hash_output("")
    assert len(result) == 32
    assert result == hashlib.md5(b"").hexdigest()


def test_vet_hash_cycle_same_output_blocked(panel, tmpdir_path, monkeypatch):
    """Identical test+build output before/after coder fix → skip to BLOCKED.

    Simulates the vet verification loop where the coder's fix produces
    no change in test/build output, indicating a fix-loop (Bug 13).
    """
    import subprocess

    panel.PROJECT_DIR = tmpdir_path
    panel.REPO = "test/test"
    panel.DEFAULT_BRANCH = "main"
    panel.TEST_CMD = "echo test"
    panel.BUILD_CMD = "echo build"

    # Mock _safe_run: first iter fails, second iter fails too (hash same)
    run_count = [0]

    def mock_safe_run(cmd_str, cwd=None, timeout=None):
        run_count[0] += 1
        if run_count[0] <= 2:
            # First verification: tests + build both fail
            return subprocess.CompletedProcess(
                args=[], returncode=1,
                stdout="1 passed, 1 failed", stderr="")
        # Second verification after coder fix: same output → hash cycle
        return subprocess.CompletedProcess(
            args=[], returncode=1,
            stdout="1 passed, 1 failed", stderr="")

    with patch.object(panel, 'git', return_value=("", "", 0)), \
         patch.object(panel, '_safe_run', side_effect=mock_safe_run), \
         patch.object(panel, 'halt_and_revert') as mock_halt, \
         patch.object(panel._agent, 'spawn_agent') as mock_spawn, \
         patch.object(panel, 'detect_commands', return_value=(
             "echo test", "echo build", "echo lint")):

        result = panel.run_phase3_vet(
            feature="test-feature",
            branch="test-branch",
            pr_sections="## What Changed\ntest",
            impact="LOW",
            spec_path=""
        )

    # Should be BLOCKED because coder fix produced no change (hash cycle)
    assert result.get("coder_failed") is True
    assert result.get("verdict") == "VET_FAILED"
    # halt_and_revert should have been called
    assert mock_halt.called


def test_vet_hash_cycle_different_output_proceeds(panel, tmpdir_path, monkeypatch):
    """Different test+build output after coder fix → proceed normally.

    When the coder fix changes the output, the hash differs and the
    retry loop continues as normal.
    """
    import subprocess

    panel.PROJECT_DIR = tmpdir_path
    panel.REPO = "test/test"
    panel.DEFAULT_BRANCH = "main"
    panel.TEST_CMD = "echo test"
    panel.BUILD_CMD = "echo build"

    run_count = [0]

    def mock_safe_run(cmd_str, cwd=None, timeout=None):
        run_count[0] += 1
        if run_count[0] <= 2:
            # First verification: tests + build both fail
            return subprocess.CompletedProcess(
                args=[], returncode=1,
                stdout="1 passed, 1 failed", stderr="")
        # After coder fix: tests pass (different output)
        return subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="4 passed, 0 failed", stderr="")

    with patch.object(panel, 'git', return_value=("", "", 0)), \
         patch.object(panel, '_safe_run', side_effect=mock_safe_run), \
         patch.object(panel._agent, 'spawn_agent') as mock_spawn, \
         patch.object(panel, 'detect_commands', return_value=(
             "echo test", "echo build", "echo lint")), \
         patch.object(panel, 'gh', return_value=(
             "https://github.com/test/test/pull/99", "", 0)):

        result = panel.run_phase3_vet(
            feature="test-feature",
            branch="test-branch",
            pr_sections="## What Changed\ntest",
            impact="LOW",
            spec_path=""
        )

    # Should NOT be blocked — different output after fix
    assert result.get("coder_failed") is False
    # spawn_agent should have been called to fix
    assert mock_spawn.called
    # PR should have been created
    assert result.get("pr_url") is not None


# ── Task 4: Lock-age auto-cleanup in _get_lock_state (--status) ─────────

def test_get_lock_state_old_lock_cleaned(panel, tmpdir_path, monkeypatch):
    """_get_lock_state removes lock file older than threshold even if PID alive."""
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path(tmpdir_path)

    # Write our PID to lock file (simulates a real process with our PID)
    with open(lp, "w") as f:
        f.write(f"{os.getpid()}\n")

    # Set mtime to 13 hours ago (exceeds default threshold)
    old_mtime = time.time() - (13 * 3600)
    os.utime(lp, (old_mtime, old_mtime))

    # Mock _check_pid to return True (PID is alive — us!)
    with patch.object(panel, '_check_pid', return_value=True):
        running, pid, info = panel._get_lock_state(tmpdir_path)

    # Should NOT be running — lock was removed due to age
    assert running is False
    assert pid == ""
    # Lock file should be gone
    assert not os.path.exists(lp)


def test_get_lock_state_fresh_lock_preserved(panel, tmpdir_path, monkeypatch):
    """_get_lock_state preserves fresh lock file with live PID."""
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path(tmpdir_path)

    # Write our PID to lock file
    with open(lp, "w") as f:
        f.write(f"{os.getpid()}\n")

    # Fresh mtime (now)
    os.utime(lp, (time.time(), time.time()))

    # Mock _check_pid to return True (PID is alive — us!)
    with patch.object(panel, '_check_pid', return_value=True):
        running, pid, info = panel._get_lock_state(tmpdir_path)

    # Should still be running — lock is fresh
    assert running is True
    assert pid == str(os.getpid())
    # Lock file should still exist
    assert os.path.exists(lp)

    # Clean up
    try:
        os.remove(lp)
    except OSError:
        pass


def test_get_lock_state_lock_missing_returns_false(panel, tmpdir_path):
    """_get_lock_state returns False when no lock file exists."""
    running, pid, info = panel._get_lock_state(tmpdir_path)
    assert running is False
    assert pid == ""
    assert info == {}
