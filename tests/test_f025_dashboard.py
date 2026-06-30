"""Tests for F025: Live Pipeline Dashboard — status.py data model and renderer."""
import os, json, tempfile
import pytest
from status import (
    PipelineStatus, TaskStatus, PhaseTiming,
    load_status, save_status, update_phase, update_task, add_task, render
)


class TestPipelineStatus:
    def test_defaults(self):
        s = PipelineStatus()
        assert s.feature == ""
        assert s.current_phase == "init"
        assert len(s.tasks) == 0
        assert s.task_total == 0

    def test_elapsed_computes_time_since_start(self):
        s = PipelineStatus()
        assert "m" in s.elapsed() or "s" in s.elapsed()  # just started

    def test_task_progress_shows_ratio(self):
        s = PipelineStatus(tasks=[TaskStatus(id="1")], task_total=3)
        s.task_completed = 2
        assert s.task_progress() == "2/3"


class TestSaveLoad:
    def test_roundtrip(self, tmpdir):
        s = PipelineStatus(feature="F001", project="/tmp/test", branch="feat/f001",
                           depth="full", risk="LOW")
        save_status(s, str(tmpdir))
        loaded = load_status(str(tmpdir))
        assert loaded is not None
        assert loaded.feature == "F001"
        assert loaded.depth == "full"
        assert str(type(loaded.tasks)) == "<class 'list'>"

    def test_load_missing_file_returns_none(self, tmpdir):
        assert load_status(os.path.join(str(tmpdir), "nonexistent")) is None

    def test_load_corrupt_file_returns_none(self, tmpdir):
        path = os.path.join(str(tmpdir), ".pipeline-status.json")
        with open(path, "w") as f:
            f.write("not json")
        assert load_status(str(tmpdir)) is None

    def test_save_atomic_does_not_leave_tmp(self, tmpdir):
        s = PipelineStatus()
        save_status(s, str(tmpdir))
        assert os.path.exists(os.path.join(str(tmpdir), ".pipeline-status.json"))
        assert not os.path.exists(os.path.join(str(tmpdir), ".pipeline-status.json.tmp"))


class TestUpdatePhase:
    def test_start_phase(self):
        s = PipelineStatus()
        update_phase(s, "coder", started=True)
        assert s.current_phase == "coder"
        assert s.phases["coder"].started_at is not None

    def test_complete_phase(self):
        s = PipelineStatus()
        update_phase(s, "coder", started=True)
        update_phase(s, "coder", started=False)
        assert s.phases["coder"].completed_at is not None

    def test_unknown_phase_ignored(self):
        s = PipelineStatus()
        update_phase(s, "nonexistent", started=True)
        assert s.current_phase == "init"


class TestUpdateTask:
    def test_add_task(self):
        s = PipelineStatus()
        add_task(s, "1", "Test task", "feat/test-t1")
        assert s.task_total == 1
        assert s.tasks[0].state == "pending"

    def test_task_lifecycle(self):
        s = PipelineStatus()
        add_task(s, "1", "Test task")
        update_task(s, "1", "running")
        assert s.tasks[0].state == "running"
        assert s.tasks[0].started_at is not None
        update_task(s, "1", "completed")
        assert s.tasks[0].state == "completed"
        assert s.task_completed == 1

    def test_task_failed_with_error(self):
        s = PipelineStatus()
        add_task(s, "1", "Buggy task")
        update_task(s, "1", "failed", "merge conflict")
        assert s.tasks[0].state == "failed"
        assert s.tasks[0].error == "merge conflict"

    def test_update_nonexistent_task_no_crash(self):
        s = PipelineStatus()
        update_task(s, "99", "completed")  # should not raise


class TestRender:
    def test_render_includes_feature(self):
        s = PipelineStatus(feature="F001", project="/tmp", branch="feat/f001",
                           depth="full", risk="LOW", log_path="/tmp/log.txt")
        out = render(s)
        assert "F001" in out
        assert "FULL" in out.upper()

    def test_render_shows_phase_status(self):
        s = PipelineStatus()
        update_phase(s, "strategist", started=True)
        update_phase(s, "strategist", started=False)
        update_phase(s, "coder", started=True)
        out = render(s)
        assert "✅" in out  # strategist done
        assert "🟢" in out  # coder running

    def test_render_shows_tasks(self):
        s = PipelineStatus()
        add_task(s, "1", "First task")
        add_task(s, "2", "Second task")
        update_task(s, "1", "completed")
        update_task(s, "2", "failed", "test error")
        out = render(s)
        assert "✅" in out
        assert "❌" in out
        assert "First task" in out
        assert "test error" in out

    def test_render_shows_errors(self):
        s = PipelineStatus()
        s.errors = ["Connection refused", "Timeout on task 3"]
        out = render(s)
        assert "Connection refused" in out
        assert "Timeout on task 3" in out

    def test_render_empty_tasks_no_section(self):
        s = PipelineStatus()
        out = render(s)
        assert "Tasks" not in out  # no task section when empty

    def test_render_includes_verdict(self):
        s = PipelineStatus(verdict="APPROVED", pr_url="https://github.com/t/pull/1")
        out = render(s)
        assert "APPROVED" in out
        assert "github.com" in out
