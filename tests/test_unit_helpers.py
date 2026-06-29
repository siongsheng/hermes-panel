"""Unit tests for remaining uncovered helper functions."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

from conftest import _load_panel as _load


# ═══════════════════════════════════════════════════════════════════
# try_auto_merge
# ═══════════════════════════════════════════════════════════════════

class TestTryAutoMerge:
    def test_merge_success(self, panel):
        """gh pr merge succeeds."""
        with patch.object(panel, "gh", return_value=("merged", "", 0)):
            result = panel.try_auto_merge("https://github.com/t/t/pull/1")
            assert result == "merged"

    def test_merge_queued(self, panel):
        """gh pr merge --auto exits 0 (queued for CI) after first merge fails with status check."""
        # First call: merge fails with "required status check" in stderr
        # Second call: --auto succeeds with rc=0
        with patch.object(panel, "gh", side_effect=[
            ("", "required status check", 1),  # first merge attempt fails
            ("queued", "", 0),                  # auto-merge succeeds
        ]):
            result = panel.try_auto_merge("https://github.com/t/t/pull/1")
            assert result == "queued"

    def test_merge_failed(self, panel):
        """PR number extraction fails or gh not available."""
        result = panel.try_auto_merge("not-a-valid-url")
        assert result == "failed"

    def test_merge_exception(self, panel):
        """gh raises exception."""
        with patch.object(panel, "gh", side_effect=OSError("not found")):
            result = panel.try_auto_merge("https://github.com/t/t/pull/1")
            assert result == "failed"


# ═══════════════════════════════════════════════════════════════════
# _get_lock_state
# ═══════════════════════════════════════════════════════════════════

class TestGetLockState:
    def test_no_lock_file(self, panel, tmpdir):
        running, pid, info = panel._get_lock_state(str(tmpdir))
        assert running is False

    def test_lock_file_with_valid_pid(self, panel, tmpdir):
        lp = panel._lock_path(str(tmpdir))
        with open(lp, "w") as f:
            f.write(f"{os.getpid()}\n")
        # Create a roadmap so info gets populated
        road_dir = os.path.join(str(tmpdir), "specs")
        os.makedirs(road_dir, exist_ok=True)
        with open(os.path.join(road_dir, "roadmap.md"), "w") as f:
            f.write("# Roadmap\n\n## Phase 1\n\n### F001: First Feature\n**Status:** [ ] Pending\n**User Story:** Test\n")
        with patch.object(panel, "_check_pid", return_value=True):
            running, pid, info = panel._get_lock_state(str(tmpdir))
        assert running is True
        assert pid == str(os.getpid())
        # info comes from roadmap parse, not from lock file
        assert info.get("total") == 1

    def test_lock_file_stale_pid(self, panel, tmpdir):
        lp = panel._lock_path(str(tmpdir))
        with open(lp, "w") as f:
            f.write("99999\n")
        with patch.object(panel, "_check_pid", return_value=False):
            running, pid, info = panel._get_lock_state(str(tmpdir))
        assert running is False
        # _get_lock_state cleans up stale lock files internally
        if os.path.exists(lp):
            os.remove(lp)


# ═══════════════════════════════════════════════════════════════════
# handle_kill remaining branches
# ═══════════════════════════════════════════════════════════════════

class TestHandleKillEdges:
    def test_sigterm_fails_with_oserror(self, panel, tmpdir):
        """os.kill raises OSError on SIGTERM."""
        panel.PROJECT_DIR = str(tmpdir)
        lp = panel._lock_path(str(tmpdir))
        with open(lp, "w") as f:
            f.write(f"{os.getpid()}\n")
        with patch.object(panel, "_get_lock_state", return_value=(True, str(os.getpid()), {})), \
             patch.object(panel, "_verify_pid_owner", return_value=True), \
             patch("os.kill", side_effect=OSError("No such process")), \
             patch.object(panel, "_check_pid", return_value=False), \
             patch("time.sleep"), \
             patch("os.remove"):
            with pytest.raises(SystemExit):
                panel.handle_kill(str(tmpdir))

    def test_sigkill_fails_with_oserror(self, panel, tmpdir):
        """SIGTERM sent → process alive → SIGKILL fails."""
        panel.PROJECT_DIR = str(tmpdir)
        lp = panel._lock_path(str(tmpdir))
        with open(lp, "w") as f:
            f.write(f"{os.getpid()}\n")
        # _verify_pid_owner called twice: once for SIGTERM check, once after sleep
        with patch.object(panel, "_get_lock_state", return_value=(True, str(os.getpid()), {})), \
             patch.object(panel, "_verify_pid_owner", side_effect=[True, True]), \
             patch.object(panel, "_check_pid", return_value=True), \
             patch("os.kill", side_effect=[None, OSError("perm")]), \
             patch("time.sleep"), \
             patch("os.remove"):
            with pytest.raises(SystemExit):
                panel.handle_kill(str(tmpdir))


# ═══════════════════════════════════════════════════════════════════
# _poll_until_wave_done
# ═══════════════════════════════════════════════════════════════════

class TestPollUntilWaveDone:
    def test_all_complete_immediately(self, panel):
        """All tasks poll as completed."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        # Non-blocking drain: stdout returns one chunk then empty
        mock_stdout = MagicMock()
        mock_stdout.read.side_effect = [b"ok", b""]
        mock_proc.stdout = mock_stdout
        mock_proc.wait.return_value = 0
        running = {"1": mock_proc}
        tasks = {
            "1": type("T", (), {"status": "pending", "output": "", "id": "1"})()
        }
        locks = MagicMock()
        panel._poll_until_wave_done(["1"], running, tasks, locks, timeout=5)
        assert tasks["1"].status == "completed"


