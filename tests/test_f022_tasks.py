"""F022 Modular Architecture — test that tasks.py exists with all required classes and functions."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest


def test_tasks_module_importable():
    """tasks.py must exist and be importable."""
    import tasks
    assert tasks is not None


def test_tasks_has_worktree_manager():
    """WorktreeManager class is in tasks.py."""
    import tasks
    assert hasattr(tasks, "WorktreeManager")


def test_tasks_has_task_lock():
    """TaskLock class is in tasks.py."""
    import tasks
    assert hasattr(tasks, "TaskLock")


def test_tasks_has_task_class():
    """Task class is in tasks.py."""
    import tasks
    assert hasattr(tasks, "Task")


def test_tasks_has_roadmap_feature():
    """RoadmapFeature class is in tasks.py."""
    import tasks
    assert hasattr(tasks, "RoadmapFeature")


def test_tasks_has_task_dag():
    """TaskDAG class is in tasks.py."""
    import tasks
    assert hasattr(tasks, "TaskDAG")


def test_tasks_has_spawn_coder_in_worktree():
    import tasks
    assert hasattr(tasks, "spawn_coder_in_worktree")
    assert callable(tasks.spawn_coder_in_worktree)


def test_tasks_has_reap_completed():
    import tasks
    assert hasattr(tasks, "_reap_completed")
    assert callable(tasks._reap_completed)


def test_tasks_has_poll_until_wave_done():
    import tasks
    assert hasattr(tasks, "_poll_until_wave_done")
    assert callable(tasks._poll_until_wave_done)


def test_tasks_has_merge_worktree_branches():
    import tasks
    assert hasattr(tasks, "merge_worktree_branches")
    assert callable(tasks.merge_worktree_branches)


def test_tasks_has_run_parallel_coders():
    import tasks
    assert hasattr(tasks, "run_parallel_coders")
    assert callable(tasks.run_parallel_coders)
