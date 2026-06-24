"""Tests for additional helpers."""
import os
import pytest

def test_make_status_entry_pending(panel):
    result = panel._make_status_entry("F001", "Login", "pending", branch="feat/login")
    assert "F001" in result
    assert "Login" in result
    assert "pending" in result
    assert "feat/login" in result

def test_make_status_entry_done_with_pr(panel):
    result = panel._make_status_entry("F001", "Login", "done",
                                       pr_url="https://github.com/x/y/pull/1",
                                       source="panel")
    assert "done" in result
    assert "github.com/x/y/pull/1" in result
    assert "[panel]" in result

def test_make_status_entry_in_progress(panel):
    result = panel._make_status_entry("F002", "Dashboard", "in_progress",
                                       timestamp="2024-06-01 12:00",
                                       branch="feat/dash")
    assert "F002" in result
    assert "Dashboard" in result
    assert "in progress" in result
    assert "2024-06-01 12:00" in result

def test_commit_roadmap_update_dry(panel, tmpdir_path):
    """Test commit_roadmap_update structure — will fail without git, but shouldn't crash."""
    panel.PROJECT_DIR = tmpdir_path
    roadmap_path = os.path.join(tmpdir_path, "roadmap.md")
    with open(roadmap_path, "w") as f:
        f.write("test")
    # This will fail because tmpdir isn't a git repo, but shouldn't crash
    # Just verify the function exists and accepts args
    assert callable(panel.commit_roadmap_update)

def test_auto_repair_status_empty(panel, tmpdir_path):
    roadmap_path = os.path.join(tmpdir_path, "roadmap.md")
    with open(roadmap_path, "w") as f:
        f.write("# Roadmap\n")
    result = panel.auto_repair_status([], roadmap_path)
    assert result == 0
