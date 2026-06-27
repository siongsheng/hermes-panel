"""Integration tests for main() orchestration logic.

Mocks spawn_agent via direct assignment (exec-loaded module constraint).
"""
import os
import sys
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load

os.environ.setdefault("PANEL_MAX_RETRIES", "0")
os.environ.setdefault("PANEL_SKIP_HUMAN_GATE", "1")


def _setup_test_project(panel, tmpdir):
    import subprocess
    project_dir = os.path.join(str(tmpdir), "test-project")
    os.makedirs(os.path.join(project_dir, "specs"), exist_ok=True)
    with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
        f.write("# Test Project\n\n## Commands\n- Test: `echo tests-pass`\n- Build: `echo build-ok`\n")
    with open(os.path.join(project_dir, "specs", "roadmap.md"), "w") as f:
        f.write("""# Roadmap\n\n## Phase 1\n\n### F001: Test Feature\n**Priority:** P0\n**Dependencies:** None\n**Status:** [ ] Pending\n**User Story:** Pipeline verification.\n""")
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


_spawn_calls = []

def _mock_spawn(profile, skills, prompt, timeout=600, cwd=None):
    _spawn_calls.append(profile)
    return "Mock agent output"


def _patch_and_run(panel, mock_lock=True):
    """Run panel.main() with all standard patches applied."""
    patches = [
        patch.object(panel, "call_agent", return_value={"content": "M", "tokens": 1}),
        patch.object(panel, "_set_gh_token"),
        patch.object(panel, "git", return_value=("", "", 0)),
        patch.object(panel, "gh", return_value=("", "", 0)),
        patch.object(panel, "load_key", return_value="fk"),
        patch.object(panel, "load_github_token", return_value="ft"),
        patch.object(panel, "detect_repo", return_value="t/t"),
        patch("time.sleep"),  # skip retry/backoff delays
    ]
    if mock_lock:
        patches.append(patch.object(panel, "acquire_lock", return_value=(True, None)))
        patches.append(patch.object(panel, "_cleanup_lock"))

    # Use ExitStack for clean nested context managers
    from contextlib import ExitStack
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        try:
            panel.main()
        except SystemExit:
            pass


class TestMainEarlyExits:

    def test_help_flag(self):
        panel = _load()
        old = sys.argv
        try:
            sys.argv = ["dokima", "--help"]
            with pytest.raises(SystemExit) as exc:
                panel.main()
            assert exc.value.code == 0
        finally:
            sys.argv = old

    def test_missing_args(self):
        panel = _load()
        old = sys.argv
        try:
            sys.argv = ["dokima"]
            with pytest.raises(SystemExit) as exc:
                panel.main()
            assert exc.value.code == 1
        finally:
            sys.argv = old