# ═══════════════════════════════════════════════════════════════════
# merge_worktree_branches
# ═══════════════════════════════════════════════════════════════════

class TestMergeWorktree:
    def test_merge_with_conflict(self, panel):
        """git merge fails → abort → return False."""
        git_calls = []
        def fake_git(*args):
            git_calls.append(args)
            if args[0] == "merge":
                return ("", "CONFLICT", 1)
            return ("", "", 0)
        tasks = {
            "1": type("T", (), {"id": "1", "branch": "feat/t1", "status": "completed", "description": "Test task"})(),
        }
        wt_mgr = MagicMock()
        with patch.object(panel, "git", side_effect=fake_git), \
             patch("shutil.rmtree"):
            result = panel.merge_worktree_branches("feat/main", tasks, wt_mgr, "/tmp")
            assert result is False


# ═══════════════════════════════════════════════════════════════════
# auto_repair_status
# ═══════════════════════════════════════════════════════════════════

class TestAutoRepairStatus:
    def test_merged_pr_marks_done(self, panel, tmpdir):
        """Feature with merged PR → roadmap updated to done, returns count 1."""
        project_dir = str(tmpdir)
        specs_dir = os.path.join(project_dir, "specs")
        os.makedirs(specs_dir, exist_ok=True)
        panel.PROJECT_DIR = project_dir
        road_path = os.path.join(specs_dir, "roadmap.md")
        with open(road_path, "w") as f:
            f.write("# Roadmap\n\n## Phase 1\n\n### F001: Test\n**Status:** [ ] Pending\n**User Story:** Test\n")
        feat = type("F", (), {"id": "F001", "title": "Test", "status": "pending"})()
        with patch.object(panel, "gh", return_value=("PR_URL", "", 0)), \
             patch("builtins.print"):
            repaired = panel.auto_repair_status([feat], road_path)
        assert repaired == 1

    def test_no_pr_leaves_pending(self, panel):
        """No PR for pending → stays pending."""
        feat = type("F", (), {"id": "F001", "title": "Test", "status": "pending"})()
        with patch.object(panel, "gh", return_value=("", "", 1)):
            panel.auto_repair_status([feat], "/fake/roadmap.md")
            assert feat.status == "pending"


# ═══════════════════════════════════════════════════════════════════
# detect_commands edge cases
# ═══════════════════════════════════════════════════════════════════

class TestDetectCommandsEdges:
    def test_no_agents_md(self, panel, tmpdir):
        """No AGENTS.md → defaults."""
        panel.PROJECT_DIR = str(tmpdir)
        t, b, l = panel.detect_commands()
        assert t == "npm test"

    def test_fenced_code_blocks(self, panel, tmpdir):
        """AGENTS.md uses fenced code blocks."""
        project_dir = os.path.join(str(tmpdir), "proj")
        os.makedirs(project_dir)
        with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
            f.write("### Commands\n- Test:\n```\npytest --cov\n```\n- Build:\n```\nmake\n```\n")
        panel.PROJECT_DIR = project_dir
        t, b, l = panel.detect_commands()
        assert t == "pytest --cov"
        assert b == "make"

    def test_command_variants(self, panel, tmpdir):
        """Different label formats."""
        project_dir = os.path.join(str(tmpdir), "proj")
        os.makedirs(project_dir)
        with open(os.path.join(project_dir, "AGENTS.md"), "w") as f:
            f.write("### Commands\n- Unit tests: `jest`\n- Full build: `npm run build`\n- Lint: `eslint .`\n")
        panel.PROJECT_DIR = project_dir
        t, b, l = panel.detect_commands()
        assert t == "jest"
        assert b == "npm run build"
        assert l == "eslint ."


# ═══════════════════════════════════════════════════════════════════
# _cleanup_lock edge cases
# ═══════════════════════════════════════════════════════════════════

class TestCleanupLock:
    def test_cleanup_with_fd(self, panel):
        """Cleanup with valid lock fd."""
        import tempfile
        fd, path = tempfile.mkstemp()
        os.close(fd)
        panel._LOCK_FD = open(path, "w")
        panel._LOG_FILE = None
        with patch("os.remove"):
            panel._cleanup_lock()
        assert panel._LOCK_FD is None

    def test_cleanup_no_fd(self, panel):
        """Cleanup with no lock (no-op)."""
        panel._LOCK_FD = None
        panel._LOG_FILE = None
        panel._cleanup_lock()  # Should not crash


# ═══════════════════════════════════════════════════════════════════
# _signal_handler
# ═══════════════════════════════════════════════════════════════════

class TestSignalHandler:
    def test_signal_handler_cleans_and_exits(self, panel):
        """Signal received → cleanup + sys.exit(1)."""
        panel._LOG_FILE = None
        with patch.object(panel, "_cleanup_lock"):
            with pytest.raises(SystemExit) as exc:
                panel._signal_handler(15, None)
            assert exc.value.code == 1
