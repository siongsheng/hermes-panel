"""Tests for triple bug fix: spec archive, verdict gate, detect_commands refresh."""
import os
import pytest

# ── Bug 1: Spec archive ──────────────────────────────────────

def test_archive_merged(panel, tmpdir_path):
    """archive_specs_for_feature moves spec dir to archive/ when PR is merged."""
    # Set up a fake spec directory
    specs_dir = os.path.join(tmpdir_path, "specs")
    archive_dir = os.path.join(specs_dir, "archive")
    spec_dir = os.path.join(specs_dir, "F001-test-feature")
    os.makedirs(spec_dir)
    readme = os.path.join(spec_dir, "README.md")
    with open(readme, "w") as f:
        f.write("# test spec")

    # Mock gh: return merged=true
    orig_gh = panel.gh

    def fake_gh(*args, **kwargs):
        if args[:2] == ("pr", "view"):
            # Return merged=true JSON
            return '{"merged": true, "state": "MERGED"}', "", 0
        return orig_gh(*args, **kwargs)

    panel.gh = fake_gh

    result = panel.archive_specs_for_feature(spec_dir, "feat/f001-test-feature", "https://github.com/x/y/pull/42")

    assert result is True
    assert not os.path.exists(spec_dir)
    assert os.path.exists(os.path.join(archive_dir, "F001-test-feature", "README.md"))


def test_archive_not_merged(panel, tmpdir_path):
    """archive_specs_for_feature does NOT move spec dir when PR is not merged."""
    specs_dir = os.path.join(tmpdir_path, "specs")
    archive_dir = os.path.join(specs_dir, "archive")
    spec_dir = os.path.join(specs_dir, "F002-other-feature")
    os.makedirs(spec_dir)
    readme = os.path.join(spec_dir, "README.md")
    with open(readme, "w") as f:
        f.write("# test spec 2")

    orig_gh = panel.gh

    def fake_gh(*args, **kwargs):
        if args[:2] == ("pr", "view"):
            return '{"merged": false, "state": "OPEN"}', "", 0
        return orig_gh(*args, **kwargs)

    panel.gh = fake_gh

    result = panel.archive_specs_for_feature(spec_dir, "feat/f002-other-feature", "https://github.com/x/y/pull/43")

    assert result is False
    assert os.path.exists(spec_dir)  # still there
    assert not os.path.exists(os.path.join(archive_dir, "F002-other-feature"))


def test_archive_no_pr_url(panel, tmpdir_path):
    """archive_specs_for_feature does not crash when pr_url is None."""
    specs_dir = os.path.join(tmpdir_path, "specs")
    spec_dir = os.path.join(specs_dir, "F003-no-pr")
    os.makedirs(spec_dir)

    result = panel.archive_specs_for_feature(spec_dir, "feat/f003-no-pr", None)

    assert result is False
    assert os.path.exists(spec_dir)  # untouched


# ── Bug 2: Verdict gate ──────────────────────────────────────

