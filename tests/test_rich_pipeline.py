"""Rich pipeline integration tests — varied mock outputs to exercise
different paths through main().

Tests parallel coders, vet failure recovery, continuous loop, and error paths.
"""
import os
import sys
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load

os.environ.setdefault("PANEL_MAX_RETRIES", "0")
os.environ.setdefault("PANEL_SKIP_HUMAN_GATE", "1")

_spawn_calls = []


def _setup_project(tmpdir, panel, features=1):
    """Create a git project with roadmap for testing."""
    import subprocess
    project_dir = os.path.join(str(tmpdir), "test-project")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)
    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test\n\n## Commands\n- Test: `echo tests-pass`\n- Build: `echo build-ok`\n")
    if features == 1:
        roadmap = """# Roadmap

## Phase 1

### F001: Test Feature
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** Pipeline verification.
"""
    else:
        roadmap = """# Roadmap

## Phase 1

### F001: First Feature
**Priority:** P0
**Dependencies:** None
**Status:** [ ] Pending
**User Story:** First.

### F002: Second Feature
**Priority:** P0
**Dependencies:** F001
**Status:** [ ] Pending
**User Story:** Second.
"""
    with open(os.path.join(project_dir, "specs", "roadmap.md"), "w") as f:
        f.write(roadmap)
    subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "config", "user.email", "test@test.com"])
    subprocess.run(["git", "-C", project_dir, "config", "user.name", "Test"])
    subprocess.run(["git", "-C", project_dir, "add", "-A"])
    subprocess.run(["git", "-C", project_dir, "commit", "-m", "init"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "-C", project_dir, "remote", "add", "origin", "https://github.com/test-owner/test-repo.git"])
    panel.PROJECT_DIR = project_dir
    panel.REPO = "test-owner/test-repo"
    panel.DEFAULT_BRANCH = "master"
    return project_dir


