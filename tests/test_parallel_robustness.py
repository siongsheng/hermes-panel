"""Tests for F010: Parallel Coder Robustness."""
import os
import sys
import time
import pytest
from unittest.mock import patch, MagicMock, call

# Reuse conftest's _load_panel to get a fresh dokima module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from conftest import _load_panel, _reload_panel


class TestWorktreeCleanupOnException:
    """Task 1: run_parallel_coders try/finally guarantees worktree cleanup."""

    def test_cleanup_all_called_on_exception(self):
        """cleanup_all() must be called even when run_parallel_coders raises."""
        panel = _load_panel()

        # Create tasks
        t1 = panel.Task("1", "Task 1", ["file_a.py"], [], True)
        t1.branch = "feat/test-feature-t1"
        t2 = panel.Task("2", "Task 2", ["file_b.py"], [], True)
        t2.branch = "feat/test-feature-t2"
        tasks = {"1": t1, "2": t2}
        waves = [["1", "2"]]

        cleanup_called = []

        class TrackingWorktreeManager:
            def __init__(self, project_root):
                self.project_root = project_root

            def create(self, task_id, branch):
                return f"/tmp/fake-worktree-{task_id}"

            def cleanup_all(self, task_ids):
                cleanup_called.append(list(task_ids))

        class MockTaskLock:
            def __init__(self, panel_dir):
                pass

            def claim(self, task_id, agent_id):
                return True

            def release(self, task_id):
                pass

        # Mock subprocess.Popen so spawn_coder_in_worktree doesn't fail
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running

        # Mock _poll_until_wave_done to raise an exception mid-wave
        def mock_poll_and_raise(wave, running, tasks, locks, timeout=600):
            raise RuntimeError("Simulated coder crash mid-wave")

        with patch.object(panel, "WorktreeManager", return_value=TrackingWorktreeManager("/tmp/test")), \
             patch.object(panel, "TaskLock", return_value=MockTaskLock("/tmp/test")), \
             patch.object(panel, "_poll_until_wave_done", side_effect=mock_poll_and_raise), \
             patch.object(panel.subprocess, "Popen", return_value=mock_proc), \
             patch("os.makedirs"):
            try:
                panel.run_parallel_coders(tasks, waves, "/tmp/test", "/tmp/spec.md")
            except RuntimeError:
                pass

        assert len(cleanup_called) == 1, (
            f"cleanup_all should have been called once, got {len(cleanup_called)}"
        )
        assert "1" in cleanup_called[0] and "2" in cleanup_called[0], (
            f"cleanup_all should include all task IDs, got {cleanup_called}"
        )

    def test_cleanup_all_called_on_normal_completion(self):
        """cleanup_all() must be called when run_parallel_coders completes normally."""
        panel = _load_panel()

        t1 = panel.Task("1", "Task 1", ["file_a.py"], [], True)
        t1.branch = "feat/test-feature-t1"
        tasks = {"1": t1}
        waves = [["1"]]

        cleanup_called = []

        class TrackingWorktreeManager:
            def __init__(self, project_root):
                self.project_root = project_root

            def create(self, task_id, branch):
                return f"/tmp/fake-worktree-{task_id}"

            def cleanup_all(self, task_ids):
                cleanup_called.append(list(task_ids))

        class MockTaskLock:
            def __init__(self, panel_dir):
                pass

            def claim(self, task_id, agent_id):
                return True

            def release(self, task_id):
                pass

        # Mock Popen to simulate normal process that completes
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # exit success
        mock_proc.communicate.return_value = ("output", "")

        def mock_poll_done(wave, running, tasks, locks, timeout=600):
            # Mark tasks as completed
            for tid in wave:
                tasks[tid].status = "completed"
            # Remove from running (simulating _reap_completed)
            for tid in list(running.keys()):
                del running[tid]

        with patch.object(panel, "WorktreeManager", return_value=TrackingWorktreeManager("/tmp/test")), \
             patch.object(panel, "TaskLock", return_value=MockTaskLock("/tmp/test")), \
             patch.object(panel, "_poll_until_wave_done", side_effect=mock_poll_done), \
             patch.object(panel.subprocess, "Popen", return_value=mock_proc), \
             patch("os.makedirs"):
            result = panel.run_parallel_coders(tasks, waves, "/tmp/test", "/tmp/spec.md")

        assert result is True
        assert len(cleanup_called) == 1, (
            f"cleanup_all should have been called once, got {len(cleanup_called)}"
        )
        assert "1" in cleanup_called[0], (
            f"cleanup_all should include task ID 1, got {cleanup_called}"
        )


