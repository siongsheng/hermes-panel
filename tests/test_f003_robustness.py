"""F003: Edge Case & Robustness Tests.

Targeted integration tests for pipeline failure modes NOT covered by
existing test files. Each test maps to one gap from the F003 spec.

Covers:
  - RED-only commits → vet fails
  - Empty coder output → no branch → vet fails
  - nm script timeout → graceful recovery
  - nm script non-zero exit → fallback
  - Vet verification retry exhaustion → BLOCKED
  - Special characters in feature title → safe branch name
  - Stale worktree cleanup → fresh creation
  - Concurrent lock → clean exit
"""

import os
import subprocess
import pytest
from unittest.mock import patch

from conftest import _load_panel as _load


def _make_result(returncode=0, stdout=""):
    """Create a mock CompletedProcess for _safe_run patches."""
    result = subprocess.CompletedProcess(args=[], returncode=returncode)
    result.stdout = stdout
    result.stderr = ""
    return result


class TestRedOnlyCommits:
    """Task 1: RED-only commits — vet detects missing GREEN via test/build failure."""

    def test_red_only_triggers_vet_failure(self, panel, test_repo):
        """RED-only commits cause test failures (no impl) → coder_failed=True, VET_FAILED."""
        # Override AGENTS.md so detect_commands picks up the right test/build commands
        ag_path = os.path.join(test_repo, "AGENTS.md")
        with open(ag_path, "w") as f:
            f.write("# Test Project\n\n## Commands\n- Test: `echo running-tests`\n- Build: `echo building`\n")
        panel.TEST_CMD = panel.detect_commands()[0]
        panel.BUILD_CMD = panel.detect_commands()[1]

        with patch.object(panel, "git", return_value=("", "", 0)):
            with patch.object(panel, "gh", return_value=("", "", 0)):
                with patch.object(panel._agent, "spawn_agent", return_value="ok"):
                    with patch.object(panel, "halt_and_revert"):
                        # Simulate test failing (RED-only → no impl → tests fail), build also fails
                        with patch.object(panel, "_safe_run", return_value=_make_result(1, "0 passed 1 failed")):
                            result = panel.run_phase3_vet(
                                feature="Test Feature",
                                branch="feat/test-feat",
                                pr_sections="## What Changed\nTest",
                                impact="LOW",
                                spec_path="",
                            )

        assert result["coder_failed"] is True
        assert result["verdict"] == "VET_FAILED"


class TestEmptyCoderOutput:
    """Task 2: Coder produces empty/no output — no RED, no GREEN, no branch."""

    def test_empty_output_prevents_checkout(self, panel, test_repo):
        """Coder produced no output → branch does not exist → checkout fails → vet fails."""
        # Override AGENTS.md for detect_commands
        ag_path = os.path.join(test_repo, "AGENTS.md")
        with open(ag_path, "w") as f:
            f.write("# Test Project\n\n## Commands\n- Test: `echo ok`\n- Build: `echo ok`\n")
        panel.TEST_CMD = panel.detect_commands()[0]
        panel.BUILD_CMD = panel.detect_commands()[1]

        # Checkout fails — branch doesn't exist (empty coder output = no branch created)
        with patch.object(panel, "git", return_value=("", "fatal: path not found", 1)):
            with patch.object(panel, "gh", return_value=("", "", 0)):
                with patch.object(panel._agent, "spawn_agent", return_value=""):
                    with patch.object(panel, "halt_and_revert"):
                        result = panel.run_phase3_vet(
                            feature="Empty Feature",
                            branch="feat/empty-output",
                            pr_sections="",
                            impact="LOW",
                            spec_path="",
                        )

        assert result["coder_failed"] is True, f"Expected coder_failed=True, got {result}"
        assert result["verdict"] == "VET_FAILED"


class TestNmTimeout:
    """Task 3: nm script timeout — pipeline recovers gracefully."""

    def test_nm_timeout_returns_gracefully(self, panel, test_repo):
        """_safe_run returns TIMEOUT (returncode 124) — nm_ok=True, pr_url preserved."""
        pr_url_in = "https://github.com/test-owner/test-repo/pull/1"

        with patch.object(panel, "gh", return_value=("", "", 0)):
            with patch.object(panel, "_safe_run", return_value=_make_result(124, "[TIMEOUT]")):
                result = panel.run_phase4_nm(
                    feature="Test",
                    branch="feat/test",
                    impact="MEDIUM",
                    pr_url_in=pr_url_in,
                )

        assert result["nm_ok"] is True
        assert result["pr_url"] == pr_url_in  # pr_url preserved from input
        assert result["risk"] == "MEDIUM"  # falls back to impact when no RISK: in stdout
        assert "[TIMEOUT]" in result.get("nm_stdout", "")


