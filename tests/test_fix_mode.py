"""Tests for --fix mode: BLOCKED PR discovery, blocker extraction, flag, dispatch."""
import os
import sys
from unittest.mock import patch

from conftest import _load_panel as _load


# ═══════════════════════════════════════════════════════════════════
# Task 3: discover_blocked_pr()
# ═══════════════════════════════════════════════════════════════════


def test_discover_blocked_pr_none(panel):
    """No BLOCKED PRs → returns None."""
    mock_stdout = ""
    with patch.object(panel, 'gh', return_value=(mock_stdout, "", 0)):
        result = panel.discover_blocked_pr()
        assert result is None


def test_discover_blocked_pr_found(panel):
    """One BLOCKED PR detected by title [BLOCKED] → returns dict."""
    import json as _json
    pr = {"number": 42, "title": "[BLOCKED] Fix login bug", "body": "PR body",
          "headRefName": "feat/fix-login", "updatedAt": "2026-06-25T10:00:00Z"}
    stdout = _json.dumps([pr])
    with patch.object(panel, 'gh', return_value=(stdout, "", 0)):
        result = panel.discover_blocked_pr()
        assert result is not None
        assert result["number"] == 42
        assert result["headRefName"] == "feat/fix-login"


def test_discover_blocked_pr_detects_verdict(panel):
    """PR has VERDICT: BLOCKED in body → detected."""
    import json as _json
    pr_data = {"number": 7, "title": "Some feature",
               "body": "## Review\n**Verdict:** BLOCKED",
               "headRefName": "feat/some", "updatedAt": "2026-06-25T09:00:00Z"}
    stdout = _json.dumps([pr_data])
    with patch.object(panel, 'gh', return_value=(stdout, "", 0)):
        result = panel.discover_blocked_pr()
        assert result is not None
        assert result["number"] == 7


def test_discover_blocked_pr_detects_blockers_section(panel):
    """PR has ### Blockers section → detected as BLOCKED."""
    import json as _json
    pr_data = {"number": 13, "title": "Some feature",
               "body": "### Blockers\n- Bug here",
               "headRefName": "feat/some", "updatedAt": "2026-06-25T08:00:00Z"}
    stdout = _json.dumps([pr_data])
    with patch.object(panel, 'gh', return_value=(stdout, "", 0)):
        result = panel.discover_blocked_pr()
        assert result is not None
        assert result["number"] == 13


def test_discover_blocked_pr_multiple(panel):
    """Multiple BLOCKED PRs → picks most recent (first in sorted array)."""
    import json as _json
    pr_list = [
        {"number": 11, "title": "[BLOCKED] New one", "body": "",
         "headRefName": "feat/new", "updatedAt": "2026-06-25T10:00:00Z"},
        {"number": 10, "title": "[BLOCKED] Old one", "body": "",
         "headRefName": "feat/old", "updatedAt": "2026-06-24T10:00:00Z"},
    ]
    stdout = _json.dumps(pr_list)
    with patch.object(panel, 'gh', return_value=(stdout, "", 0)):
        result = panel.discover_blocked_pr()
        assert result is not None
        assert result["number"] == 11  # First in sorted array = most recent


# ═══════════════════════════════════════════════════════════════════
# Task 4: extract_blockers_from_pr()
# ═══════════════════════════════════════════════════════════════════


def test_extract_blockers_standard_section(panel):
    """### Blockers section → extracts list items."""
    pr_body = """## Review
**Verdict:** BLOCKED

### Blockers
- Login test fails
- Missing error handling
"""
    result = panel.extract_blockers_from_pr(pr_body)
    assert len(result) == 2
    assert "Login test fails" in result


def test_extract_blockers_empty(panel):
    """No blockers found → returns empty list."""
    pr_body = "## Review\n**Verdict:** BLOCKED\n"
    result = panel.extract_blockers_from_pr(pr_body)
    assert result == []


def test_extract_blockers_no_blockers_section(panel):
    """No ### Blockers section → returns empty (caller handles)."""
    pr_body = "Just some PR description."
    result = panel.extract_blockers_from_pr(pr_body)
    assert result == []


def test_extract_blockers_architectural_filtered(panel):
    """ARCHITECTURAL blockers are excluded from result."""
    pr_body = """## Review
**Verdict:** BLOCKED

### Blockers
- Login test fails
- ARCHITECTURAL: Need to restructure DB schema
"""
    result = panel.extract_blockers_from_pr(pr_body)
    assert len(result) == 1
    assert "Login test fails" in result


def test_extract_blockers_all_architectural(panel):
    """All architectural → returns empty list (caller checks separately)."""
    pr_body = """## Review
**Verdict:** BLOCKED

### Blockers
- ARCHITECTURAL: Redesign the whole system
"""
    result = panel.extract_blockers_from_pr(pr_body)
    assert result == []