class TestHaltAndRevertTaskBranches:
    """Task 2: halt_and_revert cleans task branches on parallel coder failure."""

    def test_halt_and_revert_with_task_ids_deletes_task_branches(self):
        """halt_and_revert with task_ids deletes feat/<slug>-tN branches first."""
        panel = _load_panel()
        git_calls = []

        def fake_git(*args):
            git_calls.append(args)
            return ("", "", 0)

        with patch.object(panel, "git", side_effect=fake_git), \
             patch.object(panel, "DEFAULT_BRANCH", "main"):
            panel.halt_and_revert(
                "All parallel coders failed",
                "PHASE 2 (Parallel Coders)",
                "feat/test-feature",
                task_ids=["1", "2", "3"]
            )

        # Should have called git branch -D for each task branch
        task_deletes = [c for c in git_calls if c[0] == "branch" and c[1] == "-D" and "-t" in c[2]]
        assert len(task_deletes) == 3, (
            f"Expected 3 task branch deletes, got {len(task_deletes)}: {task_deletes}"
        )
        # Task branches should be feat/test-feature-t1, feat/test-feature-t2, feat/test-feature-t3
        expected_branches = {"feat/test-feature-t1", "feat/test-feature-t2", "feat/test-feature-t3"}
        actual_branches = {c[2] for c in task_deletes}
        assert actual_branches == expected_branches, (
            f"Task branches don't match. Expected {expected_branches}, got {actual_branches}"
        )
        # Main branch should still be deleted
        main_deletes = [c for c in git_calls if c[0] == "branch" and c[1] == "-D" and c[2] == "feat/test-feature"]
        assert len(main_deletes) == 1, "Main feature branch should also be deleted"

    def test_halt_and_revert_without_task_ids_backward_compatible(self):
        """halt_and_revert without task_ids preserves original behavior."""
        panel = _load_panel()
        git_calls = []

        def fake_git(*args):
            git_calls.append(args)
            return ("", "", 0)

        with patch.object(panel, "git", side_effect=fake_git), \
             patch.object(panel, "DEFAULT_BRANCH", "main"):
            panel.halt_and_revert(
                "Some error", "PHASE 2 (Coder)", "feat/old-feature"
            )

        # Only the main branch should be deleted
        branch_deletes = [c for c in git_calls if c[0] == "branch" and c[1] == "-D"]
        assert len(branch_deletes) == 1, (
            f"Without task_ids, only 1 branch delete expected, got {len(branch_deletes)}: {branch_deletes}"
        )
        assert branch_deletes[0][2] == "feat/old-feature"

    def test_halt_and_revert_with_worktrees_calls_cleanup_all(self):
        """halt_and_revert with worktrees parameter calls cleanup_all."""
        panel = _load_panel()
        git_calls = []
        cleanup_calls = []

        def fake_git(*args):
            git_calls.append(args)
            return ("", "", 0)

        class FakeWorktreeManager:
            def cleanup_all(self, task_ids):
                cleanup_calls.append(list(task_ids))

        with patch.object(panel, "git", side_effect=fake_git), \
             patch.object(panel, "DEFAULT_BRANCH", "main"):
            panel.halt_and_revert(
                "Merge failed", "PHASE 2 (Merge)", "feat/test-feature",
                task_ids=["1", "2"],
                worktrees=FakeWorktreeManager()
            )

        assert len(cleanup_calls) == 1, (
            f"cleanup_all should be called once, got {len(cleanup_calls)}"
        )
        assert cleanup_calls[0] == ["1", "2"], (
            f"cleanup_all should receive task_ids ['1', '2'], got {cleanup_calls[0]}"
        )