def _apply_rich_patches(fn):
    """Pipeline patch decorator with configurable mock outputs."""
    def wrapper(*args, **kwargs):
        mock_run = type("RunResult", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        # gh: return empty for pr list (no existing PR), URL for pr create
        def gh_side_effect(*args, **kwargs):
            if args and args[0] == "pr" and args[1] == "create":
                return ("https://github.com/t/t/pull/1", "", 0)
            return ("", "", 0)
        # Mock subprocess.Popen for parallel coders
        mock_proc = type("MockProc", (), {
            "poll": lambda self: 0,
            "communicate": lambda self, timeout=None: (b"Mock task output", None),
            "stdout": None,
            "stderr": None,
        })()
        mock_subprocess_run = type("RunResult", (), {"returncode": 0, "stdout": "mock", "stderr": ""})()
        with patch("dokima._agent.call_agent", return_value={"content": "M", "tokens": 1}), \
             patch("dokima._set_gh_token"), \
             patch("dokima.git", return_value=("", "", 0)), \
             patch("dokima.gh", side_effect=gh_side_effect), \
             patch("dokima.load_key", return_value="fk"), \
             patch("dokima.load_github_token", return_value="ft"), \
             patch("dokima.detect_repo", return_value="t/t"), \
             patch("dokima._safe_run", return_value=mock_run), \
             patch("dokima.subprocess.Popen", return_value=mock_proc), \
             patch("dokima.subprocess.run", return_value=mock_subprocess_run), \
             patch("dokima.time.sleep"):
            return fn(*args, **kwargs)
    return wrapper


# ── Strategist output with parallel tasks ──

STRAT_WITH_TASKS = """# F001: Test Feature

**Confidence:** High
**Impact:** LOW

## Task Breakdown

### Task 1: Add slugify function
**Files:** `src/utils.py`
**Dependencies:** None
**Parallelizable:** Yes

Create a slugify function that normalizes strings.

### Task 2: Add tests for slugify
**Files:** `tests/test_utils.py`
**Dependencies:** Task 1
**Parallelizable:** No

Write unit tests for the slugify function.
"""

# ── Coder output that passes the post-coder gate ──

CODER_PASSING = """RED commit: abc1234 — test: add slugify tests
GREEN commit: def5678 — feat: add slugify function

Tests: 5 passed, 0 failed
Build: clean, 0 errors

Branch: feat/f001-test-feature
"""

# ── Coder output with clarifications ──

CODER_WITH_CLARIFICATIONS = """RED commit: abc1234 — test: add tests
GREEN commit: def5678 — feat: implement

CLARIFICATION NEEDED: Should the API use REST or GraphQL?
CLARIFICATION NEEDED: What auth method?

Tests: 3 passed, 0 failed
Build: clean
"""


class TestParallelCoders:
    """Pipeline with parallel coders (strategist output has tasks)."""

    @_apply_rich_patches
    def _run(self, panel, project_dir, mock_spawn_fn, argv=None):
        old = sys.argv
        try:
            sys.argv = argv or ["dokima", "--next", project_dir]
            panel.spawn_agent = mock_spawn_fn
            try:
                panel.main()
            except SystemExit:
                pass
        finally:
            sys.argv = old

    def test_parallel_coders_with_tasks(self, tmpdir):
        """Strategist returns tasks → enters parallel coders path via Popen, not spawn_agent."""
        panel = _load()
        project_dir = _setup_project(tmpdir, panel)
        _spawn_calls.clear()

        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return STRAT_WITH_TASKS
            if profile == "coder" or profile.startswith("coder-"):
                return CODER_PASSING
            return "Mock output"

        # Also need to mock merge_worktree_branches which does real git ops
        import tempfile
        wt_dir = tempfile.mkdtemp()
        wt_mgr_instance = type("MockWT", (), {
            "create": lambda self, *a, **kw: wt_dir,
            "remove": lambda self, *a, **kw: None,
            "cleanup_all": lambda self, *a, **kw: None,
        })()
        with patch("dokima._tasks.merge_worktree_branches", return_value=True), \
             patch("dokima.WorktreeManager", return_value=wt_mgr_instance):
            self._run(panel, project_dir, mock)

        # Parallel coders use subprocess.Popen, not spawn_agent.
        # The pipeline should still complete with strategist + tech-lead phases.
        assert "strategist" in _spawn_calls, f"Strategist not called: {_spawn_calls}"
        assert "tech-lead" in _spawn_calls, f"Tech lead not called (pipeline should run phases 1-5): {_spawn_calls}"


class TestVetFailure:
    """Vet phase when tests or build fail → coder fix loop."""

    def test_vet_failure_triggers_coder_fix(self, tmpdir):
        """_safe_run returns failure → vet loop spawns coder to fix."""
        panel = _load()
        project_dir = _setup_project(tmpdir, panel)
        _spawn_calls.clear()

        # Coder passes the gate to reach vet
        def mock(profile, skills, prompt, timeout=600, cwd=None, **kwargs):
            _spawn_calls.append(profile)
            if profile == "strategist":
                return "Confidence: High\nImpact: MEDIUM\n\nSpec for test feature."
            if profile == "coder" or profile == "fix":
                return CODER_PASSING
            return "Mock"

        old = sys.argv
        try:
            sys.argv = ["dokima", "--next", project_dir]
            panel.spawn_agent = mock

            # _safe_run returns failure for test → triggers fix loop
            mock_fail = type("RunResult", (), {"returncode": 1, "stdout": "0 passed, 2 failed", "stderr": ""})()
            mock_ok = type("RunResult", (), {"returncode": 0, "stdout": "5 passed", "stderr": ""})()
            safe_results = [mock_fail, mock_ok, mock_ok, mock_ok]  # test fail, build ok, retry test ok, build ok
            call_count = [0]

            def safe_run_side_effect(*args, **kwargs):
                idx = call_count[0]
                call_count[0] += 1
                if idx < len(safe_results):
                    return safe_results[idx]
                return mock_ok

            def gh_side_effect(*args, **kwargs):
                if args and args[0] == "pr" and args[1] == "create":
                    return ("https://github.com/t/t/pull/1", "", 0)
                return ("", "", 0)

            mock_run = type("RunResult", (), {"returncode": 0, "stdout": "mock", "stderr": ""})()

            with patch("dokima._agent.call_agent", return_value={"content": "M", "tokens": 1}), \
                 patch("dokima._set_gh_token"), \
                 patch("dokima.git", return_value=("", "", 0)), \
                 patch("dokima.gh", side_effect=gh_side_effect), \
                 patch("dokima.load_key", return_value="fk"), \
                 patch("dokima.load_github_token", return_value="ft"), \
                 patch("dokima.detect_repo", return_value="t/t"), \
                 patch("dokima._safe_run", side_effect=safe_run_side_effect), \
                 patch("dokima.subprocess.run", return_value=mock_run), \
                 patch("dokima.time.sleep"), \
                 patch("dokima.sys.stdin.isatty", return_value=False):
                try:
                    panel.main()
                except SystemExit:
                    pass
        finally:
            sys.argv = old

        # With vet failure, coder should be re-spawned for fix
        # "coder" appears at least twice: initial + fix
        coder_count = sum(1 for c in _spawn_calls if c == "coder")
        assert coder_count >= 2, f"Expected >=2 coder calls (initial+fix), got {coder_count}: {_spawn_calls}"
