"""Tests for F002 closure: verify roadmap.md and STATUS.md mark F002 as Done."""

import os
import re

PROJECT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))


def test_f002_marked_done_in_roadmap():
    """F002: Pipeline Integration Tests must be [x] Done in specs/roadmap.md."""
    roadmap_path = os.path.join(PROJECT_DIR, "specs", "roadmap.md")
    assert os.path.exists(roadmap_path), f"roadmap.md not found at {roadmap_path}"

    with open(roadmap_path) as f:
        content = f.read()

    # Verify F002 section exists
    assert "### F002: Pipeline Integration Tests" in content, \
        "F002 section not found in roadmap.md"

    # Extract the F002 block: from F002 header to the next ### or end-of-file
    f002_match = re.search(
        r"### F002: Pipeline Integration Tests\n"
        r"(?:(?!###).*\n)*?"
        r"\*\*Status:\*\* \[x\] Done",
        content,
    )
    assert f002_match is not None, \
        "F002 should be [x] Done in roadmap.md (status line must be within its own ### block)"


def test_f002_recorded_in_status():
    """F002 must be recorded as done in specs/STATUS.md."""
    status_path = os.path.join(PROJECT_DIR, "specs", "STATUS.md")
    assert os.path.exists(status_path), f"STATUS.md not found at {status_path}"

    with open(status_path) as f:
        content = f.read()

    # F002 must appear in the file (Active or Archived section)
    assert "F002" in content, \
        "F002 should be recorded in STATUS.md"

    # F002 must show Done status (either table or bullet format)
    assert "Done" in content, \
        "F002 must show Done status in STATUS.md"