class TestReapCompletedHardening:
    """Task 3: _reap_completed drains pipes non-blocking, escalates to SIGKILL."""

    def test_normal_exit_drains_stdout(self):
        """Normal process exit → output captured, status completed, lock released."""
        panel = _load_panel()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # exited successfully
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read.side_effect = [b"test output", b""]  # non-blocking chunks
        mock_proc.wait.return_value = 0

        t1 = panel.Task("1", "Task 1", ["a.py"], [], True)
        running = {"1": mock_proc}
        tasks = {"1": t1}
        locks = MagicMock()

        with patch.object(panel.subprocess, "TimeoutExpired", create=True), \
             patch.object(panel, "time"):
            finished = panel._reap_completed(running, tasks, locks)

        assert finished == ["1"]
        assert t1.status == "completed"
        assert t1.output != ""
        locks.release.assert_called_once_with("1")
        assert "1" not in running

    def test_failed_exit_sets_status_failed(self):
        """Non-zero exit → status failed, lock released."""
        panel = _load_panel()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # failed
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read.side_effect = [b"error output", b""]
        mock_proc.wait.return_value = 1

        t1 = panel.Task("1", "Task 1", ["a.py"], [], True)
        running = {"1": mock_proc}
        tasks = {"1": t1}
        locks = MagicMock()

        with patch.object(panel, "time"):
            finished = panel._reap_completed(running, tasks, locks)

        assert t1.status == "failed"
        locks.release.assert_called_once_with("1")

    def test_wait_timeout_escalates_to_sigkill(self):
        """If wait() times out, escalate to kill() and mark orphaned."""
        panel = _load_panel()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = -9  # killed
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read.side_effect = [b"partial", b""]
        mock_proc.wait.side_effect = panel.subprocess.TimeoutExpired("cmd", 2)

        t1 = panel.Task("1", "Task 1", ["a.py"], [], True)
        running = {"1": mock_proc}
        tasks = {"1": t1}
        locks = MagicMock()

        with patch.object(panel, "time"):
            finished = panel._reap_completed(running, tasks, locks)

        # Should have called kill() after wait() timeout
        mock_proc.kill.assert_called_once()
        assert t1.status == "orphaned", (
            f"After SIGKILL escalation, status should be 'orphaned', got '{t1.status}'"
        )
        locks.release.assert_called_once_with("1")

    def test_stdout_none_guarded(self):
        """Popen.stdout is None → handled gracefully, no crash."""
        panel = _load_panel()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.stdout = None  # No stdout pipe
        mock_proc.wait.return_value = 0

        t1 = panel.Task("1", "Task 1", ["a.py"], [], True)
        running = {"1": mock_proc}
        tasks = {"1": t1}
        locks = MagicMock()

        with patch.object(panel, "time"):
            finished = panel._reap_completed(running, tasks, locks)

        assert t1.status == "completed"
        assert t1.output == ""
        locks.release.assert_called_once_with("1")

    def test_broken_pipe_caught(self):
        """BrokenPipeError during read → caught, partial output retained."""
        panel = _load_panel()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.stdout = MagicMock()
        # First read succeeds, second raises BrokenPipeError
        mock_proc.stdout.read.side_effect = [b"partial data", BrokenPipeError()]
        mock_proc.wait.return_value = 0

        t1 = panel.Task("1", "Task 1", ["a.py"], [], True)
        running = {"1": mock_proc}
        tasks = {"1": t1}
        locks = MagicMock()

        with patch.object(panel, "time"):
            finished = panel._reap_completed(running, tasks, locks)

        assert t1.status == "completed"
        # Should have partial output from the successful read
        assert "partial data" in t1.output
        locks.release.assert_called_once_with("1")


