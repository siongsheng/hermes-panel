"""Tests for _check_pid() and _verify_pid_owner()."""
import os
import pytest

def test_check_live_pid(panel):
    assert panel._check_pid(str(os.getpid())) is True

def test_check_dead_pid(panel):
    assert panel._check_pid("99999999") is False

def test_check_non_numeric(panel):
    assert panel._check_pid("abc") is False

def test_check_empty_string(panel):
    assert panel._check_pid("") is False

def test_verify_owner_on_self(panel):
    assert panel._verify_pid_owner(os.getpid()) is True

def test_verify_owner_on_init(panel):
    # PID 1 is always init/systemd, not python
    assert panel._verify_pid_owner(1) is False

def test_verify_owner_missing_proc(panel):
    # Non-existent PID should return False
    assert panel._verify_pid_owner(99999999) is False

def test_check_pid_one_is_alive(panel):
    # PID 1 may or may not be signalable depending on container/namespace
    # Test the pattern: if alive, _verify_pid_owner should return False
    if panel._check_pid("1"):
        assert panel._verify_pid_owner(1) is False
    else:
        # PID 1 not signalable — that's fine in containers
        pass
