"""Tests for _lock_path() and _stop_path() — per-project file paths."""
import pytest

def test_explicit_project_dir_lock(panel):
    result = panel._lock_path("/home/user/my-project")
    assert result == "/tmp/dokima-my-project.lock"

def test_explicit_project_dir_stop(panel):
    result = panel._stop_path("/home/user/my-project")
    assert result == "/tmp/dokima-my-project.stop"

def test_implicit_from_global(panel):
    panel.PROJECT_DIR = "/home/user/foo"
    result = panel._lock_path()
    assert result == "/tmp/dokima-foo.lock"

def test_trailing_slash_normalized(panel):
    result = panel._lock_path("/home/user/project/")
    assert result == "/tmp/dokima-project.lock"

def test_no_project_dir_no_arg(panel):
    # Simulate missing PROJECT_DIR by temporarily deleting from utils module
    old = panel._utils.PROJECT_DIR
    try:
        del panel._utils.PROJECT_DIR
        result = panel._lock_path()
        assert "unknown" in result
        assert result.endswith(".lock")
    finally:
        panel._utils.PROJECT_DIR = old

def test_stop_path_mirrors_lock_path(panel):
    lock = panel._lock_path("/tmp/bar")
    stop = panel._stop_path("/tmp/bar")
    assert lock.replace(".lock", ".stop") == stop
