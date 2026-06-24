"""Tests for control panel handlers: --status, --stop, --kill, --help, --list-crons."""
import os
import sys
import pytest

def test_show_help_exits_zero(panel):
    with pytest.raises(SystemExit) as exc:
        panel.show_help()
    assert exc.value.code == 0

def test_handle_status_idle(panel, tmpdir_path):
    panel.PROJECT_DIR = tmpdir_path
    # No lock file = idle
    with pytest.raises(SystemExit) as exc:
        panel.handle_status(tmpdir_path)
    assert exc.value.code == 0

def test_handle_status_running(panel, tmpdir_path):
    import fcntl
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path(tmpdir_path)
    fd = open(lp, "w")
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fd.write(f"{os.getpid()}\n")
    fd.flush()
    try:
        with pytest.raises(SystemExit) as exc:
            panel.handle_status(tmpdir_path)
        assert exc.value.code == 0
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        try:
            os.remove(lp)
        except OSError:
            pass

def test_handle_stop_no_running(panel, tmpdir_path):
    panel.PROJECT_DIR = tmpdir_path
    with pytest.raises(SystemExit) as exc:
        panel.handle_stop(tmpdir_path)
    assert exc.value.code == 0

def test_handle_stop_creates_stop_file(panel, tmpdir_path):
    import fcntl
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path(tmpdir_path)
    fd = open(lp, "w")
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fd.write(f"{os.getpid()}\n")
    fd.flush()
    try:
        sp = panel._stop_path(tmpdir_path)
        with pytest.raises(SystemExit) as exc:
            panel.handle_stop(tmpdir_path)
        assert exc.value.code == 0
        assert os.path.exists(sp)
        os.remove(sp)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        try:
            os.remove(lp)
        except OSError:
            pass

def test_handle_kill_no_running(panel, tmpdir_path):
    panel.PROJECT_DIR = tmpdir_path
    with pytest.raises(SystemExit) as exc:
        panel.handle_kill(tmpdir_path)
    assert exc.value.code == 0

def test_handle_kill_stale_lock_wrong_process(panel, tmpdir_path):
    # Lock file with PID 1 (init) — should clean up stale lock
    panel.PROJECT_DIR = tmpdir_path
    lp = panel._lock_path(tmpdir_path)
    with open(lp, "w") as f:
        f.write("1\n")
    with pytest.raises(SystemExit):
        panel.handle_kill(tmpdir_path)
    # Lock should be cleaned up
    assert not os.path.exists(lp)

def test_handle_list_crons_no_cron(panel):
    # Should not crash with no crontab
    with pytest.raises(SystemExit) as exc:
        panel.handle_list_crons()
    assert exc.value.code == 0