# ═══════════════════════════════════════════════════════════════════
# Task 1+2: --fix flag parsing and dispatch to run_fix_mode
# ═══════════════════════════════════════════════════════════════════


def test_fix_flag_dispatches_to_run_fix_mode(panel, tmpdir):
    """--fix flag should dispatch to run_fix_mode()."""
    import subprocess
    import json as _json
    project_dir = os.path.join(str(tmpdir), "proj")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)
    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test\n\n## Commands\n- Test: `echo ok`\n- Build: `echo ok`\n")
    subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "config", "user.email", "t@t.com"])
    subprocess.run(["git", "-C", project_dir, "config", "user.name", "T"])
    subprocess.run(["git", "-C", project_dir, "add", "-A"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "commit", "-m", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "remote", "add", "origin", "https://github.com/t/t.git"])

    old_argv = sys.argv
    old_cwd = os.getcwd
    run_fix_args = []
    try:
        sys.argv = ['dokima', '--fix', project_dir]

        def mock_run_fix(**kwargs):
            run_fix_args.append(kwargs.get('project_dir', ''))

        with patch.object(panel, 'acquire_lock', return_value=(None, None)):
            with patch.object(panel._pipeline, 'run_fix_mode', side_effect=mock_run_fix):
                with patch.object(panel, 'load_key', return_value="test-key"):
                    with patch.object(panel, 'detect_repo', return_value="t/t"):
                        with patch.object(panel, '_set_gh_token'):
                            with patch.object(panel, 'detect_commands', return_value=("echo test", "echo build", "echo lint")):
                                panel.main()

        assert len(run_fix_args) == 1
        assert run_fix_args[0] == project_dir
    finally:
        sys.argv = old_argv


def test_fix_mode_skips_auto_archive(panel, tmpdir):
    """--fix should skip auto-archive block."""
    import subprocess
    project_dir = os.path.join(str(tmpdir), "proj2")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)
    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test\n\n## Commands\n- Test: `echo ok`\n- Build: `echo ok`\n")
    subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "config", "user.email", "t@t.com"])
    subprocess.run(["git", "-C", project_dir, "config", "user.name", "T"])
    subprocess.run(["git", "-C", project_dir, "add", "-A"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "commit", "-m", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "remote", "add", "origin", "https://github.com/t/t.git"])

    old_argv = sys.argv
    archive_called = [False]
    try:
        sys.argv = ['dokima', '--fix', project_dir]

        # Track if auto-archive block runs
        with patch.object(panel, 'acquire_lock', return_value=(None, None)):
            with patch.object(panel._pipeline, 'run_fix_mode'):
                with patch.object(panel, 'load_key', return_value="test-key"):
                    with patch.object(panel, 'detect_repo', return_value="t/t"):
                        with patch.object(panel, '_set_gh_token'):
                            with patch.object(panel, 'detect_commands', return_value=("echo test", "echo build", "echo lint")):
                                # Monkey-patch os.listdir to detect if auto-archive runs
                                original_listdir = os.listdir
                                def tracking_listdir(path):
                                    if 'specs' in path:
                                        archive_called[0] = True
                                    return original_listdir(path)
                                with patch('os.listdir', side_effect=tracking_listdir):
                                    panel.main()
        # Archive should NOT have been called for fix mode
        assert not archive_called[0], "Auto-archive should be skipped in fix mode"
    finally:
        sys.argv = old_argv


def test_fix_answers_warning(panel):
    """--fix + --answers should warn and ignore answers file."""
    from io import StringIO
    import contextlib
    old_argv = sys.argv
    captured = []
    try:
        sys.argv = ['dokima', '--fix', '--answers', '/nonexistent/answers.json']
        with patch.object(panel, 'acquire_lock', return_value=(None, None)):
            with patch.object(panel._pipeline, 'run_fix_mode'):
                with patch.object(panel, 'load_key', return_value="test-key"):
                    with patch.object(panel, 'detect_repo', return_value="t/t"):
                        with patch.object(panel, '_set_gh_token'):
                            with patch.object(panel, 'detect_commands', return_value=("echo test", "echo build", "echo lint")):
                                with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                                    panel.main()
                                    captured.append(mock_stdout.getvalue())
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv

    output = "".join(captured)
    # Should not crash — at minimum no "ERROR: Feature description required" from fix mode path
    assert "ERROR" not in output or "answers" not in output


# ═══════════════════════════════════════════════════════════════════
# Task 5+6+7: run_fix_mode() orchestrator
# ═══════════════════════════════════════════════════════════════════


def test_run_fix_mode_discover_none(panel):
    """No BLOCKED PR → prints message, returns."""
    with patch.object(panel, 'discover_blocked_pr', return_value=None):
        with patch.object(panel, 'gh'):
            panel.run_fix_mode("/tmp/test")
            panel.gh.assert_not_called()


