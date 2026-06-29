"""Tests for F010: Parallel Coder Robustness."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

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
