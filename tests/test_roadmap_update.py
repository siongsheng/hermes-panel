"""Tests for update_roadmap_status()."""
import os
import pytest

def test_pending_to_in_progress(panel, fake_roadmap):
    content = "### F001: Login\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** T.\n"
    p = fake_roadmap(content)
    panel.update_roadmap_status(p, "F001", "in_progress")
    with open(p) as f:
        result = f.read()
    assert "[~] In Progress" in result
    assert "[ ] Pending" not in result

def test_in_progress_to_done(panel, fake_roadmap):
    content = "### F001: Login\n**Priority:** P0\n**Dependencies:** None\n**Status:** [~] In Progress\n**User Story:** T.\n"
    p = fake_roadmap(content)
    panel.update_roadmap_status(p, "F001", "done")
    with open(p) as f:
        result = f.read()
    assert "[x] Done" in result
    assert "[~] In Progress" not in result

def test_done_to_pending_revert(panel, fake_roadmap):
    content = "### F001: Login\n**Priority:** P0\n**Dependencies:** None\n**Status:** [x] Done\n**User Story:** T.\n"
    p = fake_roadmap(content)
    panel.update_roadmap_status(p, "F001", "pending")
    with open(p) as f:
        result = f.read()
    assert "[ ] Pending" in result
    assert "[x] Done" not in result

def test_feature_not_found_no_change(panel, fake_roadmap):
    content = "### F001: Login\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** T.\n"
    p = fake_roadmap(content)
    panel.update_roadmap_status(p, "F999", "done")
    with open(p) as f:
        result = f.read()
    assert result == content  # unchanged

def test_file_not_found_no_crash(panel):
    # Should not raise
    panel.update_roadmap_status("/nonexistent/roadmap.md", "F001", "done")