def test_run_fix_mode_extracts_blockers(panel):
    """Happy path: discovers PR, extracts blockers, proceeds."""
    mock_pr = {"number": 42, "title": "[BLOCKED] Fix bug", "headRefName": "feat/fix-bug",
               "body": "## Review\n**Verdict:** BLOCKED\n\n### Blockers\n- Login fails\n- Tests broken", "updatedAt": "2026-06-25T10:00:00Z"}
    # Mock gh for PR view (not merged, not closed) and git
    def mock_gh(*args, **kwargs):
        if "view" in args and "--json" in args:
            return ('{"state": "OPEN", "merged": false}', "", 0)
        return ("", "", 0)
    with patch.object(panel, 'discover_blocked_pr', return_value=mock_pr):
        with patch.object(panel, 'gh', side_effect=mock_gh):
            with patch.object(panel, 'git'):
                with patch.object(panel._pipeline, 'run_phase2_coder', return_value={"coder_failed": False, "pr_url": "https://github.com/t/t/pull/42"}):
                    with patch.object(panel._pipeline, 'run_phase3_vet', return_value={"nm_output": "", "pr_url": "", "coder_failed": False, "verdict": "APPROVED"}):
                        with patch.object(panel._pipeline, 'run_phase4_nm', return_value={"nm_ok": True, "pr_url": "", "risk": "LOW"}):
                            with patch.object(panel._pipeline, 'run_phase5_tech_lead', return_value={"verdict": "APPROVED", "tl_output": "All good"}):
                                with patch.dict(os.environ, {"PANEL_SKIP_HUMAN_GATE": "1"}):
                                    with patch('sys.stdout'):
                                        panel.run_fix_mode("/tmp/test")


def test_run_fix_mode_merged_pr(panel):
    """PR is already merged → exits with message."""
    mock_pr = {"number": 42, "title": "[BLOCKED] Merged PR", "headRefName": "feat/merged",
               "body": "", "updatedAt": "2026-06-25T10:00:00Z"}
    def mock_gh(*args, **kwargs):
        if "view" in args and "--json" in args:
            return ('{"state": "OPEN", "merged": true}', "", 0)
        return ("", "", 0)
    with patch.object(panel, 'discover_blocked_pr', return_value=mock_pr):
        with patch.object(panel, 'gh', side_effect=mock_gh):
            with patch.dict(os.environ, {"PANEL_SKIP_HUMAN_GATE": "1"}):
                with patch('sys.stdout'):
                    panel.run_fix_mode("/tmp/test")
    # Should not crash


def test_run_fix_mode_no_blockers(panel):
    """PR has no blockers → prints message."""
    mock_pr = {"number": 42, "title": "[BLOCKED] No blockers", "headRefName": "feat/none",
               "body": "## Review\n**Verdict:** BLOCKED", "updatedAt": "2026-06-25T10:00:00Z"}
    def mock_gh(*args, **kwargs):
        if "view" in args and "--json" in args:
            return ('{"state": "OPEN", "merged": false}', "", 0)
        return ("", "", 0)
    with patch.object(panel, 'discover_blocked_pr', return_value=mock_pr):
        with patch.object(panel, 'gh', side_effect=mock_gh):
            with patch.dict(os.environ, {"PANEL_SKIP_HUMAN_GATE": "1"}):
                with patch('sys.stdout'):
                    panel.run_fix_mode("/tmp/test")
    # Should not crash


def test_run_fix_mode_architectural_only(panel):
    """All blockers are architectural → exits."""
    mock_pr = {"number": 42, "title": "[BLOCKED] Architectural",
               "headRefName": "feat/arch",
               "body": "## Review\n**Verdict:** BLOCKED\n\n### Blockers\n- ARCHITECTURAL: Redesign everything",
               "updatedAt": "2026-06-25T10:00:00Z"}
    def mock_gh(*args, **kwargs):
        if "view" in args and "--json" in args:
            return ('{"state": "OPEN", "merged": false}', "", 0)
        return ("", "", 0)
    with patch.object(panel, 'discover_blocked_pr', return_value=mock_pr):
        with patch.object(panel, 'gh', side_effect=mock_gh):
            with patch.dict(os.environ, {"PANEL_SKIP_HUMAN_GATE": "1"}):
                with patch('sys.stdout'):
                    panel.run_fix_mode("/tmp/test")
    # Should not crash


# ═══════════════════════════════════════════════════════════════════
# Task 8: --fix in help text
# ═══════════════════════════════════════════════════════════════════


def test_help_text_includes_fix(panel):
    """--fix should appear in HELP_TEXT."""
    assert "--fix" in panel.HELP_TEXT or "dokima --fix" in panel.HELP_TEXT

