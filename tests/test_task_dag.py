"""Tests for TaskDAG.compute_execution_mode() — data-driven execution mode detection.

Verifies the method derives "single_session" or "per_task_spawn" correctly
from DAG signals: task count, file count, parallelizability.
"""
import pytest
from conftest import _load_panel as _load


@pytest.fixture(scope="module")
def panel():
    return _load()


# ── Helpers ──────────────────────────────────────────────────────

def _make_dag(panel, tasks):
    """Create a TaskDAG from a list of task dicts.

    Each task dict::
        {"tid": "1", "files": ["a.py"], "deps": [], "parallel": True}
    """
    dag = panel.TaskDAG()
    for t in tasks:
        task = panel.Task(
            tid=t["tid"],
            description=t.get("desc", f"Task {t['tid']}"),
            files=t.get("files", []),
            dependencies=t.get("deps", []),
            parallelizable=t.get("parallel", True),
        )
        dag.tasks[t["tid"]] = task
    return dag


# ── single_session cases ────────────────────────────────────────

class TestSingleSession:
    def test_three_tasks_two_files_all_parallel(self, panel):
        """3 tasks, 2 files, all parallel → single_session."""
        dag = _make_dag(panel, [
            {"tid": "1", "files": ["a.py"], "parallel": True},
            {"tid": "2", "files": ["b.py"], "parallel": True},
            {"tid": "3", "files": ["a.py"], "parallel": True},
        ])
        assert dag.compute_execution_mode() == "single_session"

    def test_one_task_single_session(self, panel):
        """1 task → single_session."""
        dag = _make_dag(panel, [
            {"tid": "1", "files": ["a.py"], "parallel": True},
        ])
        assert dag.compute_execution_mode() == "single_session"

    def test_max_batch_ten_tasks_three_files(self, panel):
        """10 tasks, 3 files, all parallel → single_session (boundary)."""
        tasks = [
            {"tid": str(i), "files": [f"{chr(97 + (i % 3))}.py"], "parallel": True}
            for i in range(1, 11)
        ]
        dag = _make_dag(panel, tasks)
        assert dag.compute_execution_mode() == "single_session"

    def test_empty_dag_single_session(self, panel):
        """Empty DAG (no tasks) → single_session."""
        dag = panel.TaskDAG()
        assert dag.compute_execution_mode() == "single_session"

    def test_all_empty_files_single_session(self, panel):
        """All tasks have empty files list → single_session (count ≤ 3)."""
        dag = _make_dag(panel, [
            {"tid": "1", "files": [], "parallel": True},
            {"tid": "2", "files": [], "parallel": True},
            {"tid": "3", "files": [], "parallel": True},
        ])
        assert dag.compute_execution_mode() == "single_session"


# ── per_task_spawn cases ────────────────────────────────────────

class TestPerTaskSpawn:
    def test_non_parallelizable_task(self, panel):
        """Any non-parallelizable task → per_task_spawn."""
        dag = _make_dag(panel, [
            {"tid": "1", "files": ["a.py"], "parallel": True},
            {"tid": "2", "files": ["b.py"], "parallel": False},
        ])
        assert dag.compute_execution_mode() == "per_task_spawn"

    def test_eleven_tasks_per_task_spawn(self, panel):
        """11 tasks → per_task_spawn (exceeds 10 cap)."""
        tasks = [
            {"tid": str(i), "files": ["a.py"], "parallel": True}
            for i in range(1, 12)
        ]
        dag = _make_dag(panel, tasks)
        assert dag.compute_execution_mode() == "per_task_spawn"

    def test_four_distinct_files_per_task_spawn(self, panel):
        """4 distinct files → per_task_spawn (exceeds 3 cap)."""
        dag = _make_dag(panel, [
            {"tid": "1", "files": ["a.py"], "parallel": True},
            {"tid": "2", "files": ["b.py"], "parallel": True},
            {"tid": "3", "files": ["c.py"], "parallel": True},
            {"tid": "4", "files": ["d.py"], "parallel": True},
        ])
        assert dag.compute_execution_mode() == "per_task_spawn"

    def test_mixed_parallel_and_non_parallel(self, panel):
        """5 parallel + 1 non-parallel → per_task_spawn."""
        dag = _make_dag(panel, [
            {"tid": str(i), "files": [f"{chr(96 + i)}.py"], "parallel": True}
            for i in range(1, 6)
        ] + [
            {"tid": "6", "files": ["f.py"], "parallel": False},
        ])
        assert dag.compute_execution_mode() == "per_task_spawn"


# ── Edge cases ──────────────────────────────────────────────────

class TestEdgeCases:
    def test_duplicate_files_normalized(self, panel):
        """Duplicate files with different whitespace/case → counted once."""
        dag = _make_dag(panel, [
            {"tid": "1", "files": ["Src/App.py"], "parallel": True},
            {"tid": "2", "files": [" src/app.py "], "parallel": True},
            {"tid": "3", "files": ["SRC/APP.PY"], "parallel": True},
        ])
        # All three tasks claim the same normalized file → 1 distinct file → single_session
        assert dag.compute_execution_mode() == "single_session"
