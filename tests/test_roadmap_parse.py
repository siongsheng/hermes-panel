"""Tests for parse_roadmap() — regex-based roadmap.md extraction."""
import os
import pytest

ROADMAP_TEMPLATE = """# Roadmap

## Phase 1: Foundation

### F001: User Authentication
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a user, I can log in.

### F002: Dashboard
**Priority:** P1
**Dependencies:** F001
**Status:** [ ] Pending
**User Story:** As a user, I see my dashboard.

## Phase 2: Advanced

### F003: Export Reports
**Priority:** P2
**Dependencies:** F001, F002
**Status:** [ ] Pending
**User Story:** As a user, I can export data.
"""

def test_file_not_found(panel):
    result = panel.parse_roadmap("/nonexistent/roadmap.md")
    assert result == []

def test_empty_file(panel, fake_roadmap):
    p = fake_roadmap("\n\n")
    result = panel.parse_roadmap(p)
    assert result == []

def test_single_feature_all_fields(panel, fake_roadmap):
    content = """### F001: Login
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a user, I can log in.
"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert len(result) == 1
    f = result[0]
    assert f.id == "F001"
    assert f.title == "Login"
    assert f.priority == "P0"
    assert f.dependencies == []
    assert f.status == "pending"
    assert "log in" in f.story

def test_multiple_features(panel, fake_roadmap):
    p = fake_roadmap(ROADMAP_TEMPLATE)
    result = panel.parse_roadmap(p)
    assert len(result) == 3
    assert [f.id for f in result] == ["F001", "F002", "F003"]

def test_dependencies_none(panel, fake_roadmap):
    content = """### F001: Test
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** Test.
"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].dependencies == []

def test_dependencies_empty(panel, fake_roadmap):
    content = """### F001: Test
**Priority:** P0
**Dependencies:**
**Status:** [ ] Pending
**User Story:** Test.
"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].dependencies == []

def test_dependencies_multiple(panel, fake_roadmap):
    content = """### F001: Test
**Priority:** P0
**Dependencies:** F002, F003, F004
**Status:** [ ] Pending
**User Story:** Test.
"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].dependencies == ["F002", "F003", "F004"]

def test_status_pending(panel, fake_roadmap):
    content = """### F001: Test\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** T.\n"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].status == "pending"

def test_status_in_progress(panel, fake_roadmap):
    content = """### F001: Test\n**Priority:** P0\n**Dependencies:** None\n**Status:** [~] In Progress\n**User Story:** T.\n"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].status == "in_progress"

def test_status_done(panel, fake_roadmap):
    content = """### F001: Test\n**Priority:** P0\n**Dependencies:** None\n**Status:** [x] Done\n**User Story:** T.\n"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].status == "done"

def test_missing_status_defaults_pending(panel, fake_roadmap):
    content = """### F001: Test\n**Priority:** P0\n**Dependencies:** None\n**User Story:** T.\n"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].status == "pending"

def test_missing_priority_defaults_p2(panel, fake_roadmap):
    content = """### F001: Test\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** T.\n"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].priority == "P2"

def test_missing_dependencies_defaults_empty(panel, fake_roadmap):
    content = """### F001: Test\n**Priority:** P0\n**Status:** [ ] Pending\n**User Story:** T.\n"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].dependencies == []

def test_section_detection(panel, fake_roadmap):
    p = fake_roadmap(ROADMAP_TEMPLATE)
    result = panel.parse_roadmap(p)
    assert result[0].section == "Phase 1: Foundation"
    assert result[2].section == "Phase 2: Advanced"

def test_features_across_sections(panel, fake_roadmap):
    content = """## Phase 1\n### F001: A\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** A.\n\n## Phase 2\n### F002: B\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** B.\n"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].section == "Phase 1"
    assert result[1].section == "Phase 2"

def test_malformed_id_not_parsed(panel, fake_roadmap):
    content = """### F01: Short ID\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** T.\n\n### F001: Valid\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** T.\n"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert len(result) == 1
    assert result[0].id == "F001"

def test_inline_code_in_title(panel, fake_roadmap):
    content = "### F001: Fix `auth` module\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** T.\n"
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert result[0].title == "Fix `auth` module"

def test_multiline_user_story(panel, fake_roadmap):
    content = """### F001: Login
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** As a user, I can log in with my email and password securely.
"""
    p = fake_roadmap(content)
    result = panel.parse_roadmap(p)
    assert "email" in result[0].story