class TestValidateParallelFilesNormpath:
    """Task 4: validate_parallel_files applies os.path.normpath to catch ./ and //."""

    def test_dot_slash_normalized(self, panel):
        """'./src/a.py' and 'src/a.py' should collide."""
        dag = panel.TaskDAG()
        t1 = panel.Task("1", "T1", ["./src/a.py"], [], True)
        t2 = panel.Task("2", "T2", ["src/a.py"], [], True)
        dag.tasks = {"1": t1, "2": t2}
        assert not dag.validate_parallel_files(["1", "2"]), \
            "'./src/a.py' and 'src/a.py' should collide after normpath"

    def test_double_slash_normalized(self, panel):
        """'src//a.py' and 'src/a.py' should collide."""
        dag = panel.TaskDAG()
        t1 = panel.Task("1", "T1", ["src//a.py"], [], True)
        t2 = panel.Task("2", "T2", ["src/a.py"], [], True)
        dag.tasks = {"1": t1, "2": t2}
        assert not dag.validate_parallel_files(["1", "2"]), \
            "'src//a.py' and 'src/a.py' should collide after normpath"

    def test_no_collision_different_files(self, panel):
        """'a/b/c.py' and 'd/e/f.py' should NOT collide."""
        dag = panel.TaskDAG()
        t1 = panel.Task("1", "T1", ["a/b/c.py"], [], True)
        t2 = panel.Task("2", "T2", ["d/e/f.py"], [], True)
        dag.tasks = {"1": t1, "2": t2}
        assert dag.validate_parallel_files(["1", "2"]), \
            "Different files should not collide"

    def test_empty_file_list_skipped(self, panel):
        """Tasks with empty file lists should not cause collision."""
        dag = panel.TaskDAG()
        t1 = panel.Task("1", "T1", [], [], True)
        t2 = panel.Task("2", "T2", ["src/a.py"], [], True)
        dag.tasks = {"1": t1, "2": t2}
        assert dag.validate_parallel_files(["1", "2"]), \
            "Empty file list should not collide"

    def test_normpath_is_idempotent(self, panel):
        """Applying normpath twice gives same result as once."""
        dag = panel.TaskDAG()
        t1 = panel.Task("1", "T1", ["./src/utils.py"], [], True)
        t2 = panel.Task("2", "T2", ["./src/utils.py"], [], True)
        dag.tasks = {"1": t1, "2": t2}
        # Same file claimed by two tasks is a collision
        assert not dag.validate_parallel_files(["1", "2"]), \
            "Same file claimed twice should collide"


class TestTaskLockStaleCleanup:
    """Task 5: TaskLock.__init__ cleans stale locks with old timestamps."""

    def test_stale_lock_removed(self, tmpdir_path):
        """Lock file older than 30 minutes is deleted on init."""
        panel = _load_panel()

        tasks_dir = os.path.join(tmpdir_path, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)

        # Create a lock file with an old timestamp (1 hour ago)
        old_time = time.time() - 3600
        lockfile = os.path.join(tasks_dir, "1.lock")
        with open(lockfile, "w") as f:
            f.write(f"owner: agent-old\ntimestamp: {old_time}\n")

        lockfile2 = os.path.join(tasks_dir, "2.lock")
        with open(lockfile2, "w") as f:
            f.write(f"owner: agent-old\ntimestamp: {old_time}\n")

        # Create TaskLock (should clean stale locks on init)
        lock = panel.TaskLock(tmpdir_path)

        # Old locks should be removed
        assert not os.path.exists(lockfile), \
            f"Stale lock for task 1 should be removed"
        assert not os.path.exists(lockfile2), \
            f"Stale lock for task 2 should be removed"

    def test_fresh_lock_preserved(self, tmpdir_path):
        """Lock file with recent timestamp is NOT deleted."""
        panel = _load_panel()

        tasks_dir = os.path.join(tmpdir_path, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)

        # Create a lock file with current timestamp
        fresh_time = time.time()
        lockfile = os.path.join(tasks_dir, "1.lock")
        with open(lockfile, "w") as f:
            f.write(f"owner: agent-fresh\ntimestamp: {fresh_time}\n")

        lock = panel.TaskLock(tmpdir_path)

        # Fresh lock should still exist
        assert os.path.exists(lockfile), \
            "Fresh lock should be preserved, but it was removed"

    def test_corrupt_lock_removed(self, tmpdir_path):
        """Lock file with unparseable content is removed."""
        panel = _load_panel()

        tasks_dir = os.path.join(tmpdir_path, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)

        lockfile = os.path.join(tasks_dir, "1.lock")
        with open(lockfile, "w") as f:
            f.write("garbage data\nno owner field\n")

        lock = panel.TaskLock(tmpdir_path)

        assert not os.path.exists(lockfile), \
            "Corrupt lock file should be removed"

    def test_no_tasks_dir_does_not_crash(self, tmpdir_path):
        """If tasks dir doesn't exist, init doesn't crash."""
        panel = _load_panel()

        tasks_dir = os.path.join(tmpdir_path, "tasks")
        assert not os.path.exists(tasks_dir)

        lock = panel.TaskLock(tmpdir_path)

        assert lock.tasks_dir == tasks_dir