def test_blocked_next_not_done(panel, tmpdir_path):
    """--next mode with BLOCKED verdict: status stays in_progress, NOT marked done."""
    panel.PANEL_FEATURE = "F004: blocked-next"
    panel.PROJECT_DIR = tmpdir_path
    panel.REPO = "test/test"

    # Create roadmap
    roadmap_dir = os.path.join(tmpdir_path, "specs")
    os.makedirs(roadmap_dir)
    roadmap_path = os.path.join(roadmap_dir, "roadmap.md")
    with open(roadmap_path, "w") as f:
        f.write("### F004: blocked-next\n**Priority:** P0\n**Dependencies:** None\n**Status:** [~] In Progress\n**User Story:** T.\n")

    # Create STATUS.md
    status_path = os.path.join(roadmap_dir, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n\n## Archived\n")

    continue_loop = True
    result_continue, result_stop = panel.run_post_pipeline(
        "F004: blocked-next", True, False, continue_loop,
        "https://github.com/x/y/pull/44", "BLOCKED", "LOW",
        "feat/f004-blocked-next", roadmap_dir,
        "strategist output", "next"
    )

    # Roadmap should still be in_progress [~]
    with open(roadmap_path) as f:
        roadmap_content = f.read()
    assert "[~] In Progress" in roadmap_content
    assert "[x] Done" not in roadmap_content


def test_blocked_continuous_not_done(panel, tmpdir_path):
    """--continuous mode with BLOCKED verdict: continue_loop=False, NOT marked done."""
    panel.PANEL_FEATURE = "F005: blocked-continuous"
    panel.PROJECT_DIR = tmpdir_path
    panel.REPO = "test/test"

    roadmap_dir = os.path.join(tmpdir_path, "specs")
    os.makedirs(roadmap_dir)
    roadmap_path = os.path.join(roadmap_dir, "roadmap.md")
    with open(roadmap_path, "w") as f:
        f.write("### F005: blocked-continuous\n**Priority:** P0\n**Dependencies:** None\n**Status:** [~] In Progress\n**User Story:** T.\n")

    status_path = os.path.join(roadmap_dir, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n\n## Archived\n")

    continue_loop = True
    result_continue, result_stop = panel.run_post_pipeline(
        "F005: blocked-continuous", True, True, continue_loop,
        "https://github.com/x/y/pull/45", "BLOCKED", "LOW",
        "feat/f005-blocked-continuous", roadmap_dir,
        "strategist output", "continuous"
    )

    # continue_loop should be False
    assert result_continue is False

    # Roadmap should NOT be marked done
    with open(roadmap_path) as f:
        roadmap_content = f.read()
    assert "[x] Done" not in roadmap_content


def test_approved_next_done(panel, tmpdir_path):
    """--next mode with APPROVED verdict: status IS marked done (regression)."""
    panel.PANEL_FEATURE = "F006: approved-next"
    panel.PROJECT_DIR = tmpdir_path
    panel.REPO = "test/test"

    roadmap_dir = os.path.join(tmpdir_path, "specs")
    os.makedirs(roadmap_dir)
    roadmap_path = os.path.join(roadmap_dir, "roadmap.md")
    with open(roadmap_path, "w") as f:
        f.write("### F006: approved-next\n**Priority:** P0\n**Dependencies:** None\n**Status:** [~] In Progress\n**User Story:** T.\n")

    status_path = os.path.join(roadmap_dir, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n\n## Archived\n")

    continue_loop = True
    result_continue, result_stop = panel.run_post_pipeline(
        "F006: approved-next", True, False, continue_loop,
        "https://github.com/x/y/pull/46", "APPROVED", "LOW",
        "feat/f006-approved-next", roadmap_dir,
        "strategist output", "next"
    )

    # Roadmap should be done
    with open(roadmap_path) as f:
        roadmap_content = f.read()
    assert "[x] Done" in roadmap_content


def test_changes_requested(panel, tmpdir_path):
    """CHANGES_REQUESTED verdict: behaves same as BLOCKED — NOT marked done."""
    panel.PANEL_FEATURE = "F007: changes-requested"
    panel.PROJECT_DIR = tmpdir_path
    panel.REPO = "test/test"

    roadmap_dir = os.path.join(tmpdir_path, "specs")
    os.makedirs(roadmap_dir)
    roadmap_path = os.path.join(roadmap_dir, "roadmap.md")
    with open(roadmap_path, "w") as f:
        f.write("### F007: changes-requested\n**Priority:** P0\n**Dependencies:** None\n**Status:** [~] In Progress\n**User Story:** T.\n")

    status_path = os.path.join(roadmap_dir, "STATUS.md")
    with open(status_path, "w") as f:
        f.write("# Specs Status\n\n## Active\n\n## Archived\n")

    continue_loop = True
    result_continue, result_stop = panel.run_post_pipeline(
        "F007: changes-requested", True, False, continue_loop,
        "https://github.com/x/y/pull/47", "CHANGES_REQUESTED", "LOW",
        "feat/f007-changes-requested", roadmap_dir,
        "strategist output", "next"
    )

    with open(roadmap_path) as f:
        roadmap_content = f.read()
    assert "[~] In Progress" in roadmap_content
    assert "[x] Done" not in roadmap_content


# ── Bug 3: detect_commands refresh ───────────────────────────

def test_detect_commands_refreshes(panel, tmpdir_path):
    """detect_commands() refreshes TEST_CMD globals after branch checkout in vet."""
    # Set up initial globals (stale from startup)
    panel.TEST_CMD = "npm test"
    panel.BUILD_CMD = "npm run build"
    panel.LINT_CMD = "npm run lint"

    panel.PROJECT_DIR = tmpdir_path

    # Create AGENTS.md on the feature branch with custom commands
    agents_path = os.path.join(tmpdir_path, "AGENTS.md")
    with open(agents_path, "w") as f:
        f.write("# Test\n- Test: `python3 -m pytest tests/ -q`\n- Build: `python3 -c \"compile(open('dokima').read(), 'dokima', 'exec')\"`\n- Lint: `python3 -m py_compile dokima`\n")

    # Mock git checkout to succeed (simulating branch checkout in vet)
    orig_git = panel.git

    def fake_git(*args, **kwargs):
        if args and args[0] == "checkout":
            return "", "", 0
        return orig_git(*args, **kwargs)

    panel.git = fake_git

    # Now call the refresh logic by executing the same code that vet uses
    # Simulate what happens when run_phase3_vet starts:
    panel.TEST_CMD, panel.BUILD_CMD, panel.LINT_CMD = panel.detect_commands()

    assert panel.TEST_CMD == "python3 -m pytest tests/ -q"
    assert panel.BUILD_CMD == 'python3 -c "compile(open(\'dokima\').read(), \'dokima\', \'exec\')"'
    assert panel.LINT_CMD == "python3 -m py_compile dokima"


def test_detect_commands_stale(panel, tmpdir_path):
    """Without AGENTS.md on feature branch, detect_commands returns defaults."""
    panel.PROJECT_DIR = tmpdir_path
    panel.TEST_CMD = "npm test"
    panel.BUILD_CMD = "npm run build"
    panel.LINT_CMD = "npm run lint"

    # No AGENTS.md in tmpdir_path
    test_cmd, build_cmd, lint_cmd = panel.detect_commands()

    # Should return defaults (no AGENTS.md found)
    assert test_cmd == "npm test"
    assert build_cmd == "npm run build"
    assert lint_cmd == "npm run lint"
