"""F022 Modular Architecture — test that roadmap.py exists with all required functions."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest


def test_roadmap_module_importable():
    """roadmap.py must exist and be importable."""
    import roadmap
    assert roadmap is not None


def test_roadmap_has_parse_roadmap():
    import roadmap
    assert hasattr(roadmap, "parse_roadmap")
    assert callable(roadmap.parse_roadmap)


def test_roadmap_has_pick_next_feature():
    import roadmap
    assert hasattr(roadmap, "pick_next_feature")
    assert callable(roadmap.pick_next_feature)


def test_roadmap_has_update_roadmap_status():
    import roadmap
    assert hasattr(roadmap, "update_roadmap_status")
    assert callable(roadmap.update_roadmap_status)


def test_roadmap_has_commit_roadmap_update():
    import roadmap
    assert hasattr(roadmap, "commit_roadmap_update")
    assert callable(roadmap.commit_roadmap_update)


def test_roadmap_has_auto_repair_status():
    import roadmap
    assert hasattr(roadmap, "auto_repair_status")
    assert callable(roadmap.auto_repair_status)


def test_roadmap_has_run_add_to_roadmap():
    import roadmap
    assert hasattr(roadmap, "run_add_to_roadmap")
    assert callable(roadmap.run_add_to_roadmap)


def test_roadmap_has_run_next_setup():
    import roadmap
    assert hasattr(roadmap, "run_next_setup")
    assert callable(roadmap.run_next_setup)


def test_roadmap_has_run_init():
    import roadmap
    assert hasattr(roadmap, "run_init")
    assert callable(roadmap.run_init)
