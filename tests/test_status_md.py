"""Tests for _parse_status_md() and update_status_md()."""
import os
import pytest

def test_empty_status_file(panel, tmpdir_path):
    status_path = os.path.join(tmpdir_path, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n\n## Archived\n")
    header, active, archived = panel._parse_status_md(status_path)
    assert isinstance(header, str)
    assert active == []
    assert archived == []

def test_single_active_entry(panel, tmpdir_path):
    status_path = os.path.join(tmpdir_path, "STATUS.md")
    content = """# Specs Status

## Active
| F001 | Login | in_progress | 2024-01-15 10:00 | feat/login | [panel] |

## Archived
"""
    with open(status_path, "w") as f:
        f.write(content)
    header, active, archived = panel._parse_status_md(status_path)
    assert len(active) >= 1

def test_update_existing_entry(panel, tmpdir_path):
    status_path = os.path.join(tmpdir_path, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n| F001 | Login | pending | - | - | [panel] |\n\n## Archived\n")
    panel.update_status_md(status_path, "F001", "Login", "in_progress", branch="feat/login")
    with open(status_path) as f:
        new_content = f.read()
    # update_status_md creates a new entry line below the table
    assert "in progress" in new_content
    assert "feat/login" in new_content

def test_new_entry_appended(panel, tmpdir_path):
    status_path = os.path.join(tmpdir_path, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n\n## Archived\n")
    panel.update_status_md(status_path, "F001", "Login", "pending", branch="feat/login")
    with open(status_path) as f:
        content = f.read()
    assert "F001" in content
    assert "Login" in content

def test_timestamp_auto_generated(panel, tmpdir_path):
    status_path = os.path.join(tmpdir_path, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n\n## Archived\n")
    panel.update_status_md(status_path, "F001", "Login", "pending")
    with open(status_path) as f:
        content = f.read()
    # Should contain a timestamp like 2024- or 2026-
    import re
    assert re.search(r'\d{4}-\d{2}-\d{2}', content)

def test_pr_link_preserved(panel, tmpdir_path):
    status_path = os.path.join(tmpdir_path, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n| F001 | Login | pending | 2024-01-01 00:00 | feat/login | [panel] |\n\n## Archived\n")
    panel.update_status_md(status_path, "F001", "Login", "done", pr_url="https://github.com/x/y/pull/1")
    with open(status_path) as f:
        content = f.read()
    assert "github.com/x/y/pull/1" in content
    assert "done" in content

def test_source_tag(panel, tmpdir_path):
    status_path = os.path.join(tmpdir_path, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n\n## Archived\n")
    panel.update_status_md(status_path, "F001", "Login", "pending", source="panel")
    with open(status_path) as f:
        content = f.read()
    assert "[panel]" in content