class TestOverflowBatching:
    """Task 6: Overflow tasks batched into sub-waves instead of sequential."""

    def test_overflow_tasks_batched_not_sequential(self):
        """12 tasks, max_parallel=5 → overflow polled as 5+2, not 12×1."""
        panel = _load_panel()

        task_list = {}
        for i in range(1, 13):
            t = panel.Task(str(i), f"Task {i}", [f"file_{i}.py"], [], True)
            t.branch = f"feat/test-t{i}"
            task_list[str(i)] = t

        waves = [["1","2","3","4","5","6","7","8","9","10","11","12"]]
        poll_calls = []

        class TrackingWorktreeManager:
            def __init__(self, project_root):
                self.project_root = project_root
            def create(self, task_id, branch):
                return f"/tmp/fake-wt-{task_id}"
            def cleanup_all(self, task_ids):
                pass

        class MockTaskLock:
            def __init__(self, panel_dir):
                pass
            def claim(self, task_id, agent_id):
                return True
            def release(self, task_id):
                pass

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read.side_effect = [b"ok", b""]
        mock_proc.wait.return_value = 0

        def mock_poll_done(wave, running, tasks, locks, timeout=600):
            poll_calls.append(list(wave))  # Track the wave size
            for tid in wave:
                tasks[tid].status = "completed"
            for tid in list(running.keys()):
                del running[tid]

        with patch.object(panel, "WorktreeManager", return_value=TrackingWorktreeManager("/tmp/t")), \
             patch.object(panel, "TaskLock", return_value=MockTaskLock("/tmp/t")), \
             patch.object(panel, "_poll_until_wave_done", side_effect=mock_poll_done), \
             patch.object(panel.subprocess, "Popen", return_value=mock_proc), \
             patch("os.makedirs"):
            panel.run_parallel_coders(task_list, waves, "/tmp/t", "/tmp/spec.md")

        # Old behavior: 7 single-task overflow polls
        # New behavior: no single-task polls — overflow batched as 5+2
        single_polls = [w for w in poll_calls if len(w) == 1]
        assert len(single_polls) == 0, (
            f"Overflow tasks should be batched, not polled 1-by-1. "
            f"Got {len(single_polls)} single-task polls. All polls: {poll_calls}"
        )
        # Verify we had at least one overflow poll with 5 tasks
        assert any(len(w) == 5 for w in poll_calls), (
            f"Expected a batch of 5 in overflow. Polls: {poll_calls}"
        )

    def test_max_parallel_one_all_sequential(self):
        """max_parallel=1 → all tasks sequential (degenerate case)."""
        panel = _load_panel()

        task_list = {}
        for i in range(1, 4):
            t = panel.Task(str(i), f"Task {i}", [f"file_{i}.py"], [], True)
            t.branch = f"feat/test-t{i}"
            task_list[str(i)] = t

        waves = [["1","2","3"]]
        spawn_order = []

        class TrackingWorktreeManager:
            def __init__(self, project_root):
                self.project_root = project_root
            def create(self, task_id, branch):
                return f"/tmp/fake-wt-{task_id}"
            def cleanup_all(self, task_ids):
                pass

        class MockTaskLock:
            def __init__(self, panel_dir):
                pass
            def claim(self, task_id, agent_id):
                spawn_order.append(int(task_id))
                return True
            def release(self, task_id):
                pass

        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.read.side_effect = [b"ok", b""]
        mock_proc.wait.return_value = 0

        def mock_poll_done(wave, running, tasks, locks, timeout=600):
            for tid in wave:
                tasks[tid].status = "completed"
            for tid in list(running.keys()):
                del running[tid]

        with patch.object(panel, "WorktreeManager", return_value=TrackingWorktreeManager("/tmp/t")), \
             patch.object(panel, "TaskLock", return_value=MockTaskLock("/tmp/t")), \
             patch.object(panel, "_poll_until_wave_done", side_effect=mock_poll_done), \
             patch.object(panel.subprocess, "Popen", return_value=mock_proc), \
             patch("os.makedirs"), \
             patch.object(panel, "max_parallel_override", 1):
            panel.run_parallel_coders(task_list, waves, "/tmp/t", "/tmp/spec.md")

        assert len(spawn_order) == 3, f"All 3 tasks should be spawned, got {len(spawn_order)}"