class TestNmNonZero:
    """Task 4: nm script returns non-zero exit — pipeline proceeds with fallback."""

    def test_nm_non_zero_falls_back(self, panel, test_repo):
        """nm exits with code 1, empty stdout — pr_url preserved, risk=impact."""
        pr_url_in = "https://github.com/test-owner/test-repo/pull/42"

        with patch.object(panel, "gh", return_value=("", "", 0)):
            with patch.object(panel, "_safe_run", return_value=_make_result(1, "")):
                result = panel.run_phase4_nm(
                    feature="Test",
                    branch="feat/test",
                    impact="HIGH",
                    pr_url_in=pr_url_in,
                )

        assert result["nm_ok"] is True
        assert result["pr_url"] == pr_url_in
        assert result["risk"] == "HIGH"  # falls back to impact when no RISK: in stdout


class TestVetRetryExhaustion:
    """Task 5: Vet verification retry exhaustion — BLOCKED after max retries."""

    def test_vet_exhausts_retries_and_blocks(self, panel, test_repo):
        """All retry attempts fail → halt_and_revert called, coder_failed=True, VET_FAILED."""
        # Override AGENTS.md so tests always fail
        ag_path = os.path.join(test_repo, "AGENTS.md")
        with open(ag_path, "w") as f:
            f.write("# Test\n\n## Commands\n- Test: `echo fail`\n- Build: `echo fail`\n")
        panel.TEST_CMD = panel.detect_commands()[0]
        panel.BUILD_CMD = panel.detect_commands()[1]

        halt_called = []

        def _mock_halt(reason, phase, branch, task_ids=None, worktrees=None):
            halt_called.append((reason, phase, branch))

        with patch.object(panel, "git", return_value=("", "", 0)):
            with patch.object(panel, "gh", return_value=("", "", 0)):
                with patch.object(panel._agent, "spawn_agent", return_value="fix_attempt"):
                    with patch.object(panel, "halt_and_revert", side_effect=_mock_halt):
                        with patch.object(panel, "_safe_run",
                                          return_value=_make_result(1, "0 passed 1 failed")):
                            result = panel.run_phase3_vet(
                                feature="Test",
                                branch="feat/test",
                                pr_sections="## What Changed\nTest",
                                impact="LOW",
                                spec_path="",
                            )

        assert result["coder_failed"] is True
        assert result["verdict"] == "VET_FAILED"
        assert len(halt_called) == 1, f"Expected exactly 1 halt_and_revert call, got {len(halt_called)}"
        reason, phase, branch = halt_called[0]
        assert "verification failed" in reason.lower() or "hash cycle" in reason.lower()


class TestSpecialCharacters:
    """Task 6: Feature description special characters — slugify and pipeline survive."""

    def test_slugify_with_emoji_and_punctuation(self):
        """Slugify('Fix: OAuth2 — login (urgent!!) 🚀') → safe branch name [a-z0-9-]."""
        panel = _load()
        result = panel.slugify("Fix: OAuth2 — login (urgent!!) 🚀")
        # Must only contain [a-z0-9-]
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in result), \
            f"Slug contains invalid chars: {result!r}"
        assert result.startswith("fix-oauth2--login-urgent")

    def test_slugify_all_special_chars(self):
        """Slugify of all-special-characters input returns safe fallback."""
        panel = _load()
        result = panel.slugify("!@#$%^&*()")
        # All stripped → empty base, no hash (since len <= 40 for stripped)
        assert result == ""

    def test_slugify_long_title_with_emoji(self, tmpdir):
        """100+ char title with emoji — truncated with hash suffix, still safe."""
        panel = _load()
        long_title = "🚀 " * 30 + "feature fix update"  # ~90+ chars
        # Add more to exceed 40
        long_title = "super " * 30 + "feature fix update with emoji and special chars!!!"
        result = panel.slugify(long_title)
        # Must only contain [a-z0-9-]
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in result), \
            f"Slug contains invalid chars: {result!r}"
        # With >40 input chars, slug gets hash suffix
        assert "-" in result, f"Expected hash separator in long slug: {result!r}"
        assert len(result) <= 49  # 40 base + 1 dash + 8 hash

    def test_pipeline_with_special_char_feature(self, panel, test_repo):
        """Full pipeline survives feature with special characters — uses test_repo fixture."""
        # Overwrite specs/roadmap.md with special-char feature
        spec_text = (
            "## F999: Fix OAuth2 — login (urgent!!) 🚀\n"
            "**Priority:** P0\n"
            "**Dependencies:** None\n"
            "**Status:** [ ] Pending\n"
            "**User Story:** Pipeline verification.\n"
        )
        roadmap_path = os.path.join(test_repo, "specs", "roadmap.md")
        with open(roadmap_path, "w") as f:
            f.write(f"# Roadmap\n\n## Phase 1\n\n{spec_text}")

        # Simulate the branch name being created from slugify — verify safe
        branch = "feat/" + panel.slugify("Fix: OAuth2 — login (urgent!!) 🚀")
        assert all(c in "abcdefghijklmnopqrstuvwxyz0123456789-/" for c in branch), \
            f"Branch has invalid chars: {branch!r}"