class TestMainInitPath:

    def test_init_creates_specs(self, tmpdir):
        panel = _load()
        project_dir = os.path.join(str(tmpdir), "init-test")
        os.makedirs(project_dir)
        with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
            f.write("# Test\n")
        import subprocess
        subprocess.run(["git", "init", project_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        old = sys.argv
        try:
            sys.argv = ["dokima", "init", "test", project_dir]
            panel.spawn_agent = _mock_spawn
            panel.main()
            assert os.path.exists(os.path.join(project_dir, "specs"))
        finally:
            sys.argv = old


class TestPipelineExecution:

    def test_strategist_called(self, tmpdir):
        """--next should call strategist then coder."""
        panel = _load()
        project_dir = _setup_test_project(panel, str(tmpdir))
        old = sys.argv
        try:
            _spawn_calls.clear()
            sys.argv = ["dokima", "--next", project_dir]
            panel.spawn_agent = _mock_spawn
            _patch_and_run(panel)
            assert len(_spawn_calls) >= 2, f"Expected >=2 calls, got {_spawn_calls}"
            assert _spawn_calls[0] == "strategist", f"First: {_spawn_calls}"
            assert "coder" in _spawn_calls, f"Got: {_spawn_calls}"
        finally:
            sys.argv = old

    def test_stop_file_exits_before_pipeline(self, tmpdir):
        """Stop file halts the loop before Phase 1."""
        panel = _load()
        project_dir = _setup_test_project(panel, str(tmpdir))
        sp = panel._stop_path(project_dir)
        with open(sp, "w") as f:
            f.write("stop\n")
        old = sys.argv
        try:
            _spawn_calls.clear()
            sys.argv = ["dokima", "--next", project_dir]
            panel.spawn_agent = _mock_spawn
            _patch_and_run(panel)
            # Stop file should be consumed
            assert not os.path.exists(sp), "Stop file not removed"
            # No agents should have been called
            assert "strategist" not in _spawn_calls, f"Strategist ran despite stop file: {_spawn_calls}"
        finally:
            sys.argv = old

    @pytest.mark.skip(reason="Integration test — needs main() refactored to isolate lock/flock from pipeline logic")
    def test_lock_held_and_released(self, tmpdir):
        """Lock is held during pipeline, released after."""
        panel = _load()
        project_dir = _setup_test_project(panel, str(tmpdir))
        lock_path = panel._lock_path(project_dir)
        lock_seen = []
        def check_lock(profile, skills, prompt, timeout=600, cwd=None):
            lock_seen.append(os.path.exists(lock_path))
            return "Mock"
        old = sys.argv
        try:
            sys.argv = ["dokima", "--next", project_dir]
            panel.spawn_agent = check_lock
            _patch_and_run(panel, mock_lock=False)  # test REAL lock behavior
            assert any(lock_seen), f"Lock never seen. Calls: {lock_seen}"
            assert not os.path.exists(lock_path), f"Lock still at {lock_path}"
        finally:
            sys.argv = old

    @pytest.mark.skip(reason="Integration test — hangs due to retry loop in unrefactored main()")
    def test_coder_failure_not_marked_done(self, tmpdir):
        """Failed coder should not mark feature as done."""
        panel = _load()
        project_dir = _setup_test_project(panel, str(tmpdir))
        def fail_coder(profile, skills, prompt, timeout=600, cwd=None):
            if profile == "coder":
                return "[CODER_FAILED]"
            return "Mock"
        old = sys.argv
        try:
            sys.argv = ["dokima", "--next", project_dir]
            panel.spawn_agent = fail_coder
            _patch_and_run(panel)
            roadmap_path = os.path.join(project_dir, "specs", "roadmap.md")
            if os.path.exists(roadmap_path):
                with open(roadmap_path) as f:
                    assert "[x] Done" not in f.read()
        finally:
            sys.argv = old


class TestVetPhase:
    """Phase 3: vet — runs build and test commands from AGENTS.md."""

    def test_vet_runs_commands_from_agents_md(self, tmpdir):
        """Vet checks out branch, runs TEST_CMD and BUILD_CMD, reports pass/fail.
        Verifies test_pass and build_pass booleans are set from real command output.
        """
        panel = _load()
        project_dir = _setup_test_project(panel, str(tmpdir))

        with patch.object(panel, 'git', return_value=("", "", 0)):
            with patch.object(panel, 'gh', return_value=("https://pr.url", "", 0)):
                with patch.object(panel, 'spawn_agent', return_value="ok"):
                    with patch.object(panel, 'halt_and_revert'):
                        result = panel.run_phase3_vet(
                            feature="Test Feature",
                            branch="feat/test-feat",
                            pr_sections="## What Changed\nTest",
                            impact="MEDIUM",
                            spec_path=""
                        )

        # Commands from AGENTS.md were actually run — results set from real output
        assert result["test_pass"] is True, f"Expected test_pass=True, got {result}"
        assert result["coder_failed"] is False
        assert result["build_pass"] is True
        assert "PASS" in result["nm_output"]

    def test_vet_detects_build_failure(self, tmpdir):
        """Vet detects build failure, retries, and returns VET_FAILED."""
        panel = _load()
        project_dir = _setup_test_project(panel, str(tmpdir))

        # Override AGENTS.md with a failing build command
        agents_path = os.path.join(project_dir, "AGENTS.md")
        with open(agents_path, "w") as f:
            f.write("# Test Project\n\n## Commands\n- Test: `echo tests-pass`\n- Build: `false`\n")

        with patch.object(panel, 'git', return_value=("", "", 0)):
            with patch.object(panel, 'gh', return_value=("", "", 0)):
                with patch.object(panel, 'spawn_agent', return_value="ok"):
                    with patch.object(panel, 'halt_and_revert'):
                        result = panel.run_phase3_vet(
                            feature="Test Feature",
                            branch="feat/test-feat",
                            pr_sections="## What Changed\nTest",
                            impact="MEDIUM",
                            spec_path=""
                        )

        assert result["coder_failed"] is True
        assert result["verdict"] == "VET_FAILED"
        assert "FAIL" in result["nm_output"]
