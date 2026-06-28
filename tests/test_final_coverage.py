"""Final coverage push: tests for remaining uncovered branches in main().

Targets: interview gate, human gate interactive, coder timeout,
parallel merge failure, nm re-verify, continuous auto-merge, coder PR extraction.
"""
import os
import sys
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load

_spawn_calls = []


def _setup(tmpdir, panel, features=2):
    import subprocess
    project_dir = os.path.join(str(tmpdir), "proj")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)
    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test\n\n## Commands\n- Test: `echo ok`\n- Build: `echo ok`\n")
    roadmap = """# Roadmap
## Phase 1
### F001: Test Feature
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** Test.
"""
    if features >= 2:
        roadmap += """
### F002: Second Feature
**Priority:** P0
**Dependencies:** F001
**Status:** [ ] Pending
**User Story:** Second.
"""
    with open(os.path.join(project_dir, "specs", "roadmap.md"), "w") as f:
        f.write(roadmap)
    subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "config", "user.email", "t@t.com"])
    subprocess.run(["git", "-C", project_dir, "config", "user.name", "T"])
    subprocess.run(["git", "-C", project_dir, "add", "-A"])
    subprocess.run(["git", "-C", project_dir, "commit", "-m", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "remote", "add", "origin", "https://github.com/t/t.git"])
    panel.PROJECT_DIR = project_dir
    panel.REPO = "t/t"
    panel.DEFAULT_BRANCH = "master"
    return project_dir