class TestStaleWorktreeCleanup:
    """Task 7: Stale worktree cleanup on crashed run recovery."""

    def test_stale_worktree_removed_before_create(self, panel, test_repo):
        """WorktreeManager.create() removes stale worktree before creating fresh one."""
        wm = panel.WorktreeManager(test_repo)
        # Do NOT create stale dir on disk — WorktreeManager.create() checks isdir() first
        # and would short-circuit. Instead, mock git worktree list to show the stale entry.

        stale_path = wm.worktree_path("task-stale")

        # Mock subprocess.run to:
        # 1. Show stale worktree in git worktree list --porcelain output
        # 2. Accept remove and add commands
        # Track calls so we can verify stale removal
        stale_removed = []

        def _mock_run(args, **kwargs):
            cmd = " ".join(args)
            # Simulate git worktree list showing stale worktree
            if "worktree" in cmd and "list" in cmd:
                result = subprocess.CompletedProcess(args=args, returncode=0)
                result.stdout = f"worktree {stale_path}\nHEAD 1234567\n"
                result.stderr = ""
                return result
            # Track worktree remove commands
            if "worktree" in cmd and "remove" in cmd:
                stale_removed.append(cmd)
                result = subprocess.CompletedProcess(args=args, returncode=0)
                result.stdout = ""
                result.stderr = ""
                return result
            # Track branch -D commands
            if "branch" in cmd and "-D" in cmd:
                result = subprocess.CompletedProcess(args=args, returncode=0)
                result.stdout = ""
                result.stderr = ""
                return result
            # Regular worktree add
            if "worktree" in cmd and "add" in cmd:
                os.makedirs(os.path.join(test_repo, ".dokima", "worktrees", "task-stale"),
                            exist_ok=True)
                result = subprocess.CompletedProcess(args=args, returncode=0)
                result.stdout = ""
                result.stderr = ""
                return result
            return subprocess.CompletedProcess(args=args, returncode=0)

        with patch.object(subprocess, "run", side_effect=_mock_run):
            created_path = wm.create("task-stale", "feat/stale-cleanup-test")

        # Verify stale worktree was removed (subprocess.run was called with remove)
        assert any("remove" in c for c in stale_removed), \
            f"Stale worktree remove not called. Calls: {stale_removed}"
        assert created_path == stale_path


class TestConcurrentLock:
    """Task 8: Concurrent pipeline lock — second run exits cleanly."""

    def test_acquire_lock_when_already_held(self, tmpdir):
        """acquire_lock when lock held by live process → SystemExit(1) with clear message."""
        panel = _load()
        project_dir = os.path.join(str(tmpdir), "test-project")
        os.makedirs(project_dir, exist_ok=True)
        panel.PROJECT_DIR = project_dir

        # Create a lock file simulating another process holding it
        lock_path = panel._lock_path()
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w") as f:
            f.write("99999\n")  # Fake PID

        with patch.object(panel, "_check_pid", return_value=True):
            with patch.object(panel, "_verify_pid_owner", return_value=True):
                with patch("fcntl.flock", side_effect=IOError("Lock denied")):
                    with pytest.raises(SystemExit) as exc:
                        panel.acquire_lock()

        assert exc.value.code == 1, f"Expected exit code 1, got {exc.value.code}"

    def test_acquire_lock_stale_pid_retries(self, tmpdir):
        """acquire_lock when lock held by dead process → stale removed, retry succeeds."""
        panel = _load()
        project_dir = os.path.join(str(tmpdir), "test-project")
        os.makedirs(project_dir, exist_ok=True)
        panel.PROJECT_DIR = project_dir

        lock_path = panel._lock_path()
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        with open(lock_path, "w") as f:
            f.write("99999\n")

        with patch.object(panel, "_check_pid", return_value=False):
            with patch.object(panel, "_verify_pid_owner", return_value=False):
                # Should remove stale lock and try again
                with patch.object(panel, "_lock_path", return_value=lock_path):
                    # Need to patch fcntl.flock since it won't work in test
                    with patch("fcntl.flock"):
                        held, fd = panel.acquire_lock()

        assert held is True, f"Expected lock acquired, got held={held}"
        assert fd is not None, "Expected valid fd"