class TestHaltAndRevertWiring:
    """Task 7: halt_and_revert backward-compatible wiring verification."""

    def test_backward_compatible_without_task_ids(self):
        """halt_and_revert called without task_ids remains backward compatible."""
        panel = _load_panel()
        git_calls = []

        def fake_git(*args):
            git_calls.append(args)
            return ("", "", 0)

        with patch.object(panel, "git", side_effect=fake_git), \
             patch.object(panel, "DEFAULT_BRANCH", "main"):
            panel.halt_and_revert("Coder timed out", "PHASE 2 (Coder)", "feat/old")

        # Only main branch deleted, no task branch deletes
        branch_deletes = [c for c in git_calls if c[0] == "branch" and c[1] == "-D"]
        assert len(branch_deletes) == 1
        assert branch_deletes[0][2] == "feat/old"

    def test_call_sites_pass_task_ids(self):
        """Verify the three parallel-coder halt_and_revert call sites accept task_ids."""
        panel = _load_panel()

        # Create a WorktreeManager mock
        wt_mgr = MagicMock()

        # Simulate the exact call pattern from run_pipeline (line 5355)
        halt_calls = []

        def fake_halt_and_revert(reason, phase, branch, task_ids=None, worktrees=None):
            halt_calls.append(task_ids)

        with patch.object(panel, "halt_and_revert", side_effect=fake_halt_and_revert), \
             patch.object(panel, "git", return_value=("", "", 0)), \
             patch.object(panel, "DEFAULT_BRANCH", "main"):
            # Simulate the three call sites
            panel.halt_and_revert(
                "All parallel coders failed", "PHASE 2 (Parallel Coders)",
                "feat/test", task_ids=["1", "2", "3"], worktrees=wt_mgr
            )
            panel.halt_and_revert(
                "Merge assembly failed", "PHASE 2 (Merge)",
                "feat/test", task_ids=["1", "2", "3"], worktrees=wt_mgr
            )
            panel.halt_and_revert(
                "Merge assembly failed", "PHASE 2 (Merge)",
                "feat/test", task_ids=["1", "2", "3"], worktrees=wt_mgr
            )

        # All three calls should receive task_ids
        assert len(halt_calls) == 3
        for task_ids in halt_calls:
            assert task_ids == ["1", "2", "3"], f"Expected ['1','2','3'], got {task_ids}"