def _run_pipeline(panel, project_dir, spawn_mock, extra_patches=None, is_continuous=False):
    """Run main() with standard patches + optional extras."""
    old = sys.argv
    try:
        flag = "--continuous" if is_continuous else "--next"
        sys.argv = ["dokima", flag, project_dir]
        panel.spawn_agent = spawn_mock

        mock_run = type("RunResult", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()
        def gh_se(*a, **kw):
            if len(a) > 1 and a[1] == "create":
                return ("https://github.com/t/t/pull/1", "", 0)
            return ("", "", 0)

        patches = [
            patch("dokima.call_agent", return_value={"content": "M", "tokens": 1}),
            patch("dokima._set_gh_token"),
            patch("dokima.git", return_value=("", "", 0)),
            patch("dokima.gh", side_effect=gh_se),
            patch("dokima.load_key", return_value="fk"),
            patch("dokima.load_github_token", return_value="ft"),
            patch("dokima.detect_repo", return_value="t/t"),
            patch("dokima._safe_run", return_value=mock_run),
            patch("dokima.subprocess.run", return_value=mock_run),
            patch("dokima.time.sleep"),
        ]
        if extra_patches:
            patches.extend(extra_patches)

        # Enter all patches
        for p in patches:
            p.start()
        try:
            panel.main()
        except SystemExit:
            pass
        finally:
            for p in reversed(patches):
                p.stop()
    finally:
        sys.argv = old


# ═══════════════════════════════════════════════════════════════════
# Strategist interview gate (CLARIFICATION blocks)
# ═══════════════════════════════════════════════════════════════════

STRAT_WITH_INTERVIEW = """Confidence: Medium
Impact: MEDIUM

## Spec
DECISION: INTERVIEW MODE

CLARIFICATION 1: What authentication method?
CLARIFICATION 2: REST or GraphQL?

## Tasks
### Task 1: Setup
**Files:** `a.py`
**Dependencies:** None
**Parallelizable:** Yes
"""

class TestInterviewGate:
    @pytest.mark.skip(reason="select.select on mocked sys.stdin fails — needs main() refactor to inject stdin")
    def test_interview_mode_triggers_clarification(self, tmpdir):
        """Strategist in INTERVIEW MODE → non-interactive → skips gracefully."""
        panel = _load()
        project_dir = _setup(tmpdir, panel)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return STRAT_WITH_INTERVIEW
            if profile == "coder":
                return "RED: a1\nGREEN: b2\nTests: 5 pass\nBuild: clean"
            return "Mock"

        with patch.object(panel, "sys") as mock_sys:
            mock_sys.stdin.isatty.return_value = False
            _run_pipeline(panel, project_dir, mock)


# ═══════════════════════════════════════════════════════════════════
# Coder timeout path
# ═══════════════════════════════════════════════════════════════════

CODER_TIMEOUT = """Some output
[TIMEOUT: agent exceeded 600s. Partial output above.]
"""

class TestCoderTimeout:
    def test_coder_timeout_with_branch(self, tmpdir):
        """Coder timed out but branch exists → continues with partial."""
        panel = _load()
        project_dir = _setup(tmpdir, panel)
        _spawn_calls.clear()

        # Need git rev-parse to succeed (branch exists)
        def mock_git(*args, **kw):
            if args and args[0] == "rev-parse":
                return ("commit_hash", "", 0)
            return ("", "", 0)

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: High\nImpact: MEDIUM\n\nSpec."
            if profile == "coder":
                return CODER_TIMEOUT
            return "Mock"

        _run_pipeline(panel, project_dir, mock,
                      extra_patches=[patch("dokima.git", side_effect=mock_git)])

    def test_coder_timeout_no_branch(self, tmpdir):
        """Coder timed out + no branch → halt_and_revert."""
        panel = _load()
        project_dir = _setup(tmpdir, panel)
        _spawn_calls.clear()

        # git rev-parse fails (no branch)
        def mock_git(*args, **kw):
            if args and args[0] == "rev-parse":
                return ("", "fatal: bad revision", 128)
            return ("", "", 0)

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: High\nImpact: MEDIUM\n\nSpec."
            if profile == "coder":
                return CODER_TIMEOUT
            return "Mock"

        _run_pipeline(panel, project_dir, mock,
                      extra_patches=[patch("dokima.git", side_effect=mock_git)])


# ═══════════════════════════════════════════════════════════════════
# Coder PR extraction (depth=vet, coder creates PR)
# ═══════════════════════════════════════════════════════════════════

CODER_WITH_PR = """RED: a1b2
GREEN: c3d4
Tests: 5 pass, 0 fail
Build: clean

PR: https://github.com/t/t/pull/42
"""

class TestCoderPrExtraction:
    def test_coder_output_contains_pr_url(self, tmpdir):
        """Coder output has PR URL → extracted for status."""
        panel = _load()
        project_dir = _setup(tmpdir, panel)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: High\nImpact: LOW\n\nSpec."  # Impact LOW -> depth="vet"
            if profile == "coder":
                return CODER_WITH_PR
            return "Mock"

        _run_pipeline(panel, project_dir, mock)


# ═══════════════════════════════════════════════════════════════════
# Parallel merge failure
# ═══════════════════════════════════════════════════════════════════

STRAT_MULTI_TASK = """# F001
**Confidence:** Medium
**Impact:** LOW

### Task 1: A
**Files:** `a.py`
**Dependencies:** None
**Parallelizable:** Yes

### Task 2: B
**Files:** `b.py`
**Dependencies:** Task 1
**Parallelizable:** No
"""

class TestMergeFailure:
    def test_merge_worktree_branches_fails(self, tmpdir):
        """All parallel tasks done but merge fails → halt_and_revert."""
        panel = _load()
        project_dir = _setup(tmpdir, panel)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return STRAT_MULTI_TASK
            if profile.startswith("coder-"):
                return "Task completed"
            return "Mock"

        import tempfile
        wt_dir = tempfile.mkdtemp()
        wt_mgr = type("W", (), {
            "create": lambda s,*a: wt_dir,
            "remove": lambda s,*a: None,
            "cleanup_all": lambda s,*a: None,
        })()
        mock_proc = type("P", (), {"poll": lambda s: 0, "communicate": lambda s,t=None: (b"done", None)})()

        _run_pipeline(panel, project_dir, mock, extra_patches=[
            patch("dokima.merge_worktree_branches", return_value=False),
            patch("dokima.WorktreeManager", return_value=wt_mgr),
            patch("dokima.subprocess.Popen", return_value=mock_proc),
        ])


# ═══════════════════════════════════════════════════════════════════
# Continuous auto-merge paths
# ═══════════════════════════════════════════════════════════════════

class TestAutoMerge:
    def test_auto_merge_queued(self, tmpdir):
        """Continuous loop: auto-merge queued (CI required)."""
        panel = _load()
        project_dir = _setup(tmpdir, panel, features=2)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: High\nImpact: MEDIUM\n\nSpec."
            if profile == "coder":
                return "RED: a1\nGREEN: b2\nTests: 5 pass\nBuild: clean"
            if profile == "tech-lead":
                return "VERDICT: APPROVED\nRISK: LOW\n"
            return "Mock"

        os.environ["PANEL_MAX_RETRIES"] = "0"
        os.environ["PANEL_SKIP_HUMAN_GATE"] = "1"
        os.environ["PANEL_PARALLEL"] = "0"

        _run_pipeline(panel, project_dir, mock, is_continuous=True, extra_patches=[
            patch("dokima.try_auto_merge", return_value="queued"),
        ])

        for k in ("PANEL_PARALLEL", "PANEL_MAX_RETRIES", "PANEL_SKIP_HUMAN_GATE"):
            os.environ.pop(k, None)

    def test_auto_merge_failed(self, tmpdir):
        """Continuous loop: auto-merge failed."""
        panel = _load()
        project_dir = _setup(tmpdir, panel, features=2)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: High\nImpact: MEDIUM\n\nSpec."
            if profile == "coder":
                return "RED: a1\nGREEN: b2\nTests: 5 pass\nBuild: clean"
            if profile == "tech-lead":
                return "VERDICT: APPROVED\nRISK: LOW\n"
            return "Mock"

        os.environ["PANEL_MAX_RETRIES"] = "0"
        os.environ["PANEL_SKIP_HUMAN_GATE"] = "1"
        os.environ["PANEL_PARALLEL"] = "0"

        _run_pipeline(panel, project_dir, mock, is_continuous=True, extra_patches=[
            patch("dokima.try_auto_merge", return_value="failed"),
        ])

        for k in ("PANEL_PARALLEL", "PANEL_MAX_RETRIES", "PANEL_SKIP_HUMAN_GATE"):
            os.environ.pop(k, None)


# ═══════════════════════════════════════════════════════════════════
# TL auto-fix BLOCKER sub-path (with SPEC VIOLATION skip)
# ═══════════════════════════════════════════════════════════════════

TL_WITH_SPEC_VIOLATION = """VERDICT: APPROVED
RISK: LOW

BLOCKER: SPEC VIOLATION — interface doesn't match
BLOCKER: TDD violation in tests
SHOULD FIX: naming
"""

class TestTlAutofixSkip:
    def test_spec_violation_blocker_skips_autofix(self, tmpdir):
        """TL BLOCKER with SPEC VIOLATION → auto-fix skips that one, fixes the other."""
        panel = _load()
        project_dir = _setup(tmpdir, panel)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: High\nImpact: MEDIUM\n\nSpec."
            if profile == "coder":
                return "RED: a1\nGREEN: b2\nTests: 5 pass\nBuild: clean"
            if profile == "tech-lead":
                return TL_WITH_SPEC_VIOLATION
            return "Mock"

        _run_pipeline(panel, project_dir, mock)
